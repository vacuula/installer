"""Vibecoded background flair, dont ask me about this"""

from __future__ import annotations

import random

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from vacuula_installer.constants import FLAIR_WELCOME_WORDS
from vacuula_installer.theme import PALETTE

_SEED = 42
_MIN_OPACITY, _MAX_OPACITY = 0.05, 0.16
_MIN_SIZE, _MAX_SIZE = 13, 27
_MAX_TILT_DEGREES = 16

# Keep words away from the window edges.
_X_MARGIN_RATIO = 0.08
_Y_MARGIN_RATIO = 0.10
_CENTER_EXCLUDE_X_RATIO = 0.25
_CENTER_EXCLUDE_Y_RATIO = 0.25

# Minimum gap between two word bounding boxes.
_MIN_GAP_PX = 12
# How many random positions to try before giving up on a word.
_MAX_PLACEMENT_ATTEMPTS = 40


class _FlairItem:
    __slots__ = ("angle", "opacity", "point_size", "text", "x_ratio", "y_ratio")

    def __init__(
        self, text: str, x_ratio: float, y_ratio: float, angle: float, point_size: float, opacity: float
    ) -> None:
        self.text = text
        self.x_ratio = x_ratio
        self.y_ratio = y_ratio
        self.angle = angle
        self.point_size = point_size
        self.opacity = opacity


class BackgroundFlairWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._items = self._build_items()

    @staticmethod
    def _build_items() -> list[_FlairItem]:
        rng = random.Random(_SEED)
        items: list[_FlairItem] = []
        # Use a reference size for layout; the ratios scale with the widget.
        ref_width, ref_height = 800, 600

        placed_rects: list[tuple[float, float, float, float]] = []

        for word in FLAIR_WELCOME_WORDS:
            for _ in range(_MAX_PLACEMENT_ATTEMPTS):
                x_ratio = rng.uniform(_X_MARGIN_RATIO, 1.0 - _X_MARGIN_RATIO)
                y_ratio = rng.uniform(_Y_MARGIN_RATIO, 1.0 - _Y_MARGIN_RATIO)
                angle = rng.uniform(-_MAX_TILT_DEGREES, _MAX_TILT_DEGREES)
                point_size = rng.uniform(_MIN_SIZE, _MAX_SIZE)
                opacity = rng.uniform(_MIN_OPACITY, _MAX_OPACITY)

                # Approximate the word's footprint at the reference size.
                font = QFont()
                font.setPointSizeF(point_size)
                font.setWeight(QFont.Weight.DemiBold)
                metrics = QFontMetricsF(font)
                bbox = metrics.boundingRect(word)

                # Add a safety margin for rotation.
                w = bbox.width() + 16
                h = bbox.height() + 8

                x = x_ratio * ref_width
                y = y_ratio * ref_height

                # Check window-edge clipping.
                if x - w / 2 < 0 or x + w / 2 > ref_width or y - h / 2 < 0 or y + h / 2 > ref_height:
                    continue

                # Avoid the center where buttons sit.
                if abs(x_ratio - 0.5) < _CENTER_EXCLUDE_X_RATIO and abs(y_ratio - 0.5) < _CENTER_EXCLUDE_Y_RATIO:
                    continue

                # Check overlap with already placed words.
                overlaps = any(
                    abs(x - px) < (w + pw) / 2 + _MIN_GAP_PX and abs(y - py) < (h + ph) / 2 + _MIN_GAP_PX
                    for px, py, pw, ph in placed_rects
                )
                if overlaps:
                    continue

                placed_rects.append((x, y, w, h))
                items.append(_FlairItem(word, x_ratio, y_ratio, angle, point_size, opacity))
                break

        return items

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width, height = self.width(), self.height()
        base_color = QColor(PALETTE.flair_text)

        for item in self._items:
            painter.save()
            painter.translate(item.x_ratio * width, item.y_ratio * height)
            painter.rotate(item.angle)

            font = self.font()
            font.setPointSizeF(item.point_size)
            font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)

            color = QColor(base_color)
            color.setAlphaF(item.opacity)
            painter.setPen(color)

            # Center the text on its anchor point.
            metrics = QFontMetricsF(font)
            bbox = metrics.boundingRect(item.text)
            painter.drawText(QPointF(-bbox.width() / 2, bbox.height() / 4), item.text)

            painter.restore()
