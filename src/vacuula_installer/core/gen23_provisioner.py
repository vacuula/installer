from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


import usb.core  # type: ignore[reportMissingTypeStubs]
from PySide6.QtCore import QObject, QTimer, Signal

from vacuula_installer._build_version import APP_VERSION
from vacuula_installer.core.gen23_ap_poller import _request
from vacuula_installer.core.robot_detector import SERIAL_BAUDRATE, RobotDetector
from vacuula_installer.core.robot_serial_monitor import RobotSerialMonitor
from vacuula_installer.core.session import SessionData

PROGRESS_INTERVAL_MS = 3000
MAX_POLL_FAILURES = 10
FINAL_HTTP_STEP = 4   # http progress: 1 wifi, 2 internet, 3 neato cloud, 4 robot

@dataclass(frozen=True)
class Milestone:
    """A line the install script prints that we watch for on the serial
    console. `step`, if set, updates the main 4-step checklist. `final`
    means: this is the end of provisioning (shuts the AP down and emits
    provisioningFinished). Add more of these to track extra sub-steps --
    they don't need a `step`, they'll just show up in the log/checklist."""

    marker: str
    label_key: str
    step: int | None = None
    final: bool = False


# Add new milestones here as the install script grows more checkpoints.
MILESTONES: tuple[Milestone, ...] = (
    Milestone("[[vacuula-installer-started]]", "provision.gen23.milestone.started", step=3),
    Milestone("[[vacuula-installer-reinstalling]]", "provision.gen23.milestone.reinstalling", step=3),
    Milestone("[[vacuula-installer-installing]]", "provision.gen23.milestone.installing", step=3),
    Milestone("[[vacuula-installer-finished]]", "provision.gen23.milestone.finished", step=4, final=True),
)

SCRIPT_FAILED = "[[vacuula-installer-failed]]" # detect when fail
LOCK_EXIT = "[[vacuula-installer-lock-exit]]" # script should not run multiple times
MAX_LOCK_EXIT_BEFORE_FAIL = 5 # if more then this many lock exit, then user never rebooted their robot like they were asked...

logger = logging.getLogger(__name__)


class Gen23Provisioner(QObject):
    progressChanged = Signal(int)        # step 1..4 the robot is currently on
    provisioningFailed = Signal(str)
    provisioningFinished = Signal()

    scriptLogLine = Signal(str)          # every serial line, for a log view
    milestoneReached = Signal(str)       # label_key of a matched milestone

    _initDone = Signal(bool)             # worker thread -> GUI thread
    _progressDone = Signal(bool, object)
    _shutdownDone = Signal()

    def __init__(self, parent: QObject, session: SessionData) -> None:
        super().__init__(parent)
        self._session = session
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._active = False
        self._busy = False
        self._failures = 0
        self._lock_exit_count = 0
        self._serial_driven = False          # True once a milestone has taken over
        self._remaining_milestones = list(MILESTONES)

        self._serial = RobotSerialMonitor(self)
        self._serial.lineReceived.connect(self._on_serial_line)

        self._initDone.connect(self._on_init_done)
        self._progressDone.connect(self._on_progress)
        self._shutdownDone.connect(self._on_shutdown_done)

    def start(self, device: usb.core.Device, ssid: str, password: str, mac: str) -> None:
        self._active = True
        self._busy = False
        self._failures = 0
        self._lock_exit_count = 0
        self._serial_driven = False
        self._remaining_milestones = list(MILESTONES)
        logging.debug("prepping provisioning for %s on %s", mac, ssid)

        target_serial = RobotDetector._get_serial(device)
        self._port = RobotDetector._find_serial_port(device, target_serial)

        logging.debug("found serial port %s for %s", self._port, target_serial)

        # UTC0 all year by default
        try:
            tz = self._session.timezone or "Atlantic/Reykjavik" 
            tz_offset = timezone_offsets(tz)
        except Exception:
            logger.exception("timezone lookup failed, falling back to UTC")
            tz, tz_offset = "Atlantic/Reykjavik", "UTC+0:00UTC+0:00"
        utc_offset = tz_offset + ";{ /bin/tar xOzf /tmp/upload init.sh|/bin/sh &}"

        # TODO: show this error to the user in some way as well!!!
        if (len(utc_offset) > 68):
            raise ValueError(f"utc_offset string is too long ({len(utc_offset)} > 68): {utc_offset}")

        body = {
            "name": f"{mac}--IV--{APP_VERSION}",
            "password": password,
            "server_urls": {"beehive": "vacuula", "ntp": "pool.ntp.org", "nucleo": "vacuula"},
            "ssid": ssid,
            "timezone": tz,
            "user_id": "vacuula-user",
            "utc_offset": utc_offset,
        }
        logger.debug("starting provisioning on %s", self._port)
        threading.Thread(
            target=lambda: self._initDone.emit(
                _request("PUT", "/robot/initialize", 15.0, body)[0]),
            daemon=True,
        ).start()

    def stop(self) -> None:
        self._active = False
        self._timer.stop()
        self._serial.stop()

    # -- http progress (steps 1-2-3, until a milestone takes over) --------------

    def _on_init_done(self, ok: bool) -> None:
        logger.debug("initialize done, ok=%s", ok)
        if not self._active:
            return
        if not ok:
            self.stop()
            self.provisioningFailed.emit("initialize")
            return
        if self._port is not None:
            self._serial.start(self._port, SERIAL_BAUDRATE)
        self._timer.start(PROGRESS_INTERVAL_MS)
        self._poll()

    def _poll(self) -> None:
        if self._busy or self._serial_driven:
            return
        self._busy = True
        threading.Thread(
            target=lambda: self._progressDone.emit(
                *_request("GET", "/robot/wifi_networks/new/progress")),
            daemon=True,
        ).start()

    def _on_progress(self, ok: bool, data: object) -> None:
        self._busy = False
        if not self._active or self._serial_driven:
            return
        step = data.get("step") if ok and isinstance(data, dict) else None
        if not isinstance(step, int):
            self._failures += 1
            if self._failures >= MAX_POLL_FAILURES:
                self.stop()
                self.provisioningFailed.emit("progress")
            return
        self._failures = 0
        self.progressChanged.emit(step)
        if step >= FINAL_HTTP_STEP:
            self._timer.stop()
            self._finish()

    # -- serial milestones (take over once the script starts logging) -----------

    def _on_serial_line(self, line: str) -> None:
        self.scriptLogLine.emit(line)
        logger.debug("serial line: %s", line)
        if SCRIPT_FAILED in line:
            self.stop()
            self.provisioningFailed.emit("script")
            return
        if LOCK_EXIT in line:
            self._lock_exit_count += 1
            if self._lock_exit_count > MAX_LOCK_EXIT_BEFORE_FAIL:
                self.stop()
                self.provisioningFailed.emit("lock_exit")
                return
        for milestone in list(self._remaining_milestones):
            if milestone.marker in line:
                self._remaining_milestones.remove(milestone)
                self._handle_milestone(milestone)

    def _handle_milestone(self, milestone: Milestone) -> None:
        self.milestoneReached.emit(milestone.label_key)
        if milestone.step is not None:
            self._serial_driven = True   # stop trusting http progress from here
            self._timer.stop()
            self.progressChanged.emit(milestone.step)
        if milestone.final:
            self._serial.stop()
            self._finish()

    # -- finishing ----------------------------------------------------------------

    def _finish(self) -> None:
        self._shutdownDone.emit()

    def _on_shutdown_done(self) -> None:
        if self._active:
            self._active = False
            self.provisioningFinished.emit()


def timezone_offsets(timezone_name):
    tz = ZoneInfo(timezone_name)

    def fmt(dt):
        offset = int(dt.utcoffset().total_seconds() // 60)
        hours, minutes = divmod(abs(offset), 60)
        sign = "+" if offset >= 0 else "-"
        return f"UTC{sign}{hours}:{minutes:02d}"

    winter = datetime(2026, 1, 15, tzinfo=tz)
    summer = datetime(2026, 7, 15, tzinfo=tz)

    return f"{fmt(winter)}{fmt(summer)}"
