from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from vacuula_installer.constants import (
    APP_ID,
    LOGO_SVG,
    ORG_NAME,
    WINDOWS_APP_USER_MODEL_ID,
)

logger = logging.getLogger(__name__)


_ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def prepare_app_identity() -> None:
    """Call before QApplication is constructed."""
    QCoreApplication.setApplicationName(APP_ID)
    # Wayland app_id / X11 hint used to match the .desktop file.
    QCoreApplication.setOrganizationName(ORG_NAME)
    QGuiApplication.setDesktopFileName(APP_ID)

    if sys.platform == "win32":
        _set_windows_app_user_model_id()


def apply_app_icon(app: QGuiApplication) -> QIcon:
    icon = build_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    else:
        logger.warning(f"Could not load app icon from {LOGO_SVG}")
    return icon


def build_app_icon() -> QIcon:
    renderer = QSvgRenderer(str(LOGO_SVG))
    icon = QIcon()
    if not renderer.isValid():
        return icon
    for size in _ICON_SIZES:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(pixmap)
    return icon


def _set_windows_app_user_model_id() -> None:
    try:
        import ctypes

        # ctypes.windll only exists on Windows; the checker targets Linux too.
        # ty: ignore[unresolved-attribute]
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            WINDOWS_APP_USER_MODEL_ID
        )
    except (AttributeError, OSError):
        pass
