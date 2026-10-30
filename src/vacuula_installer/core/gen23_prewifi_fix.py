from __future__ import annotations

from os import mkdir
import tarfile
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

import usb.core  # type: ignore[reportMissingTypeStubs]
from PySide6.QtCore import QObject, Signal

from vacuula_installer.constants import GEN3_DEFAULT_PORT, SCRIPTS_DIR
from vacuula_installer.core.neato_blast import upload_file
from vacuula_installer.core.robot_detector import RobotDetector
from vacuula_installer.core.session import SessionData

def _arm_movw(rd: int, value: int) -> bytes:
    """ARM (A1) 'MOVW Rd, #imm16' little-endian: imm12[7:0], Rd|imm12[11:8], imm4, 0xE3"""
    return bytes([value & 0xFF, (rd << 4) | ((value >> 8) & 0xF), (value >> 12) & 0xF, 0xE3])

def gen3_port_patch_files(port: int) -> dict[str, bytes]:
    """Byte snippets used by scripts/gen3/vacuula.sh (make_mod) to move Gen3 from 443 to `port`.
    p_* = new bytes, o_* = original bytes expected before patching. Empty for the default port."""
    if port == 443:
        return {}
    if not 100 <= port <= 999:
        raise ValueError(f"invalid gen3 port {port}")
    return {
        # original bytes
        "o_str": b"\0\0\0" + f"{443}\0".encode(),  # 3 null bytes + "443\0"
        "o_movw1": _arm_movw(1, 443),
        "o_movw2": _arm_movw(2, 443),

        # patch bytes
        "p_str": b"\0\0\0" + f"{port}\0".encode(), # same as original 3 null + "port\0"
        "p_movw1": _arm_movw(1, port),
        "p_movw2": _arm_movw(2, port)
    }

def gen3_bmu_patch_files() -> dict[str, bytes]:
    """Byte snippets used by scripts/gen3/vacuula.sh (make_mod) to bypass battery
    auth and mfg_access fault checks in libNeatoBMU on non-oem bq40z50 packs."""
    return {
        # original bytes
        "o_bmu": b"\x6d\xff\xff\xeb",      # bl auth_check (NeatoBMU::authenticate)
        "o_bmu_flt": b"\xb2\x21\x5b\xe1",  # ldrh r2, [fp, #-0x12] (mfg_access)

        # patch bytes
        "p_bmu": b"\x01\x00\xa0\xe3",      # mov r0, #1 (return true)
        "p_bmu_flt": b"\x00\x20\xa0\xe3",  # mov r2, #0 (clear fault)

        # smbus_read_word retry patch: some aftermarket bq40z50 packs randomly
        # NAK SMBus reads, and since the stock wrapper is single-shot it will 
        # imidiately assume the read failed and return 0, to help with this we 
        # simply make use of i2c_read_robust instad of the normally used i2c_read. 
        # Region 1 seeds a retry counter into the unused flag local. 
        # Region 2 reloads the GOT base, decrements the counter and branches back 
        # to the arg-reload at 0x11cc0 (5 attempts).
        "o_bmu_srw1": b"\x10\x20\x0b\xe5\x00\x20\xa0\xe1\x05\x20\x4b\xe5",
        "o_bmu_srw2": (
            b"\x00\x30\xa0\xe1\x00\x00\x53\xe3\x00\x30\xa0\x13\x01\x30\xa0\x03"
            b"\x73\x30\xef\xe6\x00\x00\x53\xe3\x01\x00\x00\x0a\x00\x30\xe0\xe3"
            b"\x00\x00\x00\xea"
        ),
        "p_bmu_srw1": b"\x05\x20\xa0\xe3\x10\x20\x0b\xe5\x05\x00\x4b\xe5",  
        "p_bmu_srw2": (
            b"\x00\x00\x50\xe3\x06\x00\x00\x1a\x24\x30\x9f\xe5\x03\x30\x8f\xe0" 
            b"\x54\x30\x43\xe2\x10\x20\x1b\xe5\x01\x20\x53\xe2\x10\x20\x0b\xe5"
            b"\xe9\xff\xff\x1a"
        ),
    }

def rc4_ksa(S, key):
    for i in range(256):
        S[i] = i

    j = 0
    for i in range(256):
        j = (j + S[i] + key[i % len(key)]) & 0xFF
        S[i], S[j] = S[j], S[i]


def rc4_prga(S, length):
    out = [0] * length
    i = j = 0

    for k in range(length):
        i = (i + 1) & 0xFF
        j = (j + S[i]) & 0xFF
        S[i], S[j] = S[j], S[i]
        out[k] = S[(S[i] + S[j]) & 0xFF]

    return out


def string_to_bytes(s):
    return [ord(c) for c in s]


def byte_to_hex(b):
    return format(b, '02x')


def mac_to_skey(mac, key="h6CX\t\t:<*{Y"):
    S = [0] * 256
    key_bytes = string_to_bytes(key)
    rc4_ksa(S, key_bytes)

    stream = rc4_prga(S, 256)
    mac_bytes = string_to_bytes(mac)

    result = ""
    for i in range(len(mac_bytes)):
        result += byte_to_hex(stream[i] ^ mac_bytes[i])

    extra_char = result[len(mac_bytes) >> 1]
    result += extra_char

    return result


def reset_network_cmd(mac: str):
    skey = mac_to_skey(mac)
    return f"SetWifi reset_network skey {skey}"


def getversion_cmd():
    return "GetVerion"

@dataclass(frozen=True)
class File:
    filename: str
    sha256: str

class Gen23WiFiFixer(QObject):
    """Uploads the install scripts over serial, then tells the robot to
    reset its network. Runs on a worker thread so the GUI doesn't freeze
    during the (potentially slow) serial upload."""

    gen23_wifiReset = Signal(str)        # serial(mac), [available wifi network ssid:s]
    gen23_fwResetRequired = Signal()     # triggers page showing fw reset progress
    gen23_fwResetFinished = Signal(bool)  # successful or not TODO

    fixFailed = Signal(str)              # "upload" | "reset"

    _uploadDone = Signal(bool, object, object)  # ok, device, mac -- worker thread -> GUI thread
    _resetDone = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._active = False
        self._uploadDone.connect(self._on_upload_done)
        self._resetDone.connect(self._on_reset_done)

    @staticmethod
    def gen23_get_mac_from_version(get_version: str | None) -> str | None:
        if not get_version:
            return None
        serial = get_version.split("MainBoard Serial Number,")[1].split(",")[1].strip()
        if len(serial) == 12:
            return serial
        return None

    # TODO: resolve port here instead of later on in the code but meh for now, not in initial release
    def fix_robot(self, device: usb.core.Device, mac: str, session: SessionData) -> None:
        self._active = True
        threading.Thread(
            target=lambda: self._uploadDone.emit(
                self._upload_scripts(device, session), device, mac
            ),
            daemon=True,
        ).start()

    def stop(self) -> None:
        self._active = False

    # -- upload (worker thread) --------------------------------------------------

    def _upload_scripts(self, device: usb.core.Device, session: SessionData) -> bool:
        target_serial = RobotDetector._get_serial(device)
        port = RobotDetector._find_serial_port(device, target_serial)
        if port is None:
            return False

        with tempfile.TemporaryDirectory() as tmp:  # deleted when the block exits
            tarball = self._generate_tarball(Path(tmp), session)
            try:
                upload_file(port, str(tarball), "Tarball", noburn=True)
            except Exception:  # noqa: BLE001
                return False
        return True

    def _generate_tarball(self, tmp_dir: Path, session: SessionData) -> Path:
        tarball = tmp_dir / "vacuula.tar.gz"
        if not session.server_certificate or not session.server_ip:
            return tarball

        # cert
        cert_path = tmp_dir / "cert.pem"
        cert_path.write_bytes(session.server_certificate.encode())

        # additional info
        ip = session.server_ip
        gen3_port = session.gen3_port or GEN3_DEFAULT_PORT
        config_path = tmp_dir / "config"
        config_path.write_bytes(f"{ip}\n{gen3_port}\n".encode())
        # line 1: ip
        # line 2: port

        patch_files = gen3_port_patch_files(gen3_port)
        patch_files.update(gen3_bmu_patch_files())
        port_patch_dir = tmp_dir / "port_patch"
        port_patch_dir.mkdir(exist_ok=True)
        for name, data in patch_files.items():
            (port_patch_dir / name).write_bytes(data)

        # make tarball
        with tarfile.open(tarball, "w:gz") as tar:
            for p in (SCRIPTS_DIR / "gen3").iterdir():
                tar.add(p, arcname=p.name)
            tar.add(cert_path, arcname="cert.pem")
            tar.add(config_path, arcname="config")
            tar.add(port_patch_dir, arcname="port_patch")

        return tarball

    # -- upload result (GUI thread) -----------------------------------------------

    def _on_upload_done(self, ok: bool, device: usb.core.Device, mac: str) -> None:
        if not self._active:
            return
        if not ok:
            self._active = False
            self.fixFailed.emit("error.generic.upload")
            return
        threading.Thread(
            target=lambda: self._resetDone.emit(self._reset_network(device, mac)),
            daemon=True,
        ).start()

    # -- reset (worker thread) ---------------------------------------------------

    @staticmethod
    def _reset_network(device: usb.core.Device, mac: str) -> bool:
        cmd = reset_network_cmd(mac)
        return RobotDetector.write_cmd(device, cmd) is not None

    # -- reset result (GUI thread) ------------------------------------------------

    def _on_reset_done(self, ok: bool) -> None:
        if not self._active:
            return
        self._active = False
        if not ok:
            self.fixFailed.emit("error.gen23.reset")