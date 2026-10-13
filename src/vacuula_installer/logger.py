import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QFileDialog, QMessageBox


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def get_log_file_path() -> Path:
    log_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "VacuulaInstaller.log"


def setup_logging() -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers.
    if root_logger.handlers:
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not is_frozen():
        console = logging.StreamHandler(sys.stderr)
        console.setLevel(logging.DEBUG)
        console.setFormatter(formatter)
        root_logger.addHandler(console)

    log_file = get_log_file_path()
    handler = RotatingFileHandler(
        log_file,
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )

    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


def download_logs() -> None:
    """Download logs to a user-specified location."""

    log_file = get_log_file_path()

    # initial release use default message bow and stuff
    if not log_file.exists():
        QMessageBox.warning(None, "Download Logs", "Log file does not exist.")
        return

    save_path, _ = QFileDialog.getSaveFileName(
        None,
        "Save Logs",
        str(Path.home() / "VacuulaInstaller.log"),
        "Log Files (*.log);;All Files (*)",
    )

    if save_path:
        try:
            with open(log_file, "rb") as src, open(save_path, "wb") as dst:
                dst.write(src.read())
            QMessageBox.information(None, "Download Logs", f"Logs saved to {save_path}.")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(None, "Download Logs", f"Failed to save logs: {e}")
