"""macOS MTP: plain libusb, but first get ptpcamerad out of the way.

macOS's ptpcamerad grabs every PTP-class (USB class 6) interface as soon as
the robot is plugged in and holds it exclusively, so libusb's claim fails with
"Access denied". It never shows the robot in Image Capture either (umtprd
speaks MTP, not camera PTP). Killing it is harmless: it's a per-user
launchd agent that respawns on demand, which is why we retry.

Unlike the base class we never dev.reset(): on macOS a reset re-enumerates
the robot, leaving our handle stale and handing ptpcamerad a fresh grab.
"""

from __future__ import annotations

import logging
import subprocess
import time

import usb.core
import usb.util

from . import MtpDevice, MtpError
from .consts import Operations

logger = logging.getLogger(__name__)

CLAIM_ATTEMPTS = 5
CLAIM_RETRY_DELAY_S = 0.3


def release_from_ptpcamerad() -> None:
    # SIGKILL: it ignores SIGTERM while Image Capture.app is open and polling it.
    subprocess.run(["pkill", "-9", "-x", "ptpcamerad"], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _bulk_endpoints(dev: usb.core.Device):
    for interface in dev.get_active_configuration():
        if interface.bInterfaceClass != 6:  # PICTURE class (MTP is subclass of PTP)
            continue
        ep_in = usb.util.find_descriptor(interface, custom_match=lambda e: (
            usb.util.endpoint_type(e.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK
            and usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN))
        ep_out = usb.util.find_descriptor(interface, custom_match=lambda e: (
            usb.util.endpoint_type(e.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK
            and usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT))
        if ep_in is not None and ep_out is not None:
            return ep_in, ep_out
    raise MtpError("Could not find MTP endpoints")


class MacMtpDevice(MtpDevice):
    # Callers never close their MtpDevice, and an earlier one's claim would
    # block the next (firmware check, then provisioning): release it first.
    _previous: usb.core.Device | None = None

    def __init__(self, dev: usb.core.Device):
        if MacMtpDevice._previous is not None:
            usb.util.dispose_resources(MacMtpDevice._previous)
        MacMtpDevice._previous = dev
        self.ep_in, self.ep_out = _bulk_endpoints(dev)
        self._tx_id = -1

    def open_session(self, session_id):
        for attempt in range(1, CLAIM_ATTEMPTS + 1):
            release_from_ptpcamerad()
            # OpenSession must go out as transaction 0, including on retries.
            self._tx_id = -1
            try:
                return super().open_session(session_id)
            except usb.core.USBError as e:
                if e.errno != 13 or attempt == CLAIM_ATTEMPTS:
                    raise
                logger.debug("Interface still held by ptpcamerad, retry %d", attempt)
                time.sleep(CLAIM_RETRY_DELAY_S)
            except MtpError:
                # Without a reset, a session left open by an earlier
                # connection survives: close it and open ours fresh.
                if attempt == CLAIM_ATTEMPTS:
                    raise
                logger.debug("Session already open, closing it")
                self._tx_no_data(Operations.CloseSession, [])
