"""Continuously reads lines from the robot's serial port in the background
and emits them, e.g. for watching install-script output."""

from __future__ import annotations

import threading

import serial  # type: ignore[reportMissingTypeStubs]
from PySide6.QtCore import QObject, Signal

READ_TIMEOUT_S = 0.5  # how often the read loop checks for a stop request


class RobotSerialMonitor(QObject):
    lineReceived = Signal(str)  # every non-empty line, as it arrives
    monitorFailed = Signal(str)  # the port could not be opened/read

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self, port: str, baudrate: int) -> None:
        self.stop()  # make sure a previous session is really gone first
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, args=(port, baudrate), daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _run(self, port: str, baudrate: int) -> None:
        try:
            with serial.Serial(port, baudrate=baudrate, timeout=READ_TIMEOUT_S) as ser:
                while not self._stop_event.is_set():
                    try:
                        raw = ser.readline()
                    except (serial.SerialException, OSError) as e:
                        self.monitorFailed.emit(str(e))
                        return
                    if not raw:
                        continue  # just a read timeout, loop and check stop again
                    line = raw.decode("ascii", errors="ignore").rstrip("\r\n")
                    if line:
                        self.lineReceived.emit(line)
        except (serial.SerialException, OSError) as e:
            self.monitorFailed.emit(str(e))
