"""The data the wizard accumulates as the user moves through its screens.
Data used by installers, presense of data by main windows for skipping screens (TODO)
"""
from __future__ import annotations

from dataclasses import dataclass

import usb.core  # type: ignore[reportMissingTypeStubs]


@dataclass
class SessionData:
    server_ip: str | None = None
    server_ip_manual: bool = False
    server_certificate: str | None = None

    # TODO: clean this up later as well, not really the cleanesy way rn
    timezone : str | None = None
    vacuula_port: int | None = None
    gen3_port: int | None = None
    gen4_port: int | None = None

    robot_serial_nbr: str | None = None
    robot_model_display_name: str | None = None
    robot_usb_device: usb.core.Device | None = None
    robot_serial_device: str | None = None #TODO maybe needs to be SysFS?
    firmware_version: str | None = None # TODO

    wifi_ssid: str | None = None
    wifi_pass: str | None = None

    install_done: bool = False

    # Some dev only goodies, for dev only screen (TODO)
    enable_ssh: bool = False #also means install dropbear
    ssh_pubkey: str | None = None
    ssh_disable_pw: bool = False
    set_root_pass: str | None = None #none means no