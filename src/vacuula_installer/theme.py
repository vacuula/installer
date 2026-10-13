"""Class containing colours to use, and the stylesheet"""

# Colours chosen based on Vacuula logo + green and blue (ish) which happen to be colours Philip likes
# They will need refinement

# Don't question the stylesheet, I know what Im doing™

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from vacuula_installer.constants import ASSETS_DIR

_CHECK_SVG = (ASSETS_DIR / "check.svg").as_posix()


@dataclass(frozen=True)
class Palette:
    bg_colour: str = "#25262d"

    border_soft: str = "#4B4B65"

    text_primary: str = "#f3f0fa"
    text_muted: str = "#8f84ac"
    flair_text: str = "#cabdec"

    accent_blue: str = "#5c73f6"
    accent_blue_hover: str = "#707cff"
    accent_blue_pressed: str = "#4758c9"
    accent_blue_desaturated: str = "#2d324d"

    accent_green: str = "#0f9616"


PALETTE = Palette()

STYLE_SHEET = f"""
QWidget#central {{
    background: {PALETTE.bg_colour};
}}


QWidget#leftPanel {{
    background: {PALETTE.bg_colour};
}}

QWidget#rightPanel {{
    background: {PALETTE.bg_colour};
}}

QLabel, QRadioButton, QCheckBox {{
    color: {PALETTE.text_primary};
}}

QLabel#taglineLabel {{
    color: {PALETTE.text_muted};
    font-size: 14px;
}}

QLabel#connectInstructionLabel {{
    color: {PALETTE.text_primary};
    font-size: 18px;
    font-weight: 600;
}}

QLabel#serversearchTitleLabel {{
    color: {PALETTE.text_primary};
    font-size: 40px;
    font-weight: 700;
}}

QLabel#serversearchBodyLabel {{
    color: {PALETTE.text_primary};
    font-weight: 500;
    font-size: 18px;

}}

QLabel#serversearchDetailLabel {{
    color: {PALETTE.text_primary};
    font-size: 14px;
}}

QLabel#serverSearchDOTS {{
    color: {PALETTE.text_muted};
    font-size: 24px;

}}
QLabel#serverSearchCROSS {{
    color: {PALETTE.text_muted};
    font-size: 40px;
}}

QLabel#statusLabel {{
    color: {PALETTE.text_muted};
    font-size: 12px;
}}

QRadioButton, QCheckBox {{
    spacing: 0px;
}}

QRadioButton::indicator, QCheckBox::indicator {{
    width: 12px;
    height: 12px;
    border: 2px solid {PALETTE.border_soft};
    background: rgba(255, 255, 255, 14);
}}

QRadioButton::indicator {{
    border-radius: 6px;   /* half of 18 */
}}

QCheckBox::indicator {{
    border-radius: 5px;
}}

QRadioButton::indicator:hover, QCheckBox::indicator:hover {{
    border-color: {PALETTE.accent_blue_hover};
}}

/* Ring with a centered dot: the gradient paints the dot, then fades to bg */
QRadioButton::indicator:checked {{
    border-color: {PALETTE.accent_blue};
    background: qradialgradient(
        cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 {PALETTE.accent_blue},
        stop:0.45 {PALETTE.accent_blue},
        stop:0.5 {PALETTE.bg_colour},
        stop:1 {PALETTE.bg_colour}
    );
}}

QCheckBox::indicator:checked {{
    border-color: {PALETTE.accent_blue};
    background: {PALETTE.accent_blue};
    image: url({_CHECK_SVG});
}}

QRadioButton::indicator:disabled, QCheckBox::indicator:disabled {{
    border-color: {PALETTE.accent_blue_desaturated};
    background: transparent;
}}

QRadioButton#firmwareOptionRadio {{
    font-size: 16px;
    font-weight: 600;
}}

QToolButton#flagButton {{
    background-color: rgba(255, 255, 255, 20);
    border: 1px solid {PALETTE.border_soft};
    border-radius: 32px;
    font-size: 28px;
    padding-top: 3px;
}}

QToolButton#flagButton:hover {{
    background-color: {PALETTE.accent_blue_hover};
}}

QToolButton#flagButton::menu-indicator {{
    image: none;
    width: 0px;
}}

QMenu#languageMenu {{
    background-color: {PALETTE.bg_colour};
    border: 1px solid {PALETTE.border_soft};
    border-radius: 16px;
}}

QMenu#languageMenu::item {{
    padding: 0px;
    background: transparent;
}}

QMenu#languageMenu::item:selected {{
    background: transparent;
}}

QToolButton#backButton {{
    color: {PALETTE.text_muted};
    font-size: 24px;
    font-weight: 700;
    background: transparent;
    border: none;
}}

QToolButton#backButton:hover {{
    color: {PALETTE.text_primary};
}}

QPushButton {{
    background-color: {PALETTE.accent_blue};
    color: white;
    border: none;
    border-radius: 22px;
    min-height: 22px; /* 22 + 2*12 padding = 46 >= 2*22 radius. needed because otherwise rendered as square, not fully sure why but some qt rule and windows renders diffrently */
    padding: 12px 42px;
    font-size: 14px;
    font-weight: 600;
}}

QPushButton:disabled {{
    background-color: {PALETTE.accent_blue_desaturated};
    color: {PALETTE.text_muted};
}}

QPushButton:hover {{
    background-color: {PALETTE.accent_blue_hover};
}}

QPushButton:pressed {{
    background-color: {PALETTE.accent_blue_pressed};
}}

#wifiInput {{
    background-color: rgba(255, 255, 255, 14);
    border: 1px solid {PALETTE.border_soft};
    border-radius: 10px;
    padding: 10px 14px;
    color: {PALETTE.text_primary};
    font-size: 14px;
    selection-background-color: {PALETTE.accent_blue};
}}

#wifiInput:focus {{
    border: 1px solid {PALETTE.accent_blue};
    background-color: rgba(255, 255, 255, 22);
}}


QLabel#wifiExplanationLabel {{
    color: {PALETTE.text_muted};
    font-weight: 500;
    font-size: 18px;
}}

QPushButton#circleLinkButton {{
    border: 1px solid {PALETTE.accent_blue};
    border-radius: 24px;  /* half of CIRCLE_BUTTON_DIAMETER */
    background: transparent;
}}

QPushButton#circleLinkButton:hover {{
    border-color: {PALETTE.accent_blue_hover};
}}

QProgressBar {{
    background-color: {PALETTE.accent_blue_desaturated};
    border: 1px solid {PALETTE.border_soft};
    border-radius: 12px;   /* half of the 24px height set in code */
    text-align: center;
    color: {PALETTE.text_primary};
    font-size: 12px;
    font-weight: 600;
}}

QProgressBar::chunk {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {PALETTE.accent_blue_pressed},
        stop:1 {PALETTE.accent_blue}
    );
    border-radius: 11px;   /* outer radius minus the 1px border */
}}

QComboBox#wifiInput QAbstractItemView {{
    color: black;
    background-color: white;
    selection-background-color: {PALETTE.accent_blue};
    selection-color: white;
    outline: none;
}}

QMessageBox, QDialog {{
    background-color: {PALETTE.bg_colour};
}}

"""  # noqa: E501


def apply_app_palette(app: QApplication) -> None:
    """Apply the Vacuula palette to the given QApplication."""
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE_SHEET)

    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Link, QColor(PALETTE.accent_blue))
    palette.setColor(QPalette.ColorRole.LinkVisited, QColor(PALETTE.accent_blue))
    app.setPalette(palette)
