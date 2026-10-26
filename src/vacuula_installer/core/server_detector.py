from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

import requests
from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal, Slot
from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf

from vacuula_installer.constants import M_DNS_SERVICE_TYPE
from vacuula_installer.version import validate_version

logger = logging.getLogger(__name__)

DEFAULT_SERVER_PORT = 8050
MANUAL_CERT_PATH = "/api/cert"

REQUEST_TIMEOUT_S = 3

NOT_FOUND = "not_found"                         # nothing answered at that address
NOT_VACUULA = "not_vacuula"                     # something answered, but not a usable Vacuula server
VERSION_INCOMPATIBLE = "version_incompatible"   # user needs to update server to newer version

class _ServerCheckError(Exception):
    def __init__(self, kind: str, detail: str = "") -> None:
        super().__init__(detail or kind)
        self.kind = kind
        logger.debug("Server check failed (%s): %s", kind, detail)


@dataclass(frozen=True)
class _ServerDetails:
    ip: str
    cert: str
    port: int
    gen3_port: int
    gen4_port: int
    version: str
    timezone: str


def _check_server(ip: str, port: int, cert_path: str) -> _ServerDetails:
    base_url = f"http://{ip}:{port}"
    logger.debug("Checking server at %s (cert path %s)", base_url, cert_path)

    try:
        cert_response = requests.get(f"{base_url}{cert_path}", timeout=REQUEST_TIMEOUT_S)
    except requests.RequestException as exc:

        raise _ServerCheckError(NOT_FOUND, f"no answer from {base_url}: {exc}") from exc

    if not cert_response.ok:
        raise _ServerCheckError(
            NOT_VACUULA, f"{cert_path} returned HTTP {cert_response.status_code}"
        )
    cert = cert_response.text
    if "BEGIN CERTIFICATE" not in cert:
        raise _ServerCheckError(NOT_VACUULA, f"{cert_path} did not return a certificate")

    logger.debug("Certificate looks valid, fetching server info from /api/server")
    try:
        server_response = requests.get(f"{base_url}/api/server", timeout=REQUEST_TIMEOUT_S)
    except requests.RequestException as exc:
        raise _ServerCheckError(NOT_FOUND, f"/api/server: {exc}") from exc
    logger.debug("/api/server returned HTTP %d", server_response.status_code)
    try:
        server_response.raise_for_status()
        server_info = server_response.json()
        logger.debug("/api/server JSON: %s", server_info)
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        raise _ServerCheckError(NOT_VACUULA, f"/api/server unusable: {exc}") from exc

    try:
        # validate version before reading other data
        server_version = str(server_info["version"])
        min_installer_version = str(server_info["min_installer_version"])
        valid, errmsg = validate_version(min_installer_version, server_version)
        if not valid:
            raise _ServerCheckError(VERSION_INCOMPATIBLE, f"server version {server_version} is incompatible: {errmsg}")

        gen4_port = int(server_info["gen4_port"])
        gen3_port = int(server_info["gen3_port"])
        timezone = server_info["timezone"]
    except (KeyError, TypeError, ValueError) as exc:
        raise _ServerCheckError(VERSION_INCOMPATIBLE, f"failed to parse server values: {exc}") from exc

    logger.debug("Server at %s:%d is Vacuula v%s (gen3 port %d, gen4 port %d)", ip, port, server_version, gen3_port, gen4_port)
    return _ServerDetails(ip=ip, cert=cert, port=port, gen3_port=gen3_port, gen4_port=gen4_port, version=server_version, timezone=timezone)


def _parse_address(text: str) -> tuple[str, int]:
    text = text.strip()
    for prefix in ("http://", "https://"):
        if text.lower().startswith(prefix):
            text = text[len(prefix):]
    text = text.split("/", 1)[0]

    logger.debug("Parsing user-entered address: %r", text)

    if text.count(":") == 1:  # host:port (more colons = bare IPv6)
        host, port_text = text.split(":")
        if port_text.isdigit():
            return host, int(port_text)
        return host, DEFAULT_SERVER_PORT

    return text, DEFAULT_SERVER_PORT


class _WorkerSignals(QObject):
    found = Signal(str, str, int, int, int, str)  # ip, cert, vacuula_port, gen3_port, gen4_port, timezone
    failed = Signal(str)


class _ServiceListener(ServiceListener):
    """Receives mDNS service discovery results."""

    def __init__(self) -> None:
        self.info: ServiceInfo | None = None
        self.event = threading.Event()

    def _resolve(self, zc: Zeroconf, type_: str, name: str, why: str) -> None:
        logger.debug("Service %s: %s", why, name)
        info = zc.get_service_info(type_, name, timeout=1000)
        if info is not None:
            logger.debug("Resolved service %s: %s", why, info)
            self.info = info
            self.event.set()

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self._resolve(zc, type_, name, "added")

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        # A service can be updated after initially appearing.
        self._resolve(zc, type_, name, "updated")

    def remove_service(self,zc: Zeroconf,type_: str,name: str,) -> None:
        logger.debug("Service removed: %s", name)


class _DetectionWorker(QRunnable):
    """Blocking mDNS resolution + HTTP cert fetch, dont run on GUI thread
    mDNS takes aages.."""

    def __init__(self) -> None:
        super().__init__()
        self.signals = _WorkerSignals()

    @Slot()
    def run(self) -> None:
        info = self._discover_vacuula()
        if info is None:
            self.signals.failed.emit(NOT_FOUND)
            return

        addresses = info.parsed_addresses()
        if not addresses:
            logger.warning("Vacuula service found but has no addresses")
            self.signals.failed.emit(NOT_FOUND)
            return

        # Prefer IPv4.
        ip = next((addr for addr in addresses if ":" not in addr), addresses[0])

        # DNS-SD TXT records are bytes -> bytes.
        properties = {
            self._decode_property(key): self._decode_property(value)
            for key, value in info.properties.items()
            if value is not None
        }
        cert_path = properties.get("cert-path")
        if not cert_path:
            logger.warning("Vacuula service found but has no cert-path property")
            self.signals.failed.emit(NOT_VACUULA)
            return

        try:
            details = _check_server(ip, info.port or DEFAULT_SERVER_PORT, cert_path)
        except _ServerCheckError as exc:
            logger.warning("mDNS server check failed (%s): %s", exc.kind, exc)
            self.signals.failed.emit(exc.kind)
            return

        logger.info("Vacuula server (v%s) found at %s:%d (gen4 port %d)", details.version, details.ip, details.port, details.gen4_port)
        self.signals.found.emit(details.ip, details.cert, details.port, details.gen3_port, details.gen4_port, details.timezone)

    @staticmethod
    def _discover_vacuula() -> ServiceInfo | None:
        zeroconf = Zeroconf()
        listener = _ServiceListener()
        browser = ServiceBrowser(zeroconf, M_DNS_SERVICE_TYPE, listener)
        try:
            # Wait until a service is discovered or timeout expires.
            listener.event.wait(3.0)
            return listener.info
        finally:
            # Stop browsing and release the mDNS socket.
            browser.cancel()
            zeroconf.close()

    @staticmethod
    def _decode_property(value: bytes | str) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value


class _ManualCheckWorker(QRunnable):
    """Same checks as _DetectionWorker, for one user-entered address."""

    def __init__(self, address: str) -> None:
        super().__init__()
        self.signals = _WorkerSignals()
        self._address = address

    @Slot()
    def run(self) -> None:
        host, port = _parse_address(self._address)
        if not host:
            self.signals.failed.emit(NOT_FOUND)
            return
        try:
            details = _check_server(host, port, MANUAL_CERT_PATH)
        except _ServerCheckError as exc:
            logger.warning("Manual server check failed (%s): %s", exc.kind, exc)
            
            # work with server where port is still 80 by default
            if port == DEFAULT_SERVER_PORT:
                try:
                    details = _check_server(host, 80, MANUAL_CERT_PATH)
                except _ServerCheckError as exc2:
                    logger.warning("Manual server check failed on port 80 (%s): %s", exc2.kind, exc2)
                    self.signals.failed.emit(exc.kind)
                    return
            else:
                self.signals.failed.emit(exc.kind)
                return

        logger.info(
            "Vacuula server (v%s) (manual) found at %s:%d (gen3 port %d, gen4 port %d)", 
            details.version, details.ip, details.port, details.gen3_port, details.gen4_port
        )
        self.signals.found.emit(details.ip, details.cert, details.port, details.gen3_port, details.gen4_port, details.timezone)


class ServerDetector(QObject):
    """Polls mDNS for M_DNS_SERVICE_TYPE, or checks a manual address, and
    emits the server's IP + cert once found."""

    # ip, cert, vacuula_port, gen3_port, gen4_port, manual (True = user-entered address), timezone
    serverDetected = Signal(str, str, int, int, int, bool, str)
    manualCheckFailed = Signal(str)
    invalidServerVersion = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(False)
        self._timer.timeout.connect(self._detection_logic)
        self._pool = QThreadPool.globalInstance()
        self._busy = False
        self._manual_busy = False
        self._active = False
        self._found = False
        # keep refs alive until each worker finishes
        self._workers: set[QRunnable] = set()

    def start(self, delay_ms: int) -> None:
        self._active = True
        self._found = False
        self._timer.start(delay_ms)

    def stop(self) -> None:
        self._active = False  # any in-flight mDNS result gets ignored
        self._timer.stop()  # Needed for back button

    def check_manual(self, address: str) -> None:
        """Check a user-entered address ('ip', 'ip:port', or a URL)."""
        if self._manual_busy:
            return
        self._manual_busy = True
        worker = _ManualCheckWorker(address)
        self._workers.add(worker)
        worker.signals.found.connect(
            lambda ip, cert, port, gen3, gen4, timezone, w=worker: self._on_manual_found(w, ip, cert, port, gen3, gen4, timezone)
        )
        worker.signals.failed.connect(
            lambda kind, w=worker: self._on_manual_failed(w, kind)
        )
        self._pool.start(worker)

    # -- mDNS --------------------------------------------------------------------

    def _detection_logic(self) -> None:
        if self._busy:
            return  # previous attempt still in flight; try again next tick
        self._busy = True
        worker = _DetectionWorker()
        self._workers.add(worker)
        worker.signals.found.connect(
            lambda ip, cert, port, gen3, gen4, timezone, w=worker: self._on_found(w, ip, cert, port, gen3, gen4, timezone)
        )
        worker.signals.failed.connect(lambda kind, w=worker: self._on_not_found(w, kind))
        self._pool.start(worker)

    def _on_found(self, worker: QRunnable, ip: str, cert: str, port: int, gen3_port: int, gen4_port: int, timezone: str) -> None:
        self._busy = False
        self._workers.discard(worker)
        if not self._active or self._found:
            return  # stopped, or a manual check already won
        self._finish(ip, cert, port, gen3_port, gen4_port, manual=False, timezone=timezone)

    def _on_not_found(self, worker: QRunnable, kind: str) -> None:
        self._busy = False
        self._workers.discard(worker)
        if kind == VERSION_INCOMPATIBLE:
            self.invalidServerVersion.emit()

    # -- manual ------------------------------------------------------------------

    def _on_manual_found(self, worker: QRunnable, ip: str, cert: str, port: int, gen3_port: int, gen4_port: int, timezone: str) -> None:
        self._manual_busy = False
        self._workers.discard(worker)
        if self._found:
            return  # mDNS already found one in the meantime
        self._finish(ip, cert, port, gen3_port, gen4_port, manual=True, timezone=timezone)

    def _on_manual_failed(self, worker: QRunnable, kind: str) -> None:
        self._manual_busy = False
        self._workers.discard(worker)
        if self._found:
            return
        if kind == VERSION_INCOMPATIBLE:
            self.invalidServerVersion.emit()
        else:
            self.manualCheckFailed.emit(kind)

    # -- shared ------------------------------------------------------------------

    def _finish(self, ip: str, cert: str, port: int, gen3_port: int, gen4_port: int, *, manual: bool, timezone: str) -> None:
        self._found = True
        self._timer.stop()
        self._active = False
        self.serverDetected.emit(ip, cert, port, gen3_port, gen4_port, manual, timezone)