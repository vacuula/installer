"""An overengineered SSID input field.

Wi-Fi network names are an arbitrary 0-32 *byte* sequence (not
character count -- multi-byte UTF-8 characters count for more than
one byte each), and some valid bytes dont correspond to a valid
character (or are whitespace).

So according to wifi spec ssid:s with for example leading or trailing
spaces are perfectly valid, but they are also easy to accidentaly type
or copy into a field with it not being very visible to user.

So "Wifi " can both be a valid ssid and a invisible misstake.

So this class simply underlines such sus whitespace without forbidding it.

It does forbid Null ssid:s, those are special anyway, and emmits signals
when enter is pressed for smoooth ui

It also enforces the length limit in a non confusable way (does not cut multibyte utf8 like emojis to single bytes to fit)
"""

from __future__ import annotations

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QKeyEvent, QSyntaxHighlighter, QTextCharFormat, QTextDocument
from PySide6.QtWidgets import QPlainTextEdit, QSizePolicy, QWidget

from vacuula_installer.theme import PALETTE

MAX_SSID_BYTES = 32


class _WhitespaceHighlighter(QSyntaxHighlighter):
    """Highlights leading/trailing whitespace"""

    # Uses difference between len(strip) and len to detect leading/trailing whitespace
    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self._format = QTextCharFormat()
        self._format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        self._format.setUnderlineColor(PALETTE.accent_green)

    def highlightBlock(self, text: str) -> None:
        leading = len(text) - len(text.lstrip())
        if leading:
            self.setFormat(0, leading, self._format)

        trailing = len(text) - len(text.rstrip())
        if trailing:
            self.setFormat(len(text) - trailing, trailing, self._format)


class SsidInput(QPlainTextEdit):
    """A single-line SSID field with a byte-length cap and no stripping.

    Emits :attr:`returnPressed` (mirroring QLineEdit) when Enter is hit,
    instead of inserting a newline -- SSIDs are always single-line.
    """

    returnPressed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("wifiInput")
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTabChangesFocus(True)
        self._fit_to_one_line()

        # Nasty sizehint bug:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._highlighter = _WhitespaceHighlighter(self.document())
        self.textChanged.connect(self._enforce_byte_limit)

    def _fit_to_one_line(self) -> None:
        # unify such that QPlainTextEdit can look like a QLineInput
        self.document().setDocumentMargin(0)
        # Clanker provided fix
        self.ensurePolished()
        margins = self.contentsMargins()
        self.setFixedHeight(self.fontMetrics().height() + margins.top() + margins.bottom())

    def is_valid(self) -> bool:
        """True if the current text is 1-32 bytes once UTF-8 encoded."""
        return 0 < len(self.toPlainText().encode("utf-8")) <= MAX_SSID_BYTES

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.returnPressed.emit()
            return
        super().keyPressEvent(event)

    def insertFromMimeData(self, source: QMimeData) -> None:
        # Only one line ssid:s, no newlines allowed
        text = source.text().replace("\r\n", " ").replace("\n", " ").replace("\r", " ")  # support of multiple os jank
        self.textCursor().insertText(text)

    def _enforce_byte_limit(self) -> None:
        text = self.toPlainText()
        encoded = text.encode("utf-8")
        if len(encoded) <= MAX_SSID_BYTES:
            return

        # Truncate on a UTF-8 character boundary (never split a multi-byte
        # character) and drop back in without re-triggering this handler
        # or disturbing the cursor position more than necessary.
        truncated = encoded[:MAX_SSID_BYTES].decode("utf-8", errors="ignore")
        cursor = self.textCursor()
        position = min(cursor.position(), len(truncated))
        self.blockSignals(True)
        self.setPlainText(truncated)
        self.blockSignals(False)
        cursor = self.textCursor()
        cursor.setPosition(position)
        self.setTextCursor(cursor)
