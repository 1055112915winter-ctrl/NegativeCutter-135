"""Centralized QSS generator for the darkroom theme."""

from filmcrop.gui.theme import (
    PAGE_BG, CARD_BG, SURFACE_BG, PANEL_BG, CANVAS_BG,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY,
    BRAND, BRAND_LIGHT, BRAND_DIM, ERROR, FOCUS,
    BORDER_LIGHT, BORDER_WARM, BORDER_HOVER,
    BTN_SAND_BG, BTN_SAND_TEXT,
    BTN_BRAND_BG, BTN_BRAND_TEXT,
)


def build_stylesheet() -> str:
    return f"""
    QMainWindow {{
        background-color: {PAGE_BG};
    }}
    QWidget {{
        background-color: {PAGE_BG};
        color: {TEXT_PRIMARY};
        font-family: "Avenir Next", "Segoe UI", "PingFang SC", sans-serif;
        font-size: 14px;
        border-radius: 0px;
    }}

    /* ── Menu ── */
    QMenuBar {{
        background-color: {CARD_BG};
        color: {TEXT_PRIMARY};
        border-bottom: 1px solid {BORDER_LIGHT};
        padding: 3px 10px;
    }}
    QMenuBar::item {{
        background: transparent;
        padding: 4px 12px;
        border-radius: 3px;
    }}
    QMenuBar::item:selected {{
        background-color: {PANEL_BG};
    }}
    QMenu {{
        background-color: {CARD_BG};
        border: 1px solid {BORDER_WARM};
        border-radius: 4px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 6px 24px;
        border-radius: 3px;
    }}
    QMenu::item:selected {{
        background-color: {PANEL_BG};
    }}

    /* ── Toolbar ── */
    QToolBar {{
        background-color: {CARD_BG};
        border-bottom: 1px solid {BORDER_LIGHT};
        padding: 7px 12px;
        spacing: 6px;
    }}
    QToolBar QToolButton {{
        background: transparent;
        color: {TEXT_SECONDARY};
        border: 1px solid transparent;
        border-radius: 3px;
        padding: 5px 10px;
        font-size: 13px;
        font-weight: 500;
    }}
    QToolBar QToolButton:hover {{
        background-color: {PANEL_BG};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_WARM};
    }}
    QToolBar QToolButton:pressed {{
        background-color: {BORDER_HOVER};
    }}

    QWidget#panel {{
        background-color: {CARD_BG};
        border: 1px solid {BORDER_WARM};
        border-radius: 6px;
    }}

    /* ── Cards (panel sections) ── */
    QWidget#card {{
        background-color: {SURFACE_BG};
        border: 1px solid {BORDER_WARM};
        border-radius: 5px;
    }}
    QWidget#coordBox {{
        background-color: transparent;
        border: none;
    }}

    /* ── Buttons ── */
    QPushButton {{
        background-color: {BTN_SAND_BG};
        color: {BTN_SAND_TEXT};
        border: 1px solid {BORDER_WARM};
        border-radius: 4px;
        padding: 8px 14px;
        font-weight: 600;
        font-size: 13px;
    }}
    QPushButton:hover {{
        background-color: {BORDER_HOVER};
        border-color: {BORDER_HOVER};
    }}
    QPushButton:pressed {{
        background-color: {BORDER_WARM};
    }}
    QPushButton:disabled {{
        background-color: {BORDER_LIGHT};
        color: {TEXT_TERTIARY};
    }}
    QPushButton#primary {{
        background-color: {BTN_BRAND_BG};
        color: {BTN_BRAND_TEXT};
        border-color: {BTN_BRAND_BG};
    }}
    QPushButton#primary:hover {{
        background-color: {BRAND_LIGHT};
    }}
    QPushButton#primary:pressed {{
        background-color: {BRAND_DIM};
    }}
    QPushButton#primary:disabled {{
        background-color: {BORDER_WARM};
        color: {TEXT_TERTIARY};
        border-color: {BORDER_LIGHT};
    }}

    /* ── Inputs ── */
    QSpinBox, QComboBox {{
        background-color: {PANEL_BG};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_WARM};
        border-radius: 4px;
        padding: 7px 10px;
        font-size: 13px;
        min-height: 20px;
    }}
    QSpinBox:focus, QComboBox:focus {{
        border: 1px solid {FOCUS};
    }}
    QComboBox QAbstractItemView {{
        background-color: {CARD_BG};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_WARM};
        border-radius: 3px;
        padding: 6px 10px;
        font-size: 13px;
        selection-background-color: {PANEL_BG};
        selection-color: {TEXT_PRIMARY};
        outline: none;
    }}
    QComboBox QAbstractItemView::item {{
        padding: 8px 14px;
        min-height: 24px;
    }}
    QSpinBox::up-button, QSpinBox::down-button {{
        background: {BORDER_LIGHT};
        border-radius: 2px;
        margin: 2px;
        width: 16px;
        border: none;
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
        background: {BORDER_HOVER};
    }}

    /* ── List ── */
    QListWidget {{
        background-color: {PANEL_BG};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_WARM};
        border-radius: 5px;
        padding: 4px;
        font-size: 12px;
        outline: none;
    }}
    QListWidget::item {{
        padding: 7px 10px;
        border-radius: 3px;
        margin: 1px 2px;
        border-bottom: 1px solid {BORDER_LIGHT};
    }}
    QListWidget::item:last {{
        border-bottom: none;
    }}
    QListWidget::item:selected {{
        background-color: #3c3223;
        color: {TEXT_PRIMARY};
    }}
    QListWidget::item:hover:!selected {{
        background-color: {BORDER_LIGHT};
    }}
    /* Remove focus rect / odd empty selection artefacts */
    QListWidget:focus {{
        border: 1px solid {BORDER_WARM};
    }}

    /* ── Labels ── */
    QLabel {{
        background-color: transparent;
        color: {TEXT_SECONDARY};
        font-size: 13px;
    }}
    QLabel#heading {{
        color: {BRAND};
        font-weight: 700;
        font-size: 12px;
        margin-bottom: 3px;
    }}
    QLabel#hint {{
        color: {TEXT_TERTIARY};
        font-size: 11px;
    }}
    QLabel#wordmark {{
        color: {TEXT_PRIMARY};
        font-family: "Avenir Next Condensed", "Avenir Next", "Segoe UI", sans-serif;
        font-size: 19px;
        font-weight: 800;
    }}
    QLabel#brandSubtitle {{
        color: {TEXT_TERTIARY};
        font-size: 10px;
        font-weight: 600;
    }}

    /* ── Status Bar ── */
    QStatusBar {{
        background-color: {CARD_BG};
        color: {TEXT_TERTIARY};
        border-top: 1px solid {BORDER_LIGHT};
        font-size: 12px;
    }}
    QStatusBar::item {{
        border: none;
    }}

    /* ── Splitter ── */
    QSplitter::handle {{
        background-color: {PAGE_BG};
    }}
    QSplitter::handle:horizontal {{
        width: 14px;
    }}
    QSplitter::handle:vertical {{
        height: 2px;
    }}

    /* ── Dialog ── */
    QProgressDialog {{
        background-color: {CARD_BG};
    }}
    QDialog {{
        background-color: {PAGE_BG};
    }}
    QMessageBox {{
        background-color: {CARD_BG};
    }}
    QMessageBox QPushButton {{
        min-width: 80px;
    }}

    /* ── Canvas ── */
    QGraphicsView {{
        border: 1px solid {BORDER_WARM};
        border-radius: 4px;
        background-color: {CANVAS_BG};
    }}

    /* ── Line Edit ── */
    QLineEdit {{
        background-color: {PANEL_BG};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_WARM};
        border-radius: 4px;
        padding: 7px 10px;
    }}
    QLineEdit:focus {{
        border: 1px solid {FOCUS};
    }}

    /* ── Form ── */
    QFormLayout QLabel {{
        color: {TEXT_SECONDARY};
    }}

    /* ── Scrollbar ── */
    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
        border-radius: 3px;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER_WARM};
        border-radius: 3px;
        min-height: 32px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {BORDER_HOVER};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 6px;
        border-radius: 3px;
    }}
    QScrollBar::handle:horizontal {{
        background: {BORDER_WARM};
        border-radius: 3px;
        min-width: 32px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {BORDER_HOVER};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    """
