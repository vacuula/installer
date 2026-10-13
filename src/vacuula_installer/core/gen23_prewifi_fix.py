from __future__ import annotations

import tarfile
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

import usb.core  # type: ignore[reportMissingTypeStubs]
from PySide6.QtCore import QObject, Signal

from vacuula_installer.constants import SCRIPTS_DIR
from vacuula_installer.core.neato_blast import upload_file
from vacuula_installer.core.robot_detector import RobotDetector
from vacuula_installer.core.session import SessionData


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
    return format(b, "02x")


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

    gen23_wifiReset = Signal(str)  # serial(mac), [available wifi network ssid:s]
    gen23_fwResetRequired = Signal()  # triggers page showing fw reset progress
    gen23_fwResetFinished = Signal(bool)  # successful or not TODO

    fixFailed = Signal(str)  # "upload" | "reset"

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
            target=lambda: self._uploadDone.emit(self._upload_scripts(device, session), device, mac),
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
        host = f"vacuula-local-{session.server_ip.replace('.', '-')}.nip.io"
        config_path = tmp_dir / "config"
        config_path.write_bytes(f"{host}\n".encode())

        # make tarball
        with tarfile.open(tarball, "w:gz") as tar:
            for p in (SCRIPTS_DIR / "gen3").iterdir():
                tar.add(p, arcname=p.name)
            tar.add(cert_path, arcname="cert.pem")
            tar.add(config_path, arcname="config")

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
