# app.spec
#
# Shared PyInstaller build spec for Windows, macOS and Linux. Invoke the
# same way on every platform:
#     pyinstaller --noconfirm --clean app.spec
# Platform differences (onefile exe / onedir for AppImage / .app bundle)
# and the SVG-to-native-icon conversion are handled below via sys.platform.
#

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

tz_datas = collect_data_files("tzdata")
hiddenimports = collect_submodules("tzdata")
if sys.platform == "win32":
    hiddenimports += collect_submodules("comtypes.gen")

APP_NAME = "VacuulaInstaller"
ENTRY_POINT = "src/vacuula_installer/__init__.py"
SVG_ICON = Path("src/assets/logo.svg")
BUILD_DIR = Path("build_icons")

# ---------------------------------------------------------------------------
# Bundled data. Plain tuples here avoid the --add-data ':' vs ';' split
# between Windows and POSIX entirely.
# ---------------------------------------------------------------------------
# Sources come from the src/ layout; the destinations match what
# constants.APP_ROOT (the package's parent dir) expects at runtime.
datas = [
    ("src/locales", "locales"),
    ("src/assets", "assets"),

    # packages
    *tz_datas
]

# ---------------------------------------------------------------------------
# Icon handling. The project keeps a single SVG source
# (src/assets/logo.svg).
# Windows/macOS need it converted to their native icon container format;
# Linux has no equivalent for a bare executable, so the AppImage workflow
# step uses the SVG directly instead of anything built here.
# ---------------------------------------------------------------------------
def _rasterize_svg_to_png(svg_path: Path, size: int, out_path: Path) -> None:
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    _app = QGuiApplication.instance() or QGuiApplication([])
    renderer = QSvgRenderer(str(svg_path))
    image = QImage(QSize(size, size), QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(out_path), "PNG")


def _build_windows_icon(svg_path: Path) -> str:
    from PIL import Image

    base_png = BUILD_DIR / "icon_512.png"
    _rasterize_svg_to_png(svg_path, 512, base_png)
    ico_path = BUILD_DIR / "icon.ico"
    Image.open(base_png).save(
        ico_path, sizes=[(16, 16), (32, 32), (48, 48), (128, 128), (256, 256)]
    )
    return str(ico_path)


def _build_macos_icon(svg_path: Path) -> str:
    import subprocess

    iconset = BUILD_DIR / "icon.iconset"
    # Apple's required filename/size pairs for a complete .iconset.
    slots = {
        "icon_16x16.png": 16, "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32, "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128, "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256, "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512, "icon_512x512@2x.png": 1024,
    }
    for filename, size in slots.items():
        _rasterize_svg_to_png(svg_path, size, iconset / filename)
    icns_path = BUILD_DIR / "icon.icns"
    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(icns_path)], check=True
    )
    return str(icns_path)


def app_icon() -> str | None:
    if sys.platform == "win32":
        return _build_windows_icon(SVG_ICON)
    if sys.platform == "darwin":
        return _build_macos_icon(SVG_ICON)
    return None  # Linux: the AppImage step points at the SVG directly


icon_path = app_icon()

# ---------------------------------------------------------------------------
# Analysis: identical on every platform.
# ---------------------------------------------------------------------------
a = Analysis(
    [ENTRY_POINT],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

# ---------------------------------------------------------------------------
# Windows: single-file exe. Linux/macOS: onedir - macOS wraps it in a
# .app bundle below; Linux onedir is what the AppImage workflow step
# consumes directly.
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name=APP_NAME,
        console=False,
        icon=icon_path,
    )

else:
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name=APP_NAME,
        console=False,
        icon=icon_path,
    )
    coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME)

    if sys.platform == "darwin":
        app = BUNDLE(
            coll,
            name=f"{APP_NAME}.app",
            icon=icon_path,
            bundle_identifier=f"com.example.{APP_NAME.lower()}",  # <-- set your real identifier
        )
