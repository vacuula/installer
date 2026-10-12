from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from vacuula_installer.core.firmware_updater import FirmwareAsset, assets_for_gen
from vacuula_installer.i18n import Translator
from vacuula_installer.widgets.clickable_label import ClickableLabel

# Steps FirmwareUpdater.installStepChanged can send, each mapped to a
# translation key below. "sending" is the only one with real percent
# progress; the rest show as an indeterminate (busy) bar.
INSTALL_STEP_KEYS = {
    "reset_network": "firmware.install.step.reset_network",
    "waiting": "firmware.install.step.waiting",
    "handshake": "firmware.install.step.handshake",
    "sending": "firmware.install.step.sending",
    "awaiting_ack": "firmware.install.step.awaiting_ack",
    "verifying": "firmware.install.step.verifying",
    "rebooting": "firmware.install.step.rebooting",
    "done": "firmware.install.step.done",
}


class _FirmwareOption(QWidget):
    """One selectable row: a radio button, version title, and description."""

    def __init__(
        self,
        key: str,
        asset: FirmwareAsset,
        translator: Translator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.key = key
        self._asset = asset
        self._translator = translator

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        self.radio = QRadioButton(self)
        self.radio.setObjectName("firmwareOptionRadio")

        self._desc_label = QLabel(self)
        self._desc_label.setObjectName("serversearchDetailLabel")
        self._desc_label.setWordWrap(True)
        self._desc_label.setContentsMargins(
            24, 0, 0, 0
        )  # line up under the radio's text
        self._desc_label.setCursor(Qt.CursorShape.PointingHandCursor)

        layout.addWidget(self.radio)
        layout.addWidget(self._desc_label)

        self._retranslate()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.radio.setChecked(True)
        super().mouseReleaseEvent(event)

    def _retranslate(self) -> None:
        title = self._translator.tr("firmware.version", version=self._asset.version)
        if self._asset.recommended:
            title += " " + self._translator.tr("firmware.recommended")
        self.radio.setText(title)
        self._desc_label.setText(self._translator.tr(self._asset.description_key))


class FirmwareUpdateScreen(QWidget):
    """Emits :attr:`downloadRequested` when the user picks a version and
    hits download, :attr:`installRequested` once they choose to install
    the file that was just downloaded, and :attr:`factoryResetRequested`
    when they ask for the (not yet implemented) automated factory reset.
    """

    downloadRequested = Signal(str)  # firmware key
    installRequested = Signal(str)  # firmware key

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._gen: str | None = None
        self._options: list[_FirmwareOption] = []
        self._selected_key: str | None = None
        self._downloaded_key: str | None = None
        self._progress_kind: str | None = (
            None  # "download" | "install", while on the progress page
        )
        self._retry_kind: str | None = None  # which phase a retry should re-attempt

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 40, 20, 26)
        outer.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        outer.setSpacing(16)

        self._title = QLabel(self)
        self._title.setObjectName("serversearchTitleLabel")
        self._title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._title.setWordWrap(True)
        outer.addWidget(self._title)

        self._subtitle = QLabel(self)
        self._subtitle.setObjectName("serversearchBodyLabel")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._subtitle.setWordWrap(True)
        outer.addWidget(self._subtitle)

        # -- picker page
        self._options_box = QWidget(self)
        self._options_layout = QVBoxLayout(self._options_box)
        self._options_layout.setContentsMargins(0, 0, 0, 0)
        self._options_layout.setSpacing(8)
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        outer.addWidget(self._options_box)

        self._factory_reset_ack_row = QWidget(self)
        ack_row_layout = QHBoxLayout(self._factory_reset_ack_row)
        ack_row_layout.setContentsMargins(0, 0, 0, 0)
        ack_row_layout.setSpacing(8)
        ack_row_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._factory_reset_ack_checkbox = QCheckBox(self._factory_reset_ack_row)
        self._factory_reset_ack_checkbox.setObjectName("acknowledgeCheckBox")
        self._factory_reset_ack_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self._factory_reset_ack_checkbox.toggled.connect(self._update_download_enabled)

        self._factory_reset_ack_caption = ClickableLabel(self._factory_reset_ack_row)
        self._factory_reset_ack_caption.setObjectName("serversearchDetailLabel")
        self._factory_reset_ack_caption.setWordWrap(True)
        self._factory_reset_ack_caption.setCursor(Qt.CursorShape.PointingHandCursor)
        self._factory_reset_ack_caption.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )
        self._factory_reset_ack_caption.clicked.connect(
            self._factory_reset_ack_checkbox.toggle
        )

        ack_row_layout.addWidget(
            self._factory_reset_ack_checkbox, alignment=Qt.AlignmentFlag.AlignTop
        )
        ack_row_layout.addWidget(self._factory_reset_ack_caption, 1)
        outer.addWidget(self._factory_reset_ack_row)

        self._factory_reset_link_button = QPushButton(self)
        self._factory_reset_link_button.setObjectName("linkButton")
        self._factory_reset_link_button.setFlat(True)
        self._factory_reset_link_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._factory_reset_link_button.clicked.connect(
            lambda: self._show_page("factory_reset")
        )
        outer.addWidget(
            self._factory_reset_link_button, alignment=Qt.AlignmentFlag.AlignHCenter
        )

        self._download_button = QPushButton(self)
        self._download_button.setObjectName("continueButton")
        self._download_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._download_button.setEnabled(False)
        self._download_button.clicked.connect(self._on_download_clicked)
        outer.addWidget(self._download_button, alignment=Qt.AlignmentFlag.AlignHCenter)

        # -- factory reset page
        self._factory_reset_explanation = QLabel(self)
        self._factory_reset_explanation.setObjectName("serversearchBodyLabel")
        self._factory_reset_explanation.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._factory_reset_explanation.setWordWrap(True)
        outer.addWidget(self._factory_reset_explanation)

        self._factory_reset_instructions = QLabel(self)
        self._factory_reset_instructions.setObjectName("serversearchDetailLabel")
        self._factory_reset_instructions.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._factory_reset_instructions.setWordWrap(True)
        self._factory_reset_instructions.setOpenExternalLinks(True)
        outer.addWidget(self._factory_reset_instructions)

        self._factory_reset_back_button = QPushButton(self)
        self._factory_reset_back_button.setObjectName("linkButton")
        self._factory_reset_back_button.setFlat(True)
        self._factory_reset_back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._factory_reset_back_button.clicked.connect(lambda: self._show_page("pick"))
        outer.addWidget(
            self._factory_reset_back_button, alignment=Qt.AlignmentFlag.AlignHCenter
        )

        # it's one less set of spinner/bar/label to keep in sync.
        self._progress_row = QWidget(self)
        progress_layout = QVBoxLayout(self._progress_row)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(8)

        self._progress_status = QLabel(self._progress_row)
        self._progress_status.setWordWrap(True)
        self._progress_status.setFixedWidth(350)  # matches the bar below it
        self._progress_status.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._progress_status.setObjectName("serversearchDetailLabel")

        self._progress_bar = QProgressBar(self._progress_row)
        self._progress_bar.setFixedWidth(350)
        self._progress_bar.setFixedHeight(24)
        self._progress_bar.setTextVisible(True)

        progress_layout.addWidget(
            self._progress_status, alignment=Qt.AlignmentFlag.AlignHCenter
        )
        progress_layout.addWidget(
            self._progress_bar, alignment=Qt.AlignmentFlag.AlignHCenter
        )
        outer.addWidget(self._progress_row)

        # -- error row
        self._error_label = QLabel(self)
        self._error_label.setObjectName("serversearchDetailLabel")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._error_label.setWordWrap(True)
        outer.addWidget(self._error_label)

        self._retry_button = QPushButton(self)
        self._retry_button.setObjectName("continueButton")
        self._retry_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._retry_button.clicked.connect(self._on_retry_clicked)
        outer.addWidget(self._retry_button, alignment=Qt.AlignmentFlag.AlignHCenter)

        # -- install prompt page (shown once the download is done)
        self._install_button = QPushButton(self)
        self._install_button.setObjectName("continueButton")
        self._install_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._install_button.clicked.connect(self._on_install_clicked)
        outer.addWidget(self._install_button, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._translator.languageChanged.connect(self._retranslate)
        self._retranslate()
        self._show_page("pick")

    def set_generation(self, gen: str) -> None:
        """`gen` is "gen3" or "gen4" -- only firmwares for that generation
        are offered. Call this before showing the screen."""
        self._gen = gen
        self._rebuild_options()
        self.reset()

    def reset(self) -> None:
        self._downloaded_key = None
        self._progress_kind = None
        self._retry_kind = None
        self._progress_bar.setValue(0)
        self._progress_bar.setRange(0, 100)
        self._button_group.setExclusive(False)
        for option in self._options:
            option.radio.setChecked(False)
        self._button_group.setExclusive(True)
        self._selected_key = None
        self._factory_reset_ack_checkbox.setChecked(False)
        self._update_download_enabled()
        self._show_page("pick")

    def _rebuild_options(self) -> None:
        for option in self._options:
            self._button_group.removeButton(option.radio)
            self._options_layout.removeWidget(option)
            option.deleteLater()
        self._options.clear()

        if self._gen is None:
            return
        for key, asset in assets_for_gen(self._gen):
            option = _FirmwareOption(key, asset, self._translator, self._options_box)
            option.radio.toggled.connect(
                lambda checked, k=key: self._on_option_toggled(k, checked)
            )
            self._button_group.addButton(option.radio)
            self._options_layout.addWidget(option)
            self._options.append(option)

    def _on_option_toggled(self, key: str, checked: bool) -> None:
        if checked:
            self._selected_key = key
            self._update_download_enabled()

    def _update_download_enabled(self) -> None:
        ack_ok = (
            self._factory_reset_ack_checkbox.isChecked()
            if self._gen == "gen3"
            else True
        )
        self._download_button.setEnabled(self._selected_key is not None and ack_ok)

    def set_download_progress(self, key: str, percent: int) -> None:
        if self._progress_kind != "download" or key != self._selected_key:
            return
        self._set_bar_percent(percent)

    def set_download_finished(self, key: str) -> None:
        if key != self._selected_key:
            return
        self._downloaded_key = key
        self._show_page("install_prompt")

    def set_download_failed(self, key: str, reason: str) -> None:
        if key != self._selected_key:
            return
        self._error_label.setText(
            self._translator.tr("firmware.download_failed", reason=reason)
        )
        self._retry_kind = "download"
        self._show_page("error")

    def set_install_step(self, key: str, step: str) -> None:
        if self._progress_kind != "install" or key != self._downloaded_key:
            return
        step_key = INSTALL_STEP_KEYS.get(step, "firmware.install.step.unknown")
        self._progress_status.setText(self._translator.tr(step_key))
        self._progress_status.adjustSize()
        if step == "sending":
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(0)
        else:
            self._progress_bar.setRange(0, 0)

    def set_install_progress(self, key: str, percent: int) -> None:
        if self._progress_kind != "install" or key != self._downloaded_key:
            return
        self._set_bar_percent(percent)

    def set_install_failed(self, key: str, reason: str) -> None:
        if key != self._downloaded_key:
            return
        self._error_label.setText(
            self._translator.tr("firmware.install_failed", reason=reason)
        )
        self._retry_kind = "install"
        self._show_page("error")

    def set_install_finished(self, key: str) -> None:
        if key != self._downloaded_key:
            return
        self._progress_status.setText(
            self._translator.tr(f"firmware.install.step.done.{self._gen}")
        )
        self._progress_status.setFixedHeight(self._progress_status.heightForWidth(350))
        self.page = "done"  # temp hack thing to detect disconnectes
        self._progress_bar.hide()

    def _set_bar_percent(self, percent: int) -> None:
        if percent < 0:
            self._progress_bar.setRange(0, 0)  # indeterminate
        else:
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(percent)

    # -- user actions
    def _on_download_clicked(self) -> None:
        ack_ok = (
            self._factory_reset_ack_checkbox.isChecked()
            if self._gen == "gen3"
            else True
        )
        if self._selected_key is None or not ack_ok:
            return
        self._progress_kind = "download"
        self._progress_status.setText(self._translator.tr("firmware.downloading"))
        self._progress_status.adjustSize()
        self._progress_bar.setValue(0)
        self._progress_bar.setRange(0, 100)
        self._show_page("progress")
        self.downloadRequested.emit(self._selected_key)

    def _on_install_clicked(self) -> None:
        if self._downloaded_key is None:
            return
        self._progress_kind = "install"
        self._progress_status.setText(
            self._translator.tr("firmware.install.step.starting")
        )
        self._progress_status.adjustSize()
        self._progress_bar.setRange(
            0, 0
        )  # indeterminate until "sending" reports real percent
        self._show_page("progress")
        self.installRequested.emit(self._downloaded_key)

    def _on_retry_clicked(self) -> None:
        if self._retry_kind == "install":
            self._show_page("install_prompt")
        else:
            self._show_page("pick")

    # -- page switching

    def _show_page(self, page: str) -> None:
        self.page = page
        self._options_box.setVisible(page == "pick")
        self._factory_reset_ack_row.setVisible(page == "pick" and self._gen == "gen3")
        self._factory_reset_link_button.setVisible(
            page == "pick" and self._gen == "gen3"
        )
        self._download_button.setVisible(page == "pick")

        self._factory_reset_explanation.setVisible(page == "factory_reset")
        self._factory_reset_instructions.setVisible(page == "factory_reset")
        self._factory_reset_back_button.setVisible(page == "factory_reset")

        self._progress_row.setVisible(page == "progress")
        self._error_label.setVisible(page == "error")
        self._retry_button.setVisible(page == "error")
        self._install_button.setVisible(page == "install_prompt")

    def _retranslate(self) -> None:
        self._title.setText(self._translator.tr("firmware.title"))
        self._subtitle.setText(self._translator.tr("firmware.subtitle"))
        self._factory_reset_ack_caption.setText(
            self._translator.tr("firmware.gen3.factory_reset_ack")
        )
        self._factory_reset_link_button.setText(
            self._translator.tr("firmware.gen3.factory_reset_link")
        )
        self._download_button.setText(self._translator.tr("firmware.download"))
        self._retry_button.setText(self._translator.tr("firmware.try_again"))
        self._install_button.setText(self._translator.tr("firmware.install"))

        self._factory_reset_explanation.setText(
            self._translator.tr("firmware.gen3.factory_reset.explanation")
        )
        self._factory_reset_instructions.setText(
            self._translator.tr("firmware.gen3.factory_reset.instructions")
        )
        self._factory_reset_back_button.setText(
            self._translator.tr("firmware.gen3.factory_reset.back")
        )

        for option in self._options:
            option._retranslate()
