from __future__ import annotations

import logging
import ssl
import threading
from typing import Any

import httpx
from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger(__name__)

BASE_URL = "https://192.168.219.1:4443"
POLL_INTERVAL_MS = 5000

# taken from app
HEADERS = {
    "accept": "application/vnd.neato.beehive.v1+json",
    "content-type": "application/json",
    "authorization": "Token token=vacuula-is-awesome",
    "accept-encoding": "gzip",
    "user-agent": "okhttp/4.9.1",
}


def _legacy_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        ctx.set_ciphers("ALL:@SECLEVEL=0")
    except ssl.SSLError:
        pass
    try:
        ctx.minimum_version = ssl.TLSVersion.TLSv1
    except (ValueError, ssl.SSLError):
        pass
    return ctx


def _request(method: str, path: str, read_timeout: float | None = 5, json_body: Any | None = None) -> tuple[bool, Any | None]:
    try:
        with httpx.Client(
            verify=_legacy_ssl_context(),
            http2=True,
            timeout=httpx.Timeout(read_timeout, connect=2.0),
            headers=HEADERS,
        ) as client:
            logger.debug(f"Requesting {method} {BASE_URL}{path}")
            r = client.request(method, f"{BASE_URL}{path}", json=json_body)
    except (httpx.HTTPError, ssl.SSLError, OSError):
        logger.error(f"Request failed: {method} {BASE_URL}{path}")
        return False, None
    if not r.is_success:
        logger.debug(f"Request not successful: {method} {BASE_URL}{path}, status: {r.status_code}")
        return False, None
    try:
        return True, r.json()
    except ValueError:
        return True, None


def _get_json(path: str, read_timeout: float | None = 5) -> Any | None:
    ok, data = _request("GET", path, read_timeout)
    return data if ok else None


def fetch_info() -> dict[str, Any] | None:
    data = _get_json("/info")
    if data is None:
        return None
    return data if isinstance(data, dict) else {"data": data}


def fetch_wifi_networks() -> list[dict[str, Any]] | None:
    data = _get_json("/wifi_networks", None)
    return data if isinstance(data, list) else None


class Gen23ApPoller(QObject):
    infoReceived = Signal(dict)  # robot answered: user is on its wifi
    requestFailed = Signal()  # a check failed (timer keeps running)

    _done = Signal(object)  # worker thread -> GUI thread
    networksReceived = Signal(list)  # [{"ssid": str, "strength": int}, ...]
    networksFailed = Signal()
    _networks_done = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._request)
        self._active = False
        self._busy = False
        self._done.connect(self._on_done)
        self._networks_done.connect(self._on_networks_done)

    def fetch_networks(self) -> None:
        threading.Thread(target=lambda: self._networks_done.emit(fetch_wifi_networks()), daemon=True).start()

    def _on_networks_done(self, networks: object) -> None:
        if networks is None:
            self.networksFailed.emit()
        else:
            self.networksReceived.emit(networks)

    def start(self) -> None:
        self._active = True
        self._timer.start(POLL_INTERVAL_MS)

    def stop(self) -> None:
        self._active = False
        self._timer.stop()

    def check_now(self) -> None:
        self._active = True
        self._timer.stop()
        self._request()

    def _request(self) -> None:
        if self._busy:
            return
        self._busy = True
        threading.Thread(target=lambda: self._done.emit(fetch_info()), daemon=True).start()

    def _on_done(self, info: object) -> None:
        self._busy = False
        if not self._active:
            return
        if info is not None:
            self.stop()
            self.infoReceived.emit(info)
        else:
            self.requestFailed.emit()
            self._timer.start(POLL_INTERVAL_MS)
