"""NegativeCutter darkroom precision-instrument design system."""

from PyQt6.QtGui import QColor

# Surfaces
PAGE_BG = "#101315"
CARD_BG = "#171b1e"
SURFACE_BG = "#1a1f22"
PANEL_BG = "#23292c"
CANVAS_BG = "#050708"

# Text
TEXT_PRIMARY = "#edf0ee"
TEXT_SECONDARY = "#a7adb0"
TEXT_TERTIARY = "#7d868b"

# Accents
BRAND = "#d7a75e"
BRAND_LIGHT = "#e6b86e"
BRAND_DIM = "#b78945"
ERROR = "#d05d5d"
FOCUS = BRAND

# Borders
BORDER_LIGHT = "#252c2f"
BORDER_WARM = "#323b3f"
BORDER_HOVER = "#465156"
RING_WARM = "#c9ced0"

# Buttons
BTN_SAND_BG = PANEL_BG
BTN_SAND_TEXT = TEXT_PRIMARY
BTN_BRAND_BG = BRAND
BTN_BRAND_TEXT = "#16130e"
BTN_DARK_BG = BORDER_HOVER
BTN_DARK_TEXT = TEXT_PRIMARY

# Frame overlays: related metallic tones remain distinguishable on scans.
_FRAME_QCOLORS = [
    QColor(215, 167, 94),
    QColor(232, 193, 126),
    QColor(185, 137, 72),
    QColor(237, 240, 238),
    QColor(166, 174, 178),
    QColor(202, 122, 74),
]


def frame_color(idx: int) -> QColor:
    return _FRAME_QCOLORS[idx % len(_FRAME_QCOLORS)]
