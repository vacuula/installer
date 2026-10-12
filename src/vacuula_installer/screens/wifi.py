"""A page for adding wifi credentials

Includes an overengineered spec-compliance with wifi SSID:s

TODO: A wifi core class that attempts to use the original robot selfdetection methods:
    gen 3: connect to its own wifi, get wifis it can see ongoing: gen23_prewifi_fix

    - The function should silently fail without disrupting user or flow if computer (this app) does not
    have wifi or bluetooth
    - But if it succeedes replace SSID field with a selection menu of what the robot sees, preferably elegantly
    filtering based on whats (pententially) already typed

"""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from vacuula_installer.i18n import Translator
from vacuula_installer.widgets.spinner import SpinnerWidget
from vacuula_installer.widgets.ssid_input import SsidInput
from vacuula_installer.widgets.width_tracking_label import WidthTrackingLabel


# TODO: the wifi screen maybe should be split one for gen23 and one for gen4, but meh for now
class WifiScreen(QWidget):
    """Emits :attr:`wifiAdded` with SSID, password"""

    _BARS: ClassVar[dict[int, str]] = {1: "▂", 2: "▂▄", 3: "▂▄▆"}

    wifiAdded = Signal(str, str)
    prewifiConnectedClicked = Signal()
    rescanRequested = Signal()

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._title_width = 0
        self._wifi_alternatives = [""]
        self._gen23_manual = False
        self._gen23_auto_manual = False  # switched to manual by us, not the user
        self._gen23_status_key: str | None = None
        self._gen23_loading = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 40, 20, 26)
        outer.setSpacing(18)
        self._central_stack = QStackedLayout()
        outer.addLayout(self._central_stack, 1)

        self._wifipage = self._build_wifi_page()
        self._gen23_wifi_page = self._build_gen23_wifi_page()
        self._gen23_prewifi_page = self._build_gen23_prewifi_page()
        self._central_stack.addWidget(self._wifipage)
        self._central_stack.addWidget(self._gen23_wifi_page)
        self._central_stack.addWidget(self._gen23_prewifi_page)
        self._translator.languageChanged.connect(self._retranslate)

        self._translator.languageChanged.connect(self._retranslate)
        self._wifi_title_labelGen23.widthChanged.connect(self._apply_label_margins)
        self._retranslate()

    def _build_gen23_prewifi_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.setSpacing(0)

        self._prewifi_title_labelGen23 = WidthTrackingLabel(page)
        self._prewifi_title_labelGen23.setObjectName("serversearchTitleLabel")
        self._prewifi_title_labelGen23.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._prewifi_title_labelGen23.setWordWrap(True)

        self._prewifi_conn_explGen23 = QLabel(page)
        self._prewifi_conn_explGen23.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._prewifi_conn_explGen23.setWordWrap(True)
        self._prewifi_conn_explGen23.setObjectName("wifiExplanationLabel")

        self._prewifi_disclaimerGen23 = QLabel(page)
        self._prewifi_disclaimerGen23.setObjectName("serversearchDetailLabel")
        self._prewifi_disclaimerGen23.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._prewifi_disclaimerGen23.setWordWrap(True)

        layout.addWidget(self._prewifi_title_labelGen23)
        layout.addSpacing(24)
        layout.addWidget(self._prewifi_conn_explGen23)
        layout.addSpacing(24)
        layout.addWidget(self._prewifi_disclaimerGen23)
        layout.addSpacing(30)

        self._prewifi_connected_button = QPushButton(page)
        self._prewifi_connected_button.setObjectName("continueButton")
        self._prewifi_connected_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._prewifi_connected_button.clicked.connect(self.prewifiConnectedClicked)
        layout.addWidget(self._prewifi_connected_button, alignment=Qt.AlignmentFlag.AlignHCenter)

        return page

    def _build_gen23_wifi_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.setSpacing(0)

        self._wifi_title_labelGen23 = WidthTrackingLabel(page)
        self._wifi_title_labelGen23.setObjectName("serversearchTitleLabel")
        self._wifi_title_labelGen23.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._wifi_title_labelGen23.setWordWrap(True)

        self._wifi_conn_explGen23 = QLabel(page)
        self._wifi_conn_explGen23.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._wifi_conn_explGen23.setWordWrap(True)
        self._wifi_conn_explGen23.setObjectName("wifiExplanationLabel")

        self._wifi_status_rowGen23 = QWidget(page)
        self._wifi_status_rowGen23.setFixedHeight(40)
        status_row = QHBoxLayout(self._wifi_status_rowGen23)
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(10)
        status_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._wifi_spinnerGen23 = SpinnerWidget(self._wifi_status_rowGen23, 20)
        self._wifi_spinnerGen23.hide()

        self._wifi_statusGen23 = QLabel(self._wifi_status_rowGen23)
        self._wifi_statusGen23.setObjectName("serversearchDetailLabel")
        self._wifi_statusGen23.setMaximumWidth(320)
        self._wifi_statusGen23.hide()

        status_row.addWidget(self._wifi_spinnerGen23)
        status_row.addWidget(self._wifi_statusGen23)

        self._ssid_field_labelGen23 = QLabel(page)
        self._ssid_field_labelGen23.setObjectName("serversearchBodyLabel")
        self._ssid_field_labelGen23.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._wifi_combo_boxGen23 = QComboBox(page)
        self._wifi_combo_boxGen23.setObjectName("wifiInput")
        self._wifi_combo_boxGen23.currentIndexChanged.connect(self._update_gen23_continue_enabled)

        self._ssid_inputGen23 = SsidInput(page)
        self._ssid_inputGen23.textChanged.connect(self._update_gen23_continue_enabled)
        self._ssid_inputGen23.returnPressed.connect(self._ssid_inputGen23.focusNextChild)

        self._wifi_combo_boxGen23.setFixedWidth(350)
        self._ssid_inputGen23.setFixedWidth(350)
        self._wifi_combo_boxGen23.setFixedHeight(45)
        self._ssid_inputGen23.setFixedHeight(45)

        self._ssid_toggleGen23 = QPushButton(page)
        self._ssid_toggleGen23.setObjectName("linkButton")
        self._ssid_toggleGen23.setFlat(True)
        self._ssid_toggleGen23.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ssid_toggleGen23.clicked.connect(self._on_gen23_toggle_clicked)

        self._rescan_buttonGen23 = QPushButton(page)
        self._rescan_buttonGen23.setObjectName("linkButton")
        self._rescan_buttonGen23.setFlat(True)
        self._rescan_buttonGen23.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rescan_buttonGen23.clicked.connect(self.rescanRequested)
        self._rescan_buttonGen23.hide()  # only shown when not scanning

        link_row = QHBoxLayout()
        link_row.setContentsMargins(0, 8, 0, 0)
        link_row.setSpacing(16)
        link_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        link_row.addWidget(self._ssid_toggleGen23)
        link_row.addWidget(self._rescan_buttonGen23)

        self._password_field_labelGen23 = QLabel(page)
        self._password_field_labelGen23.setObjectName("serversearchBodyLabel")
        self._password_field_labelGen23.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._password_inputGen23 = QLineEdit(page)
        self._password_inputGen23.setObjectName("wifiInput")
        self._password_inputGen23.setFixedWidth(350)
        self._password_inputGen23.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self._password_inputGen23.returnPressed.connect(self._handle_wifi_continue_clicked)

        self._wifi_disclaimerGen23 = QLabel(page)
        self._wifi_disclaimerGen23.setObjectName("serversearchDetailLabel")
        self._wifi_disclaimerGen23.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._wifi_disclaimerGen23.setWordWrap(True)

        self._wifi_continue_buttonGen23 = QPushButton(page)
        self._wifi_continue_buttonGen23.setObjectName("continueButton")
        self._wifi_continue_buttonGen23.setEnabled(True)
        self._wifi_continue_buttonGen23.setCursor(Qt.CursorShape.PointingHandCursor)
        self._wifi_continue_buttonGen23.clicked.connect(self._handle_wifi_continue_clicked)

        layout.addWidget(self._wifi_title_labelGen23)
        layout.addSpacing(24)
        layout.addWidget(self._wifi_conn_explGen23)
        layout.addSpacing(12)
        layout.addWidget(self._wifi_status_rowGen23)
        layout.addSpacing(6)
        layout.addWidget(self._ssid_field_labelGen23)
        layout.addSpacing(2)
        layout.addWidget(self._wifi_combo_boxGen23, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._ssid_inputGen23, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addLayout(link_row)
        layout.addSpacing(8)
        layout.addWidget(self._password_field_labelGen23)
        layout.addSpacing(2)
        layout.addWidget(self._password_inputGen23, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(24)
        layout.addWidget(self._wifi_disclaimerGen23)
        layout.addSpacing(30)
        layout.addWidget(self._wifi_continue_buttonGen23, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._set_gen23_manual(False)
        return page

    def _build_wifi_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        # We go manual with this one
        layout.setSpacing(0)

        self._wifi_title_label = WidthTrackingLabel(page)
        self._wifi_title_label.setObjectName("serversearchTitleLabel")
        self._wifi_title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._wifi_title_label.setWordWrap(True)

        self._wifi_conn_expl = QLabel(page)
        self._wifi_conn_expl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._wifi_conn_expl.setWordWrap(True)
        self._wifi_conn_expl.setObjectName("wifiExplanationLabel")

        self._ssid_field_label = QLabel(page)
        self._ssid_field_label.setObjectName("serversearchBodyLabel")
        self._ssid_field_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._ssid_input = SsidInput(page)
        self._ssid_input.setFixedWidth(350)
        self._ssid_input.textChanged.connect(self._update_wifi_continue_enabled)
        self._ssid_input.returnPressed.connect(self._ssid_input.focusNextChild)

        self._password_field_label = QLabel(page)
        self._password_field_label.setObjectName("serversearchBodyLabel")
        self._password_field_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._password_input = QLineEdit(page)
        self._password_input.setObjectName("wifiInput")
        self._password_input.setFixedWidth(350)
        self._password_input.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self._password_input.returnPressed.connect(self._handle_wifi_continue_clicked)

        self._wifi_disclaimer = QLabel(page)
        self._wifi_disclaimer.setObjectName("serversearchDetailLabel")
        self._wifi_disclaimer.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._wifi_disclaimer.setWordWrap(True)

        self._wifi_continue_button = QPushButton(page)
        self._wifi_continue_button.setObjectName("continueButton")
        self._wifi_continue_button.setEnabled(False)
        self._wifi_continue_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._wifi_continue_button.clicked.connect(self._handle_wifi_continue_clicked)

        layout.addWidget(self._wifi_title_label)
        layout.addSpacing(24)
        layout.addWidget(self._wifi_conn_expl)
        layout.addSpacing(24)
        layout.addWidget(self._ssid_field_label)
        layout.addSpacing(2)
        layout.addWidget(self._ssid_input, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(8)
        layout.addWidget(self._password_field_label)
        layout.addSpacing(2)
        layout.addWidget(self._password_input, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(24)
        layout.addWidget(self._wifi_disclaimer)
        layout.addSpacing(30)
        layout.addWidget(self._wifi_continue_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        return page

    def _apply_label_margins(self) -> None:
        available = self._wifi_title_labelGen23.width()
        if self._title_widthGen23 <= available:
            content_width = self._title_widthGen23
        else:
            # Title needs to wrap. Word wrap breaks on whole words, so its
            # widest wrapped line will be narrower than `available` - using
            # `available` here would let body/detail wrap wider than the
            # title actually renders, the opposite of the intent.
            content_width = self._wrapped_title_width(available)
        extra = max(0, available - content_width)
        left, right = extra // 2, extra - extra // 2
        for label in (self._wifi_title_labelGen23, self._wifi_combo_boxGen23):
            label.setContentsMargins(left, 0, right, 0)

    # Part of getting title textwidth as limit for other Qlabels
    def _wrapped_title_width(self, available: int) -> int:
        """Width of the title's widest line once wrapped to fit `available`."""
        fm = self._wifi_title_labelGen23.fontMetrics()
        rect = fm.boundingRect(
            QRect(0, 0, available, 32767), Qt.TextFlag.TextWordWrap, self._wifi_title_labelGen23.text()
        )
        return rect.width()

    # Just trigger on back navigation to fix valid input not allowing continue
    def wifi_revalidate_input(self) -> None:
        self._update_wifi_continue_enabled()

    def _update_wifi_continue_enabled(self) -> None:
        self._wifi_continue_button.setEnabled(self._ssid_input.is_valid())

    def _handle_wifi_continue_clicked(self) -> None:
        if self._central_stack.currentWidget() is self._gen23_wifi_page:
            if self._gen23_loading:  # if still loading, don't allow continue
                return
            if self._gen23_manual:
                if not self._ssid_inputGen23.is_valid():
                    return
                ssid = self._ssid_inputGen23.toPlainText()  # whitespace is valid SSID content
            else:
                ssid = self._wifi_combo_boxGen23.currentData()
                if not ssid:
                    return
            self.wifiAdded.emit(ssid, self._password_inputGen23.text())
            return
        if not self._ssid_input.is_valid():
            return
        ssid = self._ssid_input.toPlainText()  # not stripped -- whitespace is valid SSID content
        password = self._password_input.text()
        self._wifi_continue_button.setEnabled(False)
        self.wifiAdded.emit(ssid, password)

    # TODO continue button should work both verions

    def _set_gen23_status(self, key: str | None) -> None:
        self._gen23_status_key = key
        self._wifi_statusGen23.setText(self._translator.tr(key) if key else "")
        self._wifi_statusGen23.setVisible(key is not None)

    def _on_gen23_toggle_clicked(self) -> None:
        self._gen23_auto_manual = False
        self._set_gen23_manual(not self._gen23_manual)

    def _set_gen23_manual(self, manual: bool) -> None:
        self._gen23_manual = manual
        self._wifi_combo_boxGen23.setVisible(not manual)
        self._ssid_inputGen23.setVisible(manual)
        self._update_gen23_toggle_text()
        self._update_gen23_continue_enabled()

    def _update_gen23_toggle_text(self) -> None:
        key = "wifi.gen23.use_list" if self._gen23_manual else "wifi.gen23.use_manual"
        self._ssid_toggleGen23.setText(self._translator.tr(key))

    def _update_gen23_continue_enabled(self) -> None:
        if self._gen23_loading:
            self._wifi_continue_buttonGen23.setEnabled(False)
            return
        if self._gen23_manual:
            ok = self._ssid_inputGen23.is_valid()
        else:
            ok = bool(self._wifi_combo_boxGen23.currentData())
        self._wifi_continue_buttonGen23.setEnabled(ok)

    def set_gen23_wifi_loading(self, loading: bool) -> None:
        self._gen23_loading = loading
        if loading:
            self._wifi_spinnerGen23.start()
        else:
            self._wifi_spinnerGen23.stop()
        self._wifi_combo_boxGen23.setEnabled(not loading)
        self._rescan_buttonGen23.setVisible(not loading)
        if loading:
            self._wifi_combo_boxGen23.clear()
            self._set_gen23_status("wifi.gen23.loading")
        else:
            self._set_gen23_status(None)
        self._update_gen23_continue_enabled()

    def set_gen23_wifi_options(self, networks: list[dict]) -> None:
        """networks: [{"ssid": str, "strength": int}, ...]"""
        self.set_gen23_wifi_loading(False)

        # strongest first, one entry per SSID, skip hidden/empty names
        best: dict[str, int] = {}
        for n in networks:
            ssid = n.get("ssid") or ""
            if ssid:
                best[ssid] = max(best.get(ssid, 0), int(n.get("strength", 0)))

        # add items
        for ssid, strength in sorted(best.items(), key=lambda kv: -kv[1]):
            # visible text has the signal bars, userData keeps the raw SSID
            # Dont display bars for now, not in initial release, maybe back later
            self._wifi_combo_boxGen23.addItem(f"{ssid}", ssid)

        # no networks, force manual mode and disable the toggle until rescan
        if self._wifi_combo_boxGen23.count() == 0:
            self._gen23_auto_manual = True
            self._set_gen23_manual(True)
            self._ssid_toggleGen23.setDisabled(True)
            self._set_gen23_status("wifi.gen23.none_found")

        elif self._gen23_auto_manual:
            self._gen23_auto_manual = False
            self._set_gen23_manual(False)
        else:
            self._ssid_toggleGen23.setDisabled(False)
        self._update_gen23_continue_enabled()

    def set_gen23_wifi_failed(self) -> None:
        # scan failed, manual entry an rescan before any manual mode can be used
        self.set_gen23_wifi_loading(False)
        self._gen23_auto_manual = True
        self._set_gen23_manual(True)
        self._ssid_toggleGen23.setDisabled(True)
        self._set_gen23_status("wifi.gen23.scan_failed")

    def set_gen23_prewifi_page(self, mac: str) -> None:
        self._prewifi_conn_explGen23.setText(self._translator.tr("wifi.gen23.pre.explanation", mac=mac))
        self._central_stack.setCurrentWidget(self._gen23_prewifi_page)

    def set_prewifi_checking(self, checking: bool) -> None:
        self._prewifi_connected_button.setEnabled(not checking)

    def set_gen23_page(self) -> None:
        self._central_stack.setCurrentWidget(self._gen23_wifi_page)

    def _retranslate(self) -> None:
        self._wifi_title_label.setText(self._translator.tr("wifi.title"))
        self._ssid_field_label.setText(self._translator.tr("wifi.ssid.title"))
        self._wifi_continue_button.setText(self._translator.tr("wifi.button"))
        self._password_field_label.setText(self._translator.tr("wifi.pass.title"))
        self._wifi_disclaimer.setText(self._translator.tr("wifi.disclaimer"))
        self._wifi_conn_expl.setText(self._translator.tr("wifi.explanation"))

        self._wifi_continue_button.setText(self._translator.tr("wifi.button"))
        self._password_field_label.setText(self._translator.tr("wifi.pass.title"))
        self._wifi_disclaimer.setText(self._translator.tr("wifi.disclaimer"))
        self._wifi_conn_expl.setText(self._translator.tr("wifi.explanation"))

        self._wifi_title_labelGen23.setText(self._translator.tr("wifi.title"))
        self._wifi_conn_explGen23.setText(self._translator.tr("wifi.explanation"))
        self._ssid_field_labelGen23.setText(self._translator.tr("wifi.ssid.gen23.title"))
        self._password_field_labelGen23.setText(self._translator.tr("wifi.pass.title"))
        self._wifi_disclaimerGen23.setText(self._translator.tr("wifi.gen23.disclaimer"))
        self._wifi_continue_buttonGen23.setText(self._translator.tr("wifi.button"))

        self._prewifi_title_labelGen23.setText(self._translator.tr("wifi.gen23.pre.title"))
        self._prewifi_disclaimerGen23.setText(self._translator.tr("wifi.gen23.pre.disclaimer"))
        self._prewifi_connected_button.setText(self._translator.tr("wifi.gen23.pre.try_connection"))

        self._wifi_title_labelGen23.setContentsMargins(0, 0, 0, 0)
        self._wifi_title_labelGen23.setWordWrap(False)
        self._title_widthGen23 = self._wifi_title_labelGen23.sizeHint().width()
        self._wifi_title_labelGen23.setWordWrap(True)
        self._apply_label_margins()

        self._update_gen23_toggle_text()
        self._rescan_buttonGen23.setText(self._translator.tr("wifi.gen23.rescan"))
        if self._gen23_status_key:
            self._wifi_statusGen23.setText(self._translator.tr(self._gen23_status_key))
