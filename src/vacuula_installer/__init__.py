"""Entry point for the Vacuula robot-vacuum setup wizard."""

from __future__ import annotations

import logging
import sys
import threading

from PySide6.QtWidgets import QApplication

from vacuula_installer.app_identity import apply_app_icon, prepare_app_identity
from vacuula_installer.constants import DEFAULT_LANGUAGE, LOCALES_DIR, APP_VERSION
from vacuula_installer.i18n import Translator
from vacuula_installer.library_path import restore_library_path
from vacuula_installer.logger import setup_logging
from vacuula_installer.main_window import MainWindow
from vacuula_installer.theme import apply_app_palette

prepare_app_identity()
setup_logging()
logger = logging.getLogger(__name__)

sys.excepthook = lambda t, e, tb: logger.critical("Uncaught exception", exc_info=(t, e, tb))
threading.excepthook = lambda a: logger.critical("Uncaught exception in thread", exc_info=(a.exc_type, a.exc_value, a.exc_traceback))

def main() -> int:
    logger.info("Starting Vacuula Installer v%s", APP_VERSION)

    app = QApplication(sys.argv)
    apply_app_palette(app)
    apply_app_icon(app)

    translator = Translator(LOCALES_DIR, default_language=DEFAULT_LANGUAGE)

    window = MainWindow(translator)
    window.show()

    # Restore LD_LIBRARY_PATH, otherwise clickable links might not work
    restore_library_path()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
