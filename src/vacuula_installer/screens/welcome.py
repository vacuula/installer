"""First screen on the right-hand side: language picker + continue."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QStackedLayout, QVBoxLayout, QWidget

from vacuula_installer.i18n import Translator
from vacuula_installer.widgets.background_flair import BackgroundFlairWidget
from vacuula_installer.widgets.language_selector import FlagButton


class WelcomeScreen(QWidget):
    """Emits :attr:`continueRequested` when the user is ready to move on."""

    continueRequested = Signal()

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator

        layers = QStackedLayout(self)
        layers.setStackingMode(QStackedLayout.StackingMode.StackAll)

        self._flair = BackgroundFlairWidget(self)

        layers.addWidget(self._flair)

        foreground = QWidget(self)
        foreground.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        fg_layout = QVBoxLayout(foreground)
        # fg_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fg_layout.setSpacing(16)
        fg_layout.setContentsMargins(50, 40, 50, 26)
        fg_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._flag_button = FlagButton(self._translator, foreground)
        self._tagline_label = QLabel(foreground)
        self._tagline_label.setObjectName("taglineLabel")
        self._tagline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._continue_button = QPushButton(foreground)
        self._continue_button.setObjectName("continueButton")
        self._continue_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._continue_button.clicked.connect(self.continueRequested)
        self._helpinfo = QLabel(foreground)
        self._helpinfo.setObjectName("serversearchDetailLabel")
        self._helpinfo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._helpinfo.setWordWrap(True)
        self._helpinfo.setOpenExternalLinks(True)

        fg_layout.addStretch(1)
        fg_layout.addWidget(self._flag_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        fg_layout.addWidget(self._tagline_label)
        fg_layout.addSpacing(10)
        fg_layout.addWidget(
            self._continue_button, alignment=Qt.AlignmentFlag.AlignHCenter
        )
        fg_layout.addSpacing(24)
        fg_layout.addWidget(self._helpinfo)
        fg_layout.addStretch(1)

        layers.addWidget(foreground)

        self._translator.languageChanged.connect(self._retranslate)
        self._retranslate()

    def _retranslate(self) -> None:
        self._tagline_label.setText(self._translator.tr("welcome.tagline"))
        self._continue_button.setText(self._translator.tr("welcome.continue"))
        self._helpinfo.setText(self._translator.tr("welcome.find_help"))
