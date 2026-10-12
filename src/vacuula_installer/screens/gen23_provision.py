"""4-step checklist shown while the robot joins wifi and the cloud."""

from __future__ import annotations

from PySide6.QtCore import QMargins, Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vacuula_installer.i18n import Translator
from vacuula_installer.widgets.spinner import SpinnerWidget

STEP_KEYS = (
    "provision.gen23.step1",
    "provision.gen23.step2",
    "provision.gen23.step3",
    "provision.gen23.step4",
)


class Gen23ProvisionScreen(QWidget):
    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._step = 0
        self._failed = False
        self._log_open = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 40, 20, 26)
        outer.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._title = QLabel(self)
        self._title.setObjectName("serversearchTitleLabel")
        self._title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._title.setWordWrap(True)
        outer.addWidget(self._title)
        outer.addSpacing(30)

        # One grid for all steps: column 0 is the status slot, column 1 the
        # text. Rows share the columns, so the icons line up no matter how
        # long each text is (the block as a whole is centered).
        steps_box = QWidget(self)
        grid = QGridLayout(steps_box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(10)

        self._icons: list[QLabel] = []
        self._spinners: list[SpinnerWidget] = []
        self._texts: list[QLabel] = []
        for row, _ in enumerate(STEP_KEYS):
            # Status slot: shows either the ✔/○ label or the spinner, same
            # fixed width so nothing shifts between states.
            slot = QWidget(steps_box)
            slot.setFixedWidth(28)
            slot_layout = QHBoxLayout(slot)
            slot_layout.setContentsMargins(0, 0, 0, 0)

            icon = QLabel(slot)
            icon.setObjectName("serversearchBodyLabel")
            spinner = SpinnerWidget(slot, 18)
            spinner.hide()
            slot_layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignCenter)
            slot_layout.addWidget(spinner, alignment=Qt.AlignmentFlag.AlignCenter)

            text = QLabel(steps_box)
            text.setObjectName("serversearchBodyLabel")

            grid.addWidget(slot, row, 0, alignment=Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(text, row, 1, alignment=Qt.AlignmentFlag.AlignVCenter)
            self._icons.append(icon)
            self._spinners.append(spinner)
            self._texts.append(text)

        outer.addWidget(steps_box, alignment=Qt.AlignmentFlag.AlignHCenter)
        outer.addSpacing(10)

        self._milestone_list = QLabel(self)
        self._milestone_list.setObjectName("serversearchDetailLabel")
        self._milestone_list.setWordWrap(True)
        self._milestone_list.hide()
        outer.addWidget(self._milestone_list)
        self._milestone_lines: list[str] = []

        # Small terminal-icon button toggles the raw serial log, hidden by
        # default so the checklist stays the focus.
        self._log_toggle = QPushButton("⌨", self)
        self._log_toggle.setObjectName("iconButton")
        self._log_toggle.setFlat(True)
        self._log_toggle.setFixedSize(28, 28)
        self._log_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._log_toggle.setCheckable(True)
        self._log_toggle.toggled.connect(self._set_log_open)
        self._log_toggle.raise_()  # float above everything else in `outer`
        self._log_toggle_margin = QMargins(0, 0, 14, 14)

        self._log_view = QPlainTextEdit(self)
        self._log_view.setObjectName("provisionLogView")
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(500)
        self._log_view.setFixedHeight(120)
        self._log_view.hide()
        outer.addWidget(self._log_view)

        self._error = QLabel(self)
        self._error.setObjectName("serversearchDetailLabel")
        self._error.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._error.setWordWrap(True)
        self._error.hide()
        outer.addWidget(self._error)

        self._translator.languageChanged.connect(self._retranslate)
        self._retranslate()
        self.reset()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reposition_log_toggle()

    def _reposition_log_toggle(self) -> None:
        m = self._log_toggle_margin
        x = self.width() - self._log_toggle.width() - m.right()
        y = self.height() - self._log_toggle.height() - m.bottom()
        self._log_toggle.move(max(0, x), max(0, y))

    def add_milestone_done(self, label_key: str) -> None:
        self._milestone_lines.append(f"✔ {self._translator.tr(label_key)}")
        self._milestone_list.setText("\n".join(self._milestone_lines))
        self._milestone_list.show()

    def append_log(self, line: str) -> None:
        self._log_view.appendPlainText(line)
        self._log_toggle.show()

    def _set_log_open(self, open_: bool) -> None:
        self._log_open = open_
        self._log_view.setVisible(open_ and self._log_view.blockCount() > 0)
        self._update_log_toggle_text()

    def _update_log_toggle_text(self) -> None:
        tip_key = (
            "provision.gen23.log.hide" if self._log_open else "provision.gen23.log.show"
        )
        self._log_toggle.setToolTip(self._translator.tr(tip_key))

    # reset() should also clear these:
    def reset(self) -> None:
        self._failed = False
        self._error.hide()
        self._milestone_lines.clear()
        self._milestone_list.clear()
        self._milestone_list.hide()
        self._log_view.clear()
        self._log_view.hide()
        self._log_toggle.hide()
        self._log_toggle.setChecked(False)  # triggers _set_log_open(False)
        self.set_step(1)

    def set_step(self, step: int) -> None:
        """`step` is the step in progress: everything before it is done,
        it gets the spinner, everything after it is an empty circle."""
        self._step = step
        current = step - 1
        self._render(
            done_up_to=current,
            spinning=current if current < len(STEP_KEYS) else None,
        )

    def set_all_done(self) -> None:
        self._render(done_up_to=len(STEP_KEYS))

    def set_failed(self) -> None:
        self._failed = True
        # stop the spinner, the step it was on goes back to an empty circle
        self._render(done_up_to=max(self._step - 1, 0))
        self._error.setText(self._translator.tr("provision.gen23.failed"))
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
        if self._error.isVisible():
            self._error.setText(self._translator.tr("provision.gen23.failed"))
        self._update_log_toggle_text()
