from __future__ import annotations

import re

from vacuula_installer._build_version import APP_VERSION

# TODO: was this really required? why did i do it as a list again?
# min server version -> feature required
FEATURE_VERSIONS = {
    "1.1.0-b1": "gen3 port and nip fix",
    "1.1.0-b3": "timezone changes",
}

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-b(\d+))?$")


def parse_version(v: str) -> tuple:
    m = _VERSION_RE.match(v.strip())
    if not m:
        return (-999, -999, -999, float("-inf"))
    major, minor, patch, beta = m.groups()
    # real version comes before beta
    beta_rank = int(beta) if beta is not None else float("inf")
    return (int(major), int(minor), int(patch), beta_rank)


def validate_version(min_installer_version: str, server_version: str) -> tuple[bool, str]:
    combined = APP_VERSION + min_installer_version + server_version
    if "dev" in combined or "dirty" in combined:
        return True, ""

    inst = parse_version(APP_VERSION)
    min_inst = parse_version(min_installer_version)
    srv = parse_version(server_version)

    # check if installer is too old for the server
    if inst < min_inst:
        return False, f"installer version {APP_VERSION} is too old for server version {server_version}"
    
    # check if server is too old for the installer
    missing = [
        feature
        for min_ver, feature in FEATURE_VERSIONS.items()
        if srv < parse_version(min_ver)
    ]

    if missing:
        return False, ", ".join(missing)
    return True, ""