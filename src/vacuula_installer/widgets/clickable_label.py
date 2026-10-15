from PySide6.QtCore import Signal
from PySide6.QtGui import QMouseEvent, Qt
from PySide6.QtWidgets import QLabel


class ClickableLabel(QLabel):
    clicked = Signal()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)
