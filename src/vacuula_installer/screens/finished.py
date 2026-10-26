from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QIcon
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from vacuula_installer.constants import (
    BUYMEACOFFEE_SVG,
    DISCORD_SVG,
    GITHUB_SVG,
    KOFI_SVG,
)
from vacuula_installer.i18n import Translator

CIRCLE_BUTTON_DIAMETER = 48
CIRCLE_ICON_SIZE = 22
ICON_COLOR = QColor("white")


@dataclass(frozen=True)
class LinkButtonSpec:
    """One circular link button: an svg icon, a hover-name translation key,
    and the url it opens. Add more of these to `LINK_BUTTONS` below -- the
    row lays itself out automatically, nothing else needs to change."""

    svg_path: Path
    tooltip_key: str
    url: str


LINK_BUTTONS: tuple[LinkButtonSpec, ...] = (
    LinkButtonSpec(GITHUB_SVG, "GitHub", "https://github.com/vacuula/vacuula"),
    LinkButtonSpec(DISCORD_SVG, "Discord", "https://discord.gg/PAgwhWvyD8"),
    LinkButtonSpec(BUYMEACOFFEE_SVG, "Buy Me a Coffee", "https://www.buymeacoffee.com/philip2809"),
    LinkButtonSpec(KOFI_SVG, "Ko-Fi", "https://ko-fi.com/V7V61PBIY6"),
)

class CircleLinkButton(QPushButton):
    """A round, outlined button with a centered svg icon. Click opens `url`
    in the system browser; hover shows the translated tooltip."""

    def __init__(
        self,
        spec: LinkButtonSpec,
        translator: Translator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._spec = spec
        self._translator = translator

        self.setObjectName("circleLinkButton")
        self.setFixedSize(CIRCLE_BUTTON_DIAMETER, CIRCLE_BUTTON_DIAMETER)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setIcon(QIcon(str(spec.svg_path)))
        self.setIconSize(QSize(CIRCLE_ICON_SIZE, CIRCLE_ICON_SIZE))

        self.clicked.connect(self._open_url)
        self._retranslate()

    def _open_url(self) -> None:
        QDesktopServices.openUrl(QUrl(self._spec.url))

    def _retranslate(self) -> None:
        self.setToolTip(self._translator.tr(self._spec.tooltip_key))


class FinishedScreen(QWidget):
    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._vacuula_url = "vacuula.local"
        self._link_buttons: list[CircleLinkButton] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 40, 20, 26)
        outer.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        outer.setSpacing(16)

        self._icon_label = QLabel("🎉", self)
        self._icon_label.setObjectName("errorIconLabel")
        self._icon_label.setStyleSheet(
            "font-size: 45px;"
        )
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._finished_title = QLabel(self)
        self._finished_title.setObjectName("serversearchTitleLabel")
        self._finished_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._finished_title.setWordWrap(True)

        self.finished_subtitle = QLabel(self)
        self.finished_subtitle.setObjectName("serversearchDetailLabel")
        self.finished_subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.finished_subtitle.setOpenExternalLinks(True)
        self.finished_subtitle.setWordWrap(True)

        outer.addWidget(self._icon_label)
        outer.addWidget(self._finished_title)
        outer.addWidget(self.finished_subtitle)

        outer.addSpacing(24)
        outer.addLayout(self._build_link_row())

        self._translator.languageChanged.connect(self._retranslate)
        self._retranslate()

    def _build_link_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(14)
        row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        for spec in LINK_BUTTONS:
            button = CircleLinkButton(spec, self._translator, self)
            self._link_buttons.append(button)
            row.addWidget(button)
        return row

    def set_vacuula_url(self, url: str) -> None:
        self._vacuula_url = url
        self.finished_subtitle.setText(self._translator.tr("finished.subtitle", url=self._vacuula_url))

    def _retranslate(self) -> None:
        self._finished_title.setText(self._translator.tr("finished.title"))
        self.finished_subtitle.setText(self._translator.tr("finished.subtitle", url=self._vacuula_url))
        for button in self._link_buttons:
            button._retranslate()