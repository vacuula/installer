"""An attempt to keep variables declared at one place"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

# --------------------------------------------------------------------------
# Application metadata
# --------------------------------------------------------------------------
from ._build_version import APP_VERSION

# Must equal the .desktop file's basename (without ".desktop") on Linux.
APP_ID = "VacuulaInstaller"
ORG_NAME = "Vacuula"
# Windows taskbar grouping id: "Company.Product" style, any stable string.
WINDOWS_APP_USER_MODEL_ID = "Vacuula.Installer"

# --------------------------------------------------------------------------
# Vacuula defaults
# --------------------------------------------------------------------------
GEN3_DEFAULT_PORT = 335

# --------------------------------------------------------------------------
# Filesystem layout
# --------------------------------------------------------------------------
APP_ROOT: Path = Path(__file__).resolve().parent.parent
ASSETS_DIR: Path = APP_ROOT / "assets"
SCRIPTS_DIR: Path = ASSETS_DIR / "scripts"
LOCALES_DIR: Path = APP_ROOT / "locales"
FLAGS_DIR: Path = ASSETS_DIR / "flags"

LOGO_SVG: Path = ASSETS_DIR / "logo.svg"
CONNECT_SVG: Path = ASSETS_DIR / "connect_instr.svg"
GEN23_FACTORY_RESET_SVG: Path = ASSETS_DIR / "gen23_factory_reset.svg"

COMPUTER_SVG: Path = ASSETS_DIR / "computer.svg"
SERVER_SVG: Path = ASSETS_DIR / "server.svg"

# Icons
GITHUB_SVG: Path = ASSETS_DIR / "github.svg"
DISCORD_SVG: Path = ASSETS_DIR / "discord.svg"
KOFI_SVG: Path = ASSETS_DIR / "kofi.svg"
BUYMEACOFFEE_SVG: Path = ASSETS_DIR / "buymeacoffee.svg"

# DLL
DLL_DIR: Path = ASSETS_DIR / "dll"
LIBUSB_DLL: Path = DLL_DIR / "libusb-1.0.dll"

# --------------------------------------------------------------------------
# Window & layout geometry
# --------------------------------------------------------------------------
WINDOW_SIZE: tuple[int, int] = (1040, 640) #I think os will scale this and not take it litteraly
LEFT_PANEL_RATIO: float = 0.38  # fraction of the window width

LOGO_SIZE_CENTERED: int = 654   # logo size during the intro splash
LOGO_SIZE_DOCKED: int = 300     # logo size once settled in the left panel

BACK_BUTTON_SIZE: int = 36
BACK_BUTTON_MARGIN: int = 16

WIREFRAME_SIZE: tuple[int, int] = (400, 225)

# --------------------------------------------------------------------------
# Animation timings (ms)
# --------------------------------------------------------------------------
INTRO_DELAY_MS: int = 500
LOGO_MOVE_DURATION_MS: int = 1000
PANEL_FADE_DURATION_MS: int = 450
SCREEN_FADE_OUT_MS: int = 200
SCREEN_FADE_IN_MS: int = 380

NETWORK_POLLING_DELAY_MS: int = 5000
USB_POLLING_DELAY_MS: int = 2345

M_DNS_SERVICE_TYPE: str = "_vacuula._tcp.local."


class LanguageMeta(NamedTuple):
    # Native name is used for flag hover in picker
    flag_svg: Path
    native_name: str


# Every UI language MUST have both an entry here *and* a matching
# ``locales/<code>.json`` catalog. 
# Sorted by language code by program
LANGUAGES: dict[str, LanguageMeta] = {
    "de": LanguageMeta(flag_svg=FLAGS_DIR / "de.svg", native_name="Deutsch"),
    "sv": LanguageMeta(flag_svg=FLAGS_DIR / "se.svg", native_name="Svenska"),
    "en": LanguageMeta(flag_svg=FLAGS_DIR / "gb.svg", native_name="English"),
    "nl": LanguageMeta(flag_svg=FLAGS_DIR / "nl.svg", native_name="Nederlands"),
    "pt": LanguageMeta(flag_svg=FLAGS_DIR / "pt.svg", native_name="Português"),
    "fr": LanguageMeta(flag_svg=FLAGS_DIR / "fr.svg", native_name="Français"),
    "cs": LanguageMeta(flag_svg=FLAGS_DIR / "cz.svg", native_name="Čeština"),

}
DEFAULT_LANGUAGE = "en" #might be replaced with system locale? I dunno how to fetch safely crossplatform

# Backgroundflair, maybe do languages actually translated to?
FLAIR_WELCOME_WORDS: list[str] = [
    "Welcome", "Willkommen", "Bienvenue", "Bienvenida", "Benvenuto",
    "Bem-vindo", "いらっしゃいませ", "Välkommen", "Velkommen", "Tervetuloa",
]
