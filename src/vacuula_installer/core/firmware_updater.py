from __future__ import annotations

import hashlib
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

import httpx
import usb.core  # type: ignore[reportMissingTypeStubs]
from PySide6.QtCore import QObject, Signal

from vacuula_installer.core.gen23_prewifi_fix import reset_network_cmd
from vacuula_installer.core.mtp import MtpDevice
from vacuula_installer.core.neato_blast import upload_file
from vacuula_installer.core.robot_detector import RobotDetector


@dataclass(frozen=True)
class FirmwareAsset:
    filename: str
    version: str  # display version, e.g. "4.6.0"
    gen: str  # "gen3" | "gen4" -- which robots this applies to
    description_key: str  # translation key: why pick this one
    recommended: bool = False  # shown first / highlighted in the picker
    asset_id: str | None = None  # GitHub release asset id (private API, current)
    url: str | None = None  # plain direct download link (future)
    sha256: str | None = None  # expected hash; skipped if not set (fill in once known)


GITHUB_REPO = "vacuula/neato-firmware"
GITHUB_TOKEN = "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"  # temp

FIRMWARE_ASSETS: dict[str, FirmwareAsset] = {
    "gen4-1.7.0": FirmwareAsset(
        "Neato_1.7.0-2933.swu",
        version="1.7.0",
        gen="gen4",
        description_key="firmware.gen4-1.7.0.description",
        recommended=True,
        asset_id="623052647",
        sha256="ba17120082e173f38824a43831ca8998a83f8901ebd4419ecba3786d7fae28d7",
    ),
    "gen3-4.5.3": FirmwareAsset(
        "Neato_4.5.3_189.tgz",
        version="4.5.3",
        gen="gen3",
        description_key="firmware.gen3-4.5.3.description",
        recommended=True,
        asset_id="623054653",
        sha256="587018a6d51024bbd7e0e1fa01a350d80ac352352f4e7f78ff17406fbd62bbed",
    ),
    "gen3-4.6.0": FirmwareAsset(
        "Neato_4.6.0_72.tgz",
        version="4.6.0",
        gen="gen3",
        description_key="firmware.gen3-4.6.0.description",
        asset_id="623054703",
        sha256="9d7afc202b087072b30e012a468c13bde1d414acdcb2baede08b0171573719fa",
    ),
}


def assets_for_gen(gen: str) -> list[tuple[str, FirmwareAsset]]:
    """(key, asset) pairs for `gen`, recommended first."""
    items = [(k, a) for k, a in FIRMWARE_ASSETS.items() if a.gen == gen]
    items.sort(key=lambda pair: not pair[1].recommended)  # recommended=True sorts first
    return items


DOWNLOAD_TIMEOUT_S = 60.0
CHUNK_SIZE = 64 * 1024
RESET_NETWORK_TIMEOUT_S = 120.0  # 2 min, network reset can take a while
POST_RESET_SETTLE_S = 1.0


def _resolve_download(asset: FirmwareAsset) -> tuple[str, dict[str, str]]:
    """(url, headers) to request `asset` with -- hides whether it's coming
    from the private GitHub API or a plain public link."""
    if asset.url is not None:
        return asset.url, {}
    if asset.asset_id is not None:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/assets/{asset.asset_id}"
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/octet-stream"}
        return url, headers
    raise ValueError(f"Firmware asset {asset.filename!r} has neither url nor asset_id set")


def firmware_cache_dir() -> Path:
    path = Path(tempfile.gettempdir()) / "vacuula_firmware"
    path.mkdir(parents=True, exist_ok=True)
    return path


# -- updater ------------------------------------------------------------------------


class FirmwareUpdater(QObject):
    downloadProgress = Signal(str, int)  # key, percent 0-100 (-1 if unknown total)
    downloadFinished = Signal(str, str)  # key, local file path
    downloadFailed = Signal(str, str)  # key, reason

    installStepChanged = Signal(str, str)  # key, step
    installProgress = Signal(str, int)  # key, percent 0-100 (-1 if unknown total) -- only meaningful during "sending"
    installFailed = Signal(str, str)  # key, reason
    installFinished = Signal(str)  # key

    _progress = Signal(str, int)  # worker thread -> GUI thread
    _done = Signal(str, object)  # key, path on success | None on failure
    _failed = Signal(str, str)  # key, reason

    _install_step = Signal(str, str)
    _install_progress = Signal(str, int)
    _install_done = Signal(str)
    _install_failed = Signal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._active_downloads: dict[str, threading.Event] = {}
        self._active_installs: dict[str, threading.Event] = {}

        self._progress.connect(self.downloadProgress)
        self._done.connect(self._on_download_done)
        self._failed.connect(self._on_download_failed)

        self._install_step.connect(self.installStepChanged)
        self._install_progress.connect(self.installProgress)
        self._install_done.connect(self._on_install_done)
        self._install_failed.connect(self._on_install_failed)

    def download_firmware(self, key: str) -> None:
        asset = FIRMWARE_ASSETS.get(key)
        if asset is None:
            self._failed.emit(key, "Unknown firmware")
            return

        stop_event = threading.Event()
        self._active_downloads[key] = stop_event
        threading.Thread(target=self._download_worker, args=(key, asset, stop_event), daemon=True).start()

    def cancel_download(self, key: str) -> None:
        stop_event = self._active_downloads.get(key)
        if stop_event is not None:
            stop_event.set()

    def _download_worker(self, key: str, asset: FirmwareAsset, stop_event: threading.Event) -> None:
        dest = firmware_cache_dir() / asset.filename
        tmp_path = dest.with_suffix(dest.suffix + ".part")
        try:
            url, headers = _resolve_download(asset)
        except ValueError as e:
            self._fail_download(key, tmp_path, str(e))
            return

        try:
            with httpx.stream(
                "GET", url, headers=headers, follow_redirects=True, timeout=DOWNLOAD_TIMEOUT_S
            ) as response:
                if not response.is_success:
                    self._fail_download(key, tmp_path, f"HTTP {response.status_code}")
                    return
                total = int(response.headers.get("content-length", 0))
                received = 0
                last_reported = -1
                hasher = hashlib.sha256()

                with open(tmp_path, "wb") as f:
                    for chunk in response.iter_bytes(CHUNK_SIZE):
                        if stop_event.is_set():
                            self._fail_download(key, tmp_path, "Cancelled")
                            return
                        f.write(chunk)
                        hasher.update(chunk)
                        received += len(chunk)
                        percent = int(received * 100 / total) if total > 0 else -1
                        if percent != last_reported:
                            last_reported = percent
                            self._progress.emit(key, percent)

            if total > 0 and received != total:
                self._fail_download(key, tmp_path, f"Incomplete download: got {received} of {total} bytes")
                return

            if asset.sha256 is not None and hasher.hexdigest() != asset.sha256.lower():
                self._fail_download(
                    key, tmp_path, f"Checksum mismatch: expected {asset.sha256}, got {hasher.hexdigest()}"
                )
                return

            tmp_path.replace(dest)
        except (httpx.HTTPError, OSError) as e:
            self._fail_download(key, tmp_path, str(e))
            return
        except Exception as e:  # noqa: BLE001 -- report instead of dying silently in the thread
            self._fail_download(key, tmp_path, f"Unexpected error: {type(e).__name__}: {e}")
            return

        self._done.emit(key, str(dest))

    def _fail_download(self, key: str, tmp_path: Path, reason: str) -> None:
        tmp_path.unlink(missing_ok=True)
        self._failed.emit(key, reason)

    def _on_download_done(self, key: str, path: object) -> None:
        self._active_downloads.pop(key, None)
        self.downloadFinished.emit(key, str(path))

    def _on_download_failed(self, key: str, reason: str) -> None:
        self._active_downloads.pop(key, None)
        self.downloadFailed.emit(key, reason)

    # -- gen3 install ---------------------------------------------------------------

    def start_gen3_update(self, device: usb.core.Device, firmware_key: str, mac: str) -> None:
        stop_event = threading.Event()
        self._active_installs[firmware_key] = stop_event
        threading.Thread(
            target=self._gen3_install_worker, args=(firmware_key, device, mac, stop_event), daemon=True
        ).start()

    def cancel_install(self, key: str) -> None:
        stop_event = self._active_installs.get(key)
        if stop_event is not None:
            stop_event.set()

    def _gen3_install_worker(self, key: str, device: usb.core.Device, mac: str, stop_event: threading.Event) -> None:
        asset = FIRMWARE_ASSETS.get(key)
        if asset is None:
            self._install_failed.emit(key, "Unknown firmware")
            return

        file_path = firmware_cache_dir() / asset.filename
        if not file_path.exists():
            self._install_failed.emit(key, "Firmware file not found on disk -- download it first")
            return

        target_serial = RobotDetector._get_serial(device)
        port = RobotDetector._find_serial_port(device, target_serial)
        if port is None:
            self._install_failed.emit(key, "Could not find robot's serial port")
            return

        try:
            self._install_step.emit(key, "reset_network")
            cmd = reset_network_cmd(mac)
            try:
                RobotDetector.write_cmd_port_wait_terminator(port, cmd, timeout=RESET_NETWORK_TIMEOUT_S)
            except TimeoutError:
                self._install_failed.emit(key, "Timed out waiting for the robot to finish resetting its network")
                return
            except OSError as e:
                self._install_failed.emit(key, f"Could not send network-reset command: {e}")
                return

            if stop_event.wait(POST_RESET_SETTLE_S):
                self._install_failed.emit(key, "Cancelled")
                return

            def on_progress(sent: int, total: int) -> None:
                percent = int(sent * 100 / total) if total > 0 else -1
                self._install_progress.emit(key, percent)

            def on_status(status: str) -> None:
                self._install_step.emit(key, status)

            ok = upload_file(
                port,
                str(file_path),
                type="Tarball",
                updatesw_verify=True,
                progress_callback=on_progress,
                status_callback=on_status,
            )
        except Exception as e:  # noqa: BLE001 -- report instead of dying silently in the thread
            self._install_failed.emit(key, f"Unexpected error: {type(e).__name__}: {e}")
            return

        if not ok:
            self._install_failed.emit(key, "Robot rejected the upload (NAK)")
            return

        self._install_done.emit(key)

    # -- gen4 install ---------------------------------------------------------------

    def start_gen4_update(self, device: usb.core.Device, firmware_key: str) -> None:
        stop_event = threading.Event()
        self._active_installs[firmware_key] = stop_event
        threading.Thread(target=self._gen4_install_worker, args=(firmware_key, device, stop_event), daemon=True).start()

    def _gen4_install_worker(self, key: str, device: usb.core.Device, stop_event: threading.Event) -> None:
        asset = FIRMWARE_ASSETS.get(key)
        if asset is None:
            self._install_failed.emit(key, "Unknown firmware")
            return

        file_path = firmware_cache_dir() / asset.filename
        if not file_path.exists():
            self._install_failed.emit(key, "Firmware file not found on disk -- download it first")
            return

        # MTP objects (COM on Windows) must be created, used and closed on
        # this one worker thread.
        mtp = None
        try:
            self._install_step.emit(key, "connect")
            try:
                mtp = _open_mtp(device)
                mtp.open_session(1)
                storage_ids = mtp.get_storage_ids()
            except Exception as e:  # noqa: BLE001
                self._install_failed.emit(key, f"Could not connect to the robot over MTP: {e}")
                return
            if not storage_ids:
                self._install_failed.emit(key, "Robot reported no storage")
                return

            # Last point where cancelling is safe: aborting halfway through
            # the transfer would leave a partial file on the robot.
            if stop_event.is_set():
                self._install_failed.emit(key, "Cancelled")
                return

            def on_progress(sent: int, total: int) -> None:
                percent = int(sent * 100 / total) if total > 0 else -1
                self._install_progress.emit(key, percent)

            self._install_step.emit(key, "sending")
            try:
                # Path, not bytes: the file is streamed in chunks.
                mtp.send_update_file("update.swu", storage_ids[0], file_path, progress=on_progress)
            except Exception as e:  # noqa: BLE001
                self._install_failed.emit(key, f"Could not send the firmware to the robot: {e}")
                return
        except Exception as e:  # noqa: BLE001 -- report instead of dying silently in the thread
            self._install_failed.emit(key, f"Unexpected error: {type(e).__name__}: {e}")
            return
        finally:
            close = getattr(mtp, "close", None)  # Windows: releases WPD + COM
            if close is not None:
                try:
                    close()
                except Exception:  # noqa: BLE001, S110 -- defensive teardown
                    pass

        self._install_done.emit(key)

    # -- shared -------------------------------------------------------------------

    def _on_install_done(self, key: str) -> None:
        self._active_installs.pop(key, None)
        self.installFinished.emit(key)

    def _on_install_failed(self, key: str, reason: str) -> None:
        self._active_installs.pop(key, None)
        self.installFailed.emit(key, reason)


def _open_mtp(device: usb.core.Device) -> MtpDevice:
    """libusb MTP on Linux/macOS, Windows' own MTP driver on Windows."""
    if sys.platform == "win32":
        from vacuula_installer.core.mtp.windows import WindowsMtpDevice

        return WindowsMtpDevice(RobotDetector._get_serial(device))
    return MtpDevice(device)
