"""A small rotating-arc spinner, painted directly with QPainter."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from vacuula_installer.theme import PALETTE

_STEP_DEGREES = 10
_INTERVAL_MS = 35
_ARC_SPAN_DEGREES = 300
_PEN_WIDTH = 2.4


class SpinnerWidget(QWidget):
    """Small indeterminate spinner. Call :meth:`start`/:meth:`stop`."""

    def __init__(self, parent: QWidget | None = None, diameter: int = 18) -> None:
        super().__init__(parent)
        self._diameter = diameter
        self.setFixedSize(diameter, diameter)

        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)

    def start(self) -> None:
        self.show()
        if not self._timer.isActive():
            self._timer.start(_INTERVAL_MS)

    def stop(self) -> None:
        self._timer.stop()
        self.hide()

    def _advance(self) -> None:
        self._angle = (self._angle + _STEP_DEGREES) % 360
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor(PALETTE.accent_blue_hover))
        pen.setWidthF(_PEN_WIDTH)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        margin = _PEN_WIDTH
        rect = QRectF(margin, margin, self._diameter - 2 * margin, self._diameter - 2 * margin)
        # Was confused about spinning rate, apparently Qt angles are in 1/16th of a degree
        painter.drawArc(rect, -self._angle * 16, _ARC_SPAN_DEGREES * 16)
