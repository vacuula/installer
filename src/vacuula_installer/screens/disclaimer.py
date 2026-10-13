"""Second screen on the right-hand side: disclaimer bullets + acknowledgement."""

from __future__ import annotations

import math

from PySide6 import QtGui
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QShowEvent, QTextDocument
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from vacuula_installer.i18n import Translator
from vacuula_installer.widgets.clickable_label import ClickableLabel

_CENTER = Qt.AlignmentFlag.AlignHCenter
_TOP = Qt.AlignmentFlag.AlignTop


class DisclaimerScreen(QWidget):
    """Emits :attr:`understandRequested` when the user accepts the notice."""

    understandRequested = Signal()

    # The bullet block is as wide as its widest wrapped line, capped at this
    # value. Sizing it to its content (instead of a fixed 460 px) is what makes
    # the visible text centred left-to-right, not just an empty box around it.
    _MAX_BLOCK_WIDTH = 460
    _MARKER_WIDTH = 14
    _ROW_SPACING = 8

    # Translation keys, top to bottom. The acknowledgement checkbox is its own
    # row, inserted after the first _BULLETS_BEFORE_CHECKBOX bullets.
    _BULLET_KEYS: tuple[str, ...] = (
        "disclaimer.bullet1",
        "disclaimer.bullet2",
        "disclaimer.bullet3",
        "disclaimer.bullet4",
        "disclaimer.bullet5",
        "disclaimer.bullet6",
        "disclaimer.bullet7",
        "disclaimer.bullet8",
    )
    _BULLETS_BEFORE_CHECKBOX = 4

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._title_label = QLabel(self)
        self._title_label.setObjectName("serversearchTitleLabel")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Bullet block: bullet rows plus the acknowledgement checkbox.
        self._bullet_block = QWidget(self)
        self._bullet_block.setObjectName("bulletBlock")
        self._bullet_block.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self._bullets: list[tuple[str, QLabel]] = []  # (translation key, text label)
        block_layout = QVBoxLayout(self._bullet_block)
        block_layout.setContentsMargins(0, 0, 0, 0)
        block_layout.setSpacing(8)
        for key in self._BULLET_KEYS:
            self._add_bullet_row(block_layout, key)
        self._acknowledge_checkbox, self._acknowledge_caption = self._add_acknowledge_row(block_layout, 4)
        self._warning_checkbox, self._warning_caption = self._add_acknowledge_row(block_layout, 6)

        self._understand_button = QPushButton(self)
        self._understand_button.setObjectName("understandButton")
        self._understand_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._understand_button.setEnabled(False)
        self._understand_button.clicked.connect(self.understandRequested)
        self._acknowledge_checkbox.toggled.connect(self._update_understand_button)
        self._warning_checkbox.toggled.connect(self._update_understand_button)

        # Centre the block with stretches on both sides. A horizontal layout hands
        # the block its real width, so the wrapped rows get the height they need
        # (an AlignHCenter item in the vertical layout is sized at the full width).
        centered_block = QHBoxLayout()
        centered_block.addStretch(1)
        centered_block.addWidget(self._bullet_block)
        centered_block.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.addStretch(1)
        layout.addWidget(self._title_label)
        layout.addSpacing(24)
        layout.addLayout(centered_block)
        layout.addSpacing(10)
        layout.addWidget(self._understand_button, alignment=_CENTER)
        layout.addStretch(1)

        self._translator.languageChanged.connect(self._retranslate)
        self._retranslate()

    def _update_understand_button(self) -> None:
        """Enable the button only while every acknowledgement is ticked."""
        self._understand_button.setEnabled(self._acknowledge_checkbox.isChecked() and self._warning_checkbox.isChecked())

    def _new_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(self._ROW_SPACING)
        row.setAlignment(_TOP)
        return row

    def _add_bullet_row(self, layout: QVBoxLayout, key: str) -> None:
        marker = QLabel("•", self._bullet_block)
        marker.setObjectName("serversearchDetailLabel")
        marker.setFixedWidth(self._MARKER_WIDTH)
        marker.setAlignment(_TOP | _CENTER)

        text = QLabel(self._bullet_block)
        text.setObjectName("serversearchDetailLabel")
        text.setWordWrap(True)
        text.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        text.setOpenExternalLinks(True)

        row = self._new_row()
        row.addWidget(marker)
        row.addWidget(text, 1)

        layout.addLayout(row)
        self._bullets.append((key, text))

    def _add_acknowledge_row(self, layout: QVBoxLayout, position) -> tuple[QCheckBox, QLabel]:
        # QCheckBox only draws plain text, so the caption is a QLabel instead
        # (rich text + word wrap like the bullets); clicking it toggles the box.
        checkbox = QCheckBox(self._bullet_block)
        checkbox.setObjectName("acknowledgeCheckBox")
        checkbox.setCursor(Qt.CursorShape.PointingHandCursor)

        caption = ClickableLabel(self._bullet_block)
        caption.setObjectName("serversearchDetailLabel")
        caption.setWordWrap(True)
        caption.setAlignment(Qt.AlignmentFlag.AlignLeft | _TOP)  # first line at the top
        caption.setCursor(Qt.CursorShape.PointingHandCursor)
        caption.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        caption.clicked.connect(checkbox.toggle)

        row = self._new_row()
        row.addWidget(checkbox, alignment=_TOP)
        row.addWidget(caption, 1)

        layout.insertLayout(position, row)
        return checkbox, caption

    @staticmethod
    def _wrapped_width(label: QLabel, limit: int) -> int:
        """Width of the widest line once the label's text wraps at ``limit`` px.

        Measured with a QTextDocument so rich text (``<b>...``) counts the way
        QLabel will actually draw it, not as literal tag characters.
        """
        label.ensurePolished()  # pick up the stylesheet font before measuring
        document = QTextDocument()
        document.setDocumentMargin(0)
        document.setDefaultFont(label.font())
        if QtGui.Qt.mightBeRichText(label.text()):
            document.setHtml(label.text())
        else:
            document.setPlainText(label.text())
        document.setTextWidth(limit)
        return math.ceil(document.idealWidth())

    def _fit_to_fonts(self) -> None:
        """Everything that depends on the final fonts: block width, checkbox alignment."""
        checkbox_rows = (
            (self._acknowledge_checkbox, self._acknowledge_caption),
            (self._warning_checkbox, self._warning_caption),
        )

        # Block exactly as wide as its widest wrapped line.
        rows = [(label, self._MARKER_WIDTH) for _, label in self._bullets]
        for checkbox, caption in checkbox_rows:
            checkbox.ensurePolished()
            rows.append((caption, checkbox.sizeHint().width()))
        width = 0
        for label, lead in rows:  # lead = marker / checkbox column in front of the text
            lead += self._ROW_SPACING
            width = max(width, lead + self._wrapped_width(label, self._MAX_BLOCK_WIDTH - lead))
        # +2 px of slack so rounding can never re-wrap the widest line.
        self._bullet_block.setFixedWidth(min(width + 2, self._MAX_BLOCK_WIDTH))

        # Checkbox centred on the first text line, whichever of the two is taller.
        for checkbox, caption in checkbox_rows:
            line = caption.fontMetrics().height()
            checkbox.setMinimumHeight(line)
            hint = checkbox.sizeHint().height()
            caption.setContentsMargins(0, max(0, (hint - line) // 2), 0, 0)

    def showEvent(self, event: QShowEvent) -> None:
        # A stylesheet inherited from the parent window only applies once the
        # screen is in place, so fit again with the real fonts.
        self._fit_to_fonts()
        super().showEvent(event)

    def _retranslate(self) -> None:
        tr = self._translator.tr
        self._title_label.setText(tr("disclaimer.title"))
        for key, label in self._bullets:
            label.setText(tr(key))
        self._acknowledge_caption.setText(tr("disclaimer.acknowledge"))
        self._understand_button.setText(tr("disclaimer.understand"))
        self._warning_caption.setText(tr("disclaimer.warning"))
        self._fit_to_fonts()
