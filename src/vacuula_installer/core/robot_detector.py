"""Robot detection.
Multiple robots not allowed
Can be used to detect disconnection, care about polling rate

Lots here was generated using claude sonnet, for example the cross platform serial stuff cause I could not bother
"""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass
from enum import IntEnum, auto

import serial  # type: ignore[reportMissingTypeStubs]
import serial.tools.list_ports  # type: ignore[reportMissingTypeStubs]
import usb.backend.libusb1
import usb.core  # type: ignore[reportMissingTypeStubs]
import usb.util  # type: ignore[reportMissingTypeStubs]
from PySide6.QtCore import QObject, QTimer, Signal

from vacuula_installer.constants import LIBUSB_DLL

logger = logging.getLogger(__name__)

# idVendor, idProduct
GEN4_USB = [0x1D6B, 0x0100]
GEN23_USB = [0x2108, 0x780C]

SERIAL_BAUDRATE = 115200
SERIAL_TIMEOUT_S = 1.0
GET_VERSION_CMD = b"GetVersion\n"

if sys.platform == "win32":
    USB_BACKEND = usb.backend.libusb1.get_backend(find_library=lambda _: str(LIBUSB_DLL))

    if USB_BACKEND is None:
        raise RuntimeError(f"Could not load libusb backend from {LIBUSB_DLL}")
else:
    USB_BACKEND = None


@dataclass(frozen=True)
class RobotUsbId:
    usb_idVendor: int
    usb_idProduct: int
    display_name: str

    # Default values, as not all generations have a serial connection /
    # a known usb serial-number pattern respectively.
    usb_iSerial_part: str = ""
    usb_iSerial_part_pos: int = 0
    usb_iManufacturer: str = "Neato Robotics"
    usb_iProduct: str = "Neato Robot"
    serial_model: str = ""


ROBOT_IDS: tuple[RobotUsbId, ...] = (
    RobotUsbId(
        usb_idVendor=GEN4_USB[0],
        usb_idProduct=GEN4_USB[1],
        display_name="Neato D10",
        usb_iSerial_part="N2",
        usb_iSerial_part_pos=4,
    ),
    RobotUsbId(
        usb_idVendor=GEN4_USB[0],
        usb_idProduct=GEN4_USB[1],
        display_name="Neato D9",
        usb_iSerial_part="N1",
        usb_iSerial_part_pos=4,
    ),
    RobotUsbId(
        usb_idVendor=GEN4_USB[0],
        usb_idProduct=GEN4_USB[1],
        display_name="Neato D8",
        usb_iSerial_part="N3",
        usb_iSerial_part_pos=4,
    ),
    RobotUsbId(
        usb_idVendor=GEN4_USB[0],
        usb_idProduct=GEN4_USB[1],
        display_name="Neato D800",
        usb_iSerial_part="N5",
        usb_iSerial_part_pos=4,
    ),
    RobotUsbId(
        usb_idVendor=GEN23_USB[0],
        usb_idProduct=GEN23_USB[1],
        display_name="Neato Botvac D7",
        usb_iManufacturer="Acme Corporation",
        usb_iProduct="CDC Serial Peripheral",
        serial_model="BotVacD7Connected",
    ),
    RobotUsbId(
        usb_idVendor=GEN23_USB[0],
        usb_idProduct=GEN23_USB[1],
        display_name="Neato Botvac D6",
        usb_iManufacturer="Acme Corporation",
        usb_iProduct="CDC Serial Peripheral",
        serial_model="BotVacD6Connected",
    ),
    RobotUsbId(
        usb_idVendor=GEN23_USB[0],
        usb_idProduct=GEN23_USB[1],
        display_name="Neato Botvac D5",
        usb_iManufacturer="Acme Corporation",
        usb_iProduct="CDC Serial Peripheral",
        serial_model="BotVacD5Connected",
    ),
    RobotUsbId(
        usb_idVendor=GEN23_USB[0],
        usb_idProduct=GEN23_USB[1],
        display_name="Neato Botvac D4",
        usb_iManufacturer="Acme Corporation",
        usb_iProduct="CDC Serial Peripheral",
        serial_model="BotVacD4Connected",
    ),
    RobotUsbId(
        usb_idVendor=GEN23_USB[0],
        usb_idProduct=GEN23_USB[1],
        display_name="Neato Botvac D3",
        usb_iManufacturer="Acme Corporation",
        usb_iProduct="CDC Serial Peripheral",
        serial_model="BotVacD3Connected",
    ),
    RobotUsbId(
        usb_idVendor=GEN23_USB[0],
        usb_idProduct=GEN23_USB[1],
        display_name="Neato Botvac Connected",
        usb_iManufacturer="Acme Corporation",
        usb_iProduct="CDC Serial Peripheral",
        serial_model="BotVacConnected",
    ),
)


class State(IntEnum):
    NONE = 0
    ONE = auto()
    MULTIPLE = auto()


class RobotDetector(QObject):
    """Fires
        :attr:`robotDetected` when robot is detected,
        :attr:`robotDisconnected` when robot looses connection,
        :attr:`multipleRobotsDetected` if more than one detected,
    Only firing on change of state
    If class is deconstructed it can be initialised with the expected state
    """

    robotDisconnected = Signal()
    robotDetected = Signal(str, usb.core.Device)  # display_name, serial_device TODO, usb_device
    gen23VersionText = Signal(str)  # temp solution, should be looked over how exactly this should be fetched and saved

    # Probably never happens but needs to be handled:
    multipleRobotsDetected = Signal()

    def __init__(self, parent: QObject | None = None, lastState: State = State.NONE) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(False)
        self._timer.timeout.connect(self._update_robots)
        self._last_state = State(lastState)
        # Keyed by (bus, address) of the physical USB device. Avoids
        # repeating the blocking "getVersion" serial round-trip on every
        # single poll once a GEN23_USB robot has already been identified.
        self._resolved_cache: dict[tuple[int, int], RobotUsbId] = {}

    def start(self, delay_ms: int) -> None:
        """Begin polling; emits ``robotDetected`` after ``delay_ms``."""
        self._timer.start(delay_ms)

    def stop(self) -> None:
        """Cancel a pending detection, e.g. if the user navigates away."""
        self._timer.stop()
        self._last_state = State.NONE
        self._resolved_cache.clear()

    def _update_robots(self) -> None:  # ruff: ignore[C901]
        # GEN4_USB and GEN23_USB entries share one (idVendor, idProduct)
        # pair each, so query USB once per unique pair rather than once
        # per ROBOT_IDS entry.
        ids_by_usb_id: dict[tuple[int, int], list[RobotUsbId]] = {}
        for robot_id in ROBOT_IDS:
            key = (robot_id.usb_idVendor, robot_id.usb_idProduct)
            ids_by_usb_id.setdefault(key, []).append(robot_id)

        resolved: list[tuple[usb.core.Device, RobotUsbId]] = []

        gen4_devices = usb.core.find(find_all=True, idVendor=GEN4_USB[0], idProduct=GEN4_USB[1], backend=USB_BACKEND)
        for dev in gen4_devices if gen4_devices is not None else []:
            logger.debug("usb.core.find matched GEN4 device")
            if not isinstance(dev, usb.core.Device):
                logger.debug("usb.core.find returned non-Device for GEN4 device")
                continue

            descriptor_matches = [c for c in ids_by_usb_id[(0x1D6B, 0x0100)] if self._descriptor_matches(dev, c)]
            if not descriptor_matches:
                continue
            robot_id = self._resolve_robot(dev, descriptor_matches)
            if robot_id is not None:
                resolved.append((dev, robot_id))

        gen23_devices = usb.core.find(find_all=True, idVendor=GEN23_USB[0], idProduct=GEN23_USB[1], backend=USB_BACKEND)
        for dev in gen23_devices if gen23_devices is not None else []:
            logger.debug("usb.core.find matched GEN2/GEN3 device")
            if not isinstance(dev, usb.core.Device):
                logger.debug("usb.core.find returned non-Device for GEN2/GEN3 device")
                continue

            descriptor_matches = [c for c in ids_by_usb_id[(0x2108, 0x780C)]]
            robot_id = self._resolve_robot(dev, descriptor_matches)
            if robot_id is not None:
                resolved.append((dev, robot_id))

        if len(resolved) == 0:
            if self._last_state == State.ONE:
                self.robotDisconnected.emit()
            self._last_state = State.NONE
            self._resolved_cache.clear()

        elif len(resolved) == 1:
            device, robot_id = resolved[0]
            if self._last_state != State.ONE:
                self.robotDetected.emit(robot_id.display_name, device)
            self._last_state = State.ONE

        else:
            was_multiple = self._last_state == State.MULTIPLE
            self._last_state = State.MULTIPLE
            if not was_multiple:
                self.multipleRobotsDetected.emit()

    @staticmethod
    def _descriptor_matches(dev: usb.core.Device, robot_id: RobotUsbId) -> bool:
        """idVendor/idProduct alone isn't unique enough - several Neato
        generations (and potentially unrelated devices) share the same
        pair - so also check the manufacturer/product string descriptors.
        """
        if sys.platform == "win32":
            return True  # windows cannot open and read, verify by serial existing.
            # TODO: make sure other mtp devices wont show up as robots
        try:
            manufacturer = usb.util.get_string(dev, dev.iManufacturer) if dev.iManufacturer else None  # ty: ignore[unresolved-attribute]
            product = usb.util.get_string(dev, dev.iProduct) if dev.iProduct else None  # ty: ignore[unresolved-attribute]
        except (usb.core.USBError, ValueError, NotImplementedError) as e:
            return False
        return manufacturer == robot_id.usb_iManufacturer and product == robot_id.usb_iProduct

    def _resolve_robot(self, dev: usb.core.Device, candidates: list[RobotUsbId]) -> RobotUsbId | None:
        """Given a physical device and the RobotUsbId entries whose
        idVendor/idProduct/iManufacturer/iProduct all matched it, work out
        exactly which model it is. Each USB id group has exactly one valid
        way to resolve it.
        """
        usb_id = [dev.idVendor, dev.idProduct]  # ty: ignore[unresolved-attribute]

        if usb_id == GEN4_USB:
            return self._match_by_usb_serial(dev, candidates)

        if usb_id == GEN23_USB:
            return self._match_by_get_version(dev, candidates)

        return None

    @staticmethod
    def _match_by_usb_serial(dev: usb.core.Device, candidates: list[RobotUsbId]) -> RobotUsbId | None:
        serial_number = RobotDetector._get_serial(dev)

        for candidate in candidates:
            start = candidate.usb_iSerial_part_pos
            end = start + len(candidate.usb_iSerial_part)
            if serial_number[start:end] == candidate.usb_iSerial_part:
                return candidate
        return None

    def _match_by_get_version(self, dev: usb.core.Device, candidates: list[RobotUsbId]) -> RobotUsbId | None:
        cache_key = (dev.bus, dev.address)
        cached = self._resolved_cache.get(cache_key)
        if cached in candidates:
            return cached
        version_output = self._query_get_version(dev)
        self.gen23VersionText.emit(version_output or "")
        if version_output is None:
            return None
        for candidate in candidates:
            if candidate.serial_model in version_output:
                self._resolved_cache[cache_key] = candidate  # ty: ignore[invalid-assignment]
                return candidate
        return None

    @staticmethod
    def _find_serial_port(dev: usb.core.Device, target_serial: str) -> str | None:
        """Resolve the OS-specific serial port name (``COM3`` on Windows,
        ``/dev/ttyACM0`` on Linux, ``/dev/cu.usbmodemXXXX`` on macOS) for a
        pyusb device. pyserial's ``list_ports`` enumerates each platform's
        ports uniformly and reports vid/pid/serial_number regardless of
        OS, which is what makes this lookup cross-platform.
        """
        vid_pid_matches = [
            port
            for port in serial.tools.list_ports.comports()
            if port.vid == dev.idVendor and port.pid == dev.idProduct  # ty: ignore[unresolved-attribute]
        ]
        if target_serial:
            for port in vid_pid_matches:
                if port.serial_number == target_serial:
                    return port.device
        # Fall back to a bare vid/pid match - only safe when exactly one
        # candidate port is present (e.g. serial number unreadable).
        if len(vid_pid_matches) == 1:
            return vid_pid_matches[0].device
        return None

    # TODO: uart stuff should be move to separate thing for just that!!
    @staticmethod
    def write_cmd(dev: usb.core.Device, cmd: str) -> str | None:
        target_serial = RobotDetector._get_serial(dev)
        port_name = RobotDetector._find_serial_port(dev, target_serial)
        if port_name is None:
            return None
        return RobotDetector.write_cmd_port(port_name, cmd)

    @staticmethod
    def write_cmd_port(port_name: str, cmd: str) -> str | None:
        try:
            with serial.Serial(port_name, baudrate=SERIAL_BAUDRATE, timeout=SERIAL_TIMEOUT_S) as ser:
                ser.reset_input_buffer()
                ser.write(cmd.encode("ascii") + b"\n")
                ser.flush()
                raw = ser.read(4096)
        except (serial.SerialException, OSError):
            return None
        return raw.decode("ascii", errors="ignore")

    @staticmethod
    def write_cmd_port_wait_terminator(port_name: str, cmd: str, terminator: bytes = b"\x1a", timeout: float = 10.0) -> str:
        with serial.Serial(port_name, baudrate=SERIAL_BAUDRATE, timeout=0.2) as ser:
            ser.reset_input_buffer()
            ser.write(cmd.encode("ascii") + b"\n")
            ser.flush()
            buf = bytearray()
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                chunk = ser.read(4096)
                if chunk:
                    buf += chunk
                    if terminator in buf:
                        return buf.decode("ascii", errors="ignore")
            raise TimeoutError(f"timed out waiting for terminator {terminator!r}; got {bytes(buf)!r}")

    @staticmethod
    def _query_get_version(dev: usb.core.Device) -> str | None:
        return RobotDetector.write_cmd(dev, "GetVersion")

    @staticmethod
    def _get_serial(dev: usb.core.Device) -> str:
        if sys.platform == "win32":
            # libusb cannot open the device on Windows.
            if [dev.idVendor, dev.idProduct] == GEN4_USB:  # ty: ignore[unresolved-attribute]
                # Gen4 may expose only MTP (no COM port), so ask Windows'
                # device list instead. Works for both USB layouts.
                from vacuula_installer.core.mtp.windows import present_robot_serials

                try:
                    serials = present_robot_serials()
                except Exception:  # noqa: BLE001
                    logger.error("present_robot_serials could not list present robots to fetch serial")
                    serials = []
                if len(serials) == 1:
                    return serials[0]
                if serials:
                    return ""  # several robots: can't tell which libusb device is which
            # Fallback (and gen2/3): serial number of the robot's COM port.
            ports = [p for p in serial.tools.list_ports.comports() if p.vid == dev.idVendor and p.pid == dev.idProduct]
            return (ports[0].serial_number or "") if len(ports) == 1 else ""
        try:
            serial_number = dev.serial_number
        except (usb.core.USBError, ValueError, NotImplementedError):
            return ""
        return serial_number or ""
