"""Round flag button showing (and letting the user switch) the UI language."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QGridLayout, QMenu, QToolButton, QWidget, QWidgetAction

from vacuula_installer.constants import LANGUAGES
from vacuula_installer.i18n import Translator

_FLAG_SIZE = 64
_ICON_SIZE = _FLAG_SIZE - 32
_GRID_COLUMNS = 4


class FlagButton(QToolButton):
    """Shows the current language's flag; click for a menu of languages."""

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator

        self.setObjectName("flagButton")
        self.setFixedSize(_FLAG_SIZE, _FLAG_SIZE)
        self.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

        self._menu = QMenu(self)
        self._menu.setObjectName("languageMenu")
        self._menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._menu.setWindowFlags(
            self._menu.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint
        )
        self._build_menu()

        self.clicked.connect(self._show_language_menu)  # ny
        self._translator.languageChanged.connect(self._on_language_changed)  # ny
        self._refresh()

    def _show_language_menu(self) -> None:
        anchor = self.parentWidget() or self
        anchor_center = anchor.mapToGlobal(anchor.rect().center())
        menu_size = self._menu.sizeHint()
        top_left = anchor_center - QPoint(menu_size.width() // 2, menu_size.height() // 2)
        self._menu.popup(top_left)

    def _build_menu(self) -> None:
        self._menu.clear()
        grid_widget = QWidget(self._menu)
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(8)

        for index, code in enumerate(self._translator.available_languages()):
            row, column = divmod(index, _GRID_COLUMNS)
            grid.addWidget(self._make_flag_option(code, grid_widget), row, column)

        action = QWidgetAction(self._menu)
        action.setDefaultWidget(grid_widget)
        self._menu.addAction(action)

    def _make_flag_option(self, code: str, parent: QWidget) -> QToolButton:
        meta = LANGUAGES.get(code)
        button = QToolButton(parent)
        button.setObjectName("flagButton")
        button.setFixedSize(_FLAG_SIZE, _FLAG_SIZE)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIcon(QIcon(str(meta.flag_svg)) if meta else QIcon())
        button.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        button.setToolTip(meta.native_name if meta else code.upper())
        button.clicked.connect(self._make_selector(code))
        return button

    def _make_selector(self, code: str):
        def _select(checked: bool = False) -> None:
            del checked
            self._translator.set_language(code)
            self._menu.close()

        return _select

    def _on_language_changed(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        meta = LANGUAGES.get(self._translator.language)
        self.setIcon(QIcon(str(meta.flag_svg)) if meta else QIcon())
        self.setToolTip(self._translator.tr("welcome.language_tooltip"))
