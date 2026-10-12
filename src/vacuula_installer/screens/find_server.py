"""
Before starting robot hacking biting or w/e a server needs to be set up.
This screen just shows feedback if a vacuula-server.local has been
detected, no iteraction except "here" link that opens browser for future server
install istructions.
"""
# Contains some jank bacause I obsessed about not allowing text to be wider than the text in the "title"

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QMargins,
    QParallelAnimationGroup,
    QRect,
    Qt,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QColor
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from vacuula_installer.constants import COMPUTER_SVG, SERVER_SVG
from vacuula_installer.i18n import Translator
from vacuula_installer.theme import PALETTE
from vacuula_installer.widgets.clickable_label import ClickableLabel
from vacuula_installer.widgets.spinner import SpinnerWidget
from vacuula_installer.widgets.width_tracking_label import WidthTrackingLabel


class FindServerScreen(QWidget):
    startFindServerRequested = Signal(str)
    enterIpManuallyRequested = Signal()
    manualConnectionTestRequested = Signal(str)

    """Simple informational screen shown while locating a Vacuula server."""

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._server_ip: str | None = None
        self._title_width = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 40, 20, 26)
        outer.setSpacing(18)

        self._central_stack = QStackedLayout()
        outer.addLayout(self._central_stack, 1)

        self._info_page = self._build_info_page()
        self._central_stack.addWidget(self._info_page)

        outer.addLayout(self._build_status_row())

        self._enter_ip_button = ClickableLabel(self)
        self._enter_ip_button.setObjectName("statusLabel")
        self._enter_ip_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._enter_ip_button.clicked.connect(self._handle_enter_ip_clicked)
        self._enter_ip_button.adjustSize()
        self._corner_margin = QMargins(0, 0, 14, 14)

        self._translator.languageChanged.connect(self._retranslate)
        self._title_label.widthChanged.connect(self._apply_label_margins)
        self._retranslate()
        self.reset_searching()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reposition_enter_ip_button()

    def _reposition_enter_ip_button(self) -> None:
        self._enter_ip_button.adjustSize()
        m = self._corner_margin
        x = self.width() - self._enter_ip_button.width() - m.right()
        y = self.height() - self._enter_ip_button.height() - m.bottom()
        self._enter_ip_button.move(max(0, x), max(0, y))

    def _build_info_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.setSpacing(24)

        self._title_label = WidthTrackingLabel(page)
        self._title_label.setObjectName("serversearchTitleLabel")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._title_label.setWordWrap(True)

        self._body_label = QLabel(page)
        self._body_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._body_label.setObjectName("serversearchBodyLabel")
        self._body_label.setWordWrap(True)
        self._body_label.setOpenExternalLinks(True)

        self._icon_row = self._build_icon_row(page)

        self._detailinfo_label = QLabel(page)
        self._detailinfo_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._detailinfo_label.setObjectName("serversearchDetailLabel")
        self._detailinfo_label.setWordWrap(True)

        layout.addWidget(self._title_label)
        layout.addWidget(self._body_label)
        self._manual_ip_container = self._build_manual_ip_container(page)
        layout.addWidget(self._manual_ip_container)
        layout.addWidget(self._icon_row)
        layout.addWidget(self._detailinfo_label)
        return page

    def _build_manual_ip_container(self, parent: QWidget) -> QWidget:
        container = QWidget(parent)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)

        row = QWidget(container)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        self._manual_ip_input = QLineEdit(row)
        self._manual_ip_input.setObjectName("wifiInput")
        self._manual_ip_input.setFixedWidth(220)
        self._manual_ip_input.returnPressed.connect(self._handle_try_connection_clicked)

        self._try_connection_button = QPushButton(row)
        self._try_connection_button.setObjectName("continueButton")
        self._try_connection_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._try_connection_button.clicked.connect(self._handle_try_connection_clicked)

        row_layout.addWidget(self._manual_ip_input)
        row_layout.addWidget(self._try_connection_button)

        self._manual_ip_status_label = QLabel(container)
        self._manual_ip_status_label.setObjectName("statusLabel")
        self._manual_ip_status_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._manual_ip_status_label.setWordWrap(True)
        self._manual_ip_status_label.hide()

        container_layout.addWidget(row, alignment=Qt.AlignmentFlag.AlignHCenter)
        container_layout.addWidget(self._manual_ip_status_label)
        container.hide()
        return container

    def _build_icon_row(self, parent: QWidget) -> QWidget:
        container = QWidget(parent)
        row = QHBoxLayout(container)
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.setSpacing(12)
        row.setContentsMargins(0, 0, 0, 0)

        self._computer = QSvgWidget(str(COMPUTER_SVG), parent)
        self._computer.setFixedSize(100, 100)

        self._dots_left = QLabel("•   •   •", parent)
        self._dots_left.setObjectName("serverSearchDOTS")
        self._dots_left.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._x_mark = QLabel("✕", parent)
        self._x_mark.setObjectName("serverSearchCROSS")
        self._x_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._dots_right = QLabel("•   •   •", parent)
        self._dots_right.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dots_right.setObjectName("serverSearchDOTS")

        self._server = QSvgWidget(str(SERVER_SVG), parent)
        self._server.setFixedSize(100, 100)

        row.addWidget(self._computer)
        row.addWidget(self._dots_left)
        row.addWidget(self._x_mark)
        row.addWidget(self._dots_right)
        row.addWidget(self._server)

        return container

    def reset_searching(self) -> None:
        self._server_ip = None
        self._central_stack.setCurrentWidget(self._info_page)
        self._status_label.setText(self._translator.tr("serversearch.status.searching"))
        self._dots_left.setStyleSheet("")
        self._dots_right.setStyleSheet("")
        self._x_mark.setText("✕")
        self._spinner.start()

        self._manual_ip_container.hide()
        self._manual_ip_status_label.hide()
        self._manual_ip_status_label.clear()
        self._manual_ip_input.clear()
        self._manual_ip_input.setEnabled(True)
        self._try_connection_button.setEnabled(True)
        self._enter_ip_button.show()

    def _fade_text_colour(
        self, label: QLabel, start_hex: str, end_hex: str, duration_ms: int = 1000
    ):
        anim = QVariantAnimation(parent=label)
        anim.setStartValue(QColor(start_hex))
        anim.setEndValue(QColor(end_hex))
        anim.setDuration(duration_ms)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # minor TODO: Do I need to re-set the fontsize?
        def _apply_color(color: QColor) -> None:
            label.setStyleSheet(f"color: {color.name()};font-size: 24px;")

        anim.valueChanged.connect(_apply_color)
        anim.start()
        return anim

    def show_server_detected(self, ip: str) -> QParallelAnimationGroup:
        self._x_mark.setText("🔗")
        self._x_mark.setStyleSheet(
            "font-size: 32px;"
        )  # Anoyingly 🔗 is bigger than ✕ for a given fontsize.. Empiric match
        self._spinner.stop()
        self._status_label.setText(
            self._translator.tr("serversearch.status.found", ip=ip)
        )
        color_anim1 = self._fade_text_colour(
            self._dots_left, PALETTE.text_muted, "#1dd73c", 1300
        )
        color_anim2 = self._fade_text_colour(
            self._dots_right, PALETTE.text_muted, "#1dd73c", 1300
        )
        group = QParallelAnimationGroup()
        group.addAnimation(color_anim2)
        group.addAnimation(color_anim1)

        return group

    def _build_status_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch(1)

        self._status_label = QLabel(self)
        self._status_label.setObjectName("statusLabel")
        self._spinner = SpinnerWidget(self, diameter=16)

        row.addWidget(self._status_label)
        row.addWidget(self._spinner)
        row.addStretch(1)
        return row

    def _handle_enter_ip_clicked(self) -> None:
        self.enterIpManuallyRequested.emit()
        self._enter_ip_button.hide()
        self._manual_ip_container.show()
        self._manual_ip_input.setFocus()

    def _handle_try_connection_clicked(self) -> None:
        ip = self._manual_ip_input.text().strip()
        if not ip:
            return
        self._manual_ip_input.setEnabled(False)
        self._try_connection_button.setEnabled(False)
        self._manual_ip_status_label.hide()
        self.manualConnectionTestRequested.emit(ip)

    def set_manual_ip_test_result(self, success: bool, message: str = "") -> None:
        if success:
            self._manual_ip_container.hide()
            self._manual_ip_status_label.clear()
        else:
            self._manual_ip_input.setEnabled(True)
            self._try_connection_button.setEnabled(True)
            self._manual_ip_status_label.setText(
                message or self._translator.tr("serversearch.manual.failed")
            )
            self._manual_ip_status_label.show()

    # Part of getting title textwidth as limit for other Qlabels
    def _apply_label_margins(self) -> None:
        available = self._title_label.width()
        if self._title_width <= available:
            content_width = self._title_width
        else:
            # Title needs to wrap. Word wrap breaks on whole words, so its
            # widest wrapped line will be narrower than `available` - using
            # `available` here would let body/detail wrap wider than the
            # title actually renders, the opposite of the intent.
            content_width = self._wrapped_title_width(available)
        extra = max(0, available - content_width)
        left, right = extra // 2, extra - extra // 2
        for label in (self._title_label, self._body_label, self._detailinfo_label):
            label.setContentsMargins(left, 0, right, 0)

    # Part of getting title textwidth as limit for other Qlabels
    def _wrapped_title_width(self, available: int) -> int:
        """Width of the title's widest line once wrapped to fit `available`."""
        fm = self._title_label.fontMetrics()
        rect = fm.boundingRect(
            QRect(0, 0, available, 32767),
            Qt.TextFlag.TextWordWrap,
            self._title_label.text(),
        )
        return rect.width()

    def _retranslate(self) -> None:
        self._title_label.setText(self._translator.tr("serversearch.title"))
        self._body_label.setText(self._translator.tr("serversearch.body"))
        self._detailinfo_label.setText(self._translator.tr("serversearch.detailinfo"))
        self._enter_ip_button.setText(
            self._translator.tr("serversearch.enter_ip_manually")
        )
        self._reposition_enter_ip_button()
        self._manual_ip_input.setPlaceholderText(
            self._translator.tr("serversearch.manual.placeholder")
        )
        self._try_connection_button.setText(
            self._translator.tr("serversearch.manual.try_connection")
        )

        # Part of getting title textwidth as limit for other Qlabels
        self._title_label.setContentsMargins(0, 0, 0, 0)
        self._title_label.setWordWrap(False)
        self._title_width = self._title_label.sizeHint().width()
        self._title_label.setWordWrap(True)
        self._apply_label_margins()

        if self._server_ip is None:
            self._status_label.setText(
                self._translator.tr("serversearch.status.searching")
            )
        else:
            self._status_label.setText(
                self._translator.tr("serversearch.status.found", ip=self._server_ip)
            )
