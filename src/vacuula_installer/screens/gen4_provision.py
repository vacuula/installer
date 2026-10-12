"""2-step checklist shown while files are pushed to a Gen4 robot over MTP."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from vacuula_installer.i18n import Translator
from vacuula_installer.widgets.spinner import SpinnerWidget

STEP_KEYS = ("provision.gen4.step1", "provision.gen4.step2")


class Gen4ProvisionScreen(QWidget):
    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._step = 0
        self._failed = False
        self._done = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 40, 20, 26)
        outer.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._title = QLabel(self)
        self._title.setObjectName("serversearchTitleLabel")
        self._title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._title.setWordWrap(True)
        outer.addWidget(self._title)
        outer.addSpacing(30)

        # Same slot/column layout as the gen23 checklist, so the ✔/○/spinner
        # icons line up regardless of each step's text length.
        self._steps_box = QWidget(self)
        grid = QGridLayout(self._steps_box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(10)

        self._icons: list[QLabel] = []
        self._spinners: list[SpinnerWidget] = []
        self._texts: list[QLabel] = []
        for row, _ in enumerate(STEP_KEYS):
            slot = QWidget(self._steps_box)
            slot.setFixedWidth(28)
            slot_layout = QHBoxLayout(slot)
            slot_layout.setContentsMargins(0, 0, 0, 0)

            icon = QLabel(slot)
            icon.setObjectName("serversearchBodyLabel")
            spinner = SpinnerWidget(slot, 18)
            spinner.hide()
            slot_layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignCenter)
            slot_layout.addWidget(spinner, alignment=Qt.AlignmentFlag.AlignCenter)

            text = QLabel(self._steps_box)
            text.setObjectName("serversearchBodyLabel")

            grid.addWidget(slot, row, 0, alignment=Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(text, row, 1, alignment=Qt.AlignmentFlag.AlignVCenter)
            self._icons.append(icon)
            self._spinners.append(spinner)
            self._texts.append(text)

        outer.addWidget(self._steps_box, alignment=Qt.AlignmentFlag.AlignHCenter)
        outer.addSpacing(16)

        # Shown once uploading finishes: tells the user to power-cycle the
        # robot. Hidden the rest of the time, and instead of the checklist.
        self._instructions = QLabel(self)
        self._instructions.setObjectName("serversearchDetailLabel")
        self._instructions.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._instructions.setWordWrap(True)
        self._instructions.hide()
        outer.addWidget(self._instructions)

        self._error = QLabel(self)
        self._error.setObjectName("serversearchDetailLabel")
        self._error.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._error.setWordWrap(True)
        self._error.hide()
        outer.addWidget(self._error)

        self._translator.languageChanged.connect(self._retranslate)
        self._retranslate()
        self.reset()

    def reset(self) -> None:
        self._failed = False
        self._done = False
        self._error.hide()
        self._instructions.hide()
        self._steps_box.show()
        self.set_step(1)

    def set_step(self, step: int) -> None:
        """`step` is the step in progress: everything before it is done,
        it gets the spinner, everything after it is an empty circle."""
        self._step = step
        current = step - 1
        self._render(done_up_to=current, spinning=current if current < len(STEP_KEYS) else None)

    def set_finished(self) -> None:
        self._done = True
        self._render(done_up_to=len(STEP_KEYS))
        self._instructions.show()

    def set_failed(self) -> None:
        self._failed = True
        # stop the spinner, the step it was on goes back to an empty circle
        self._render(done_up_to=max(self._step - 1, 0))
        self._error.setText(self._translator.tr("provision.failed"))
        self._error.show()

    def _render(self, done_up_to: int, spinning: int | None = None) -> None:
        for i, (icon, spinner) in enumerate(zip(self._icons, self._spinners)):
            if i == spinning:
                icon.hide()
                spinner.start()
            else:
                spinner.stop()
                icon.setText("✔" if i < done_up_to else "○")
                icon.show()

    def _retranslate(self) -> None:
        self._title.setText(self._translator.tr("provision.title"))
        for text, key in zip(self._texts, STEP_KEYS):
            text.setText(self._translator.tr(key))
        self._instructions.setText(self._translator.tr("provision.gen4.instructions"))
        if self._error.isVisible():
            self._error.setText(self._translator.tr("provision.failed"))
