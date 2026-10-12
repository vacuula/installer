from __future__ import annotations

import sys
import threading

import usb.core  # type: ignore[reportMissingTypeStubs]
from PySide6.QtCore import QObject, Signal

from vacuula_installer.core.mtp import MtpDevice
from vacuula_installer.core.robot_detector import RobotDetector

VALID_GEN3_VERSIONS = [
    ("4.5.3", "Software,4,5,3,189,0"),
    ("4.6.0", "Software,4,6,0,72,0"),
]

VALID_GEN4_VERSIONS = [
    ("1.7.0", "Firmware version: 1.7.0-2933"),
]

# TODO Nonblocking thread, see server detector


class FirmwareDetector(QObject):
    _done = Signal(bool, str)  # worker thread -> GUI thread
    firmwareDetected = Signal(
        bool, str
    )  # true if valid firmware detected, false if not | str is either the version string or an error message

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._active = False
        self._done.connect(self._on_done)

    def detect(self, device: usb.core.Device, gen23_version: str | None) -> None:
        "Pick gen23/gen4 based on if GetVersion was sent"
        self._active = True

        if gen23_version is not None:
            # gen23:
            self._done.emit(*self._match_gen23(gen23_version))
            return

        # gen4:
        threading.Thread(
            target=lambda: self._done.emit(*self._detect_gen4(device)),
            daemon=True,
        ).start()

    def stop(self) -> None:
        self._active = False

    @staticmethod
    def _match_gen23(gen23_version: str) -> tuple[bool, str]:
        "Check the GetVersion result, search for a valid string and return version"
        for version, version_search in VALID_GEN3_VERSIONS:
            if version_search in gen23_version:
                return True, version
        return False, "error.firmware.invalid"

    @staticmethod
    def _detect_gen4(device: usb.core.Device) -> tuple[bool, str]:
        "Connect to MTP, read version.txt and search for valid string, return version"
        if sys.platform == "win32":
            from vacuula_installer.core.mtp.windows import WindowsMtpDevice

            serial_number = RobotDetector._get_serial(device)
            with WindowsMtpDevice(serial_number) as mtp:
                mtp.open_session(1)
                storage_id = mtp.get_storage_ids()[0]
                raw_version_data = mtp.read_file(storage_id, ["version.txt"])
        else:
            try:
                mtp = MtpDevice(device)
                mtp.open_session(1)
                storage_id = mtp.get_storage_ids()[0]
                raw_version_data = mtp.read_file(storage_id, ["version.txt"])
            except Exception:  # noqa: BLE001
                return False, "error.generic.connect"

        if raw_version_data is None:
            return False, "error.gen4.unreadable"

        version_data = raw_version_data.decode("utf-8", errors="ignore")
        for version, version_search in VALID_GEN4_VERSIONS:
            if version_search in version_data:
                return True, version
        return False, "error.firmware.invalid"

    def _on_done(self, ok: bool, result: str) -> None:
        if not self._active:
            return
        self._active = False
        self.firmwareDetected.emit(ok, result)
