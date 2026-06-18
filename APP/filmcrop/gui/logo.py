"""Generated NegativeCutter brand assets for the darkroom GUI."""

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QPixmap, QIcon, QColor, QPen, QBrush

from filmcrop.gui.theme import BRAND, BRAND_DIM, CARD_BG, TEXT_PRIMARY


_BG = QColor(CARD_BG)
_AMBER = QColor(BRAND)
_AMBER_DIM = QColor(BRAND_DIM)
_IVORY = QColor(TEXT_PRIMARY)


def _diamond(center: QPointF, radius: float) -> list[QPointF]:
    return [
        QPointF(center.x(), center.y() - radius),
        QPointF(center.x() + radius, center.y()),
        QPointF(center.x(), center.y() + radius),
        QPointF(center.x() - radius, center.y()),
    ]


def _draw_mark(painter: QPainter, size: int, with_plate: bool) -> None:
    s = float(size)
    center = QPointF(s / 2, s / 2)

    if with_plate:
        pad = s * 0.07
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(_BG))
        painter.drawRoundedRect(QRectF(pad, pad, s - pad * 2, s - pad * 2), s * 0.16, s * 0.16)

    outer_radius = s * (0.31 if with_plate else 0.38)
    pen = QPen(_AMBER)
    pen.setWidthF(max(1.5, s * 0.055))
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPolygon(_diamond(center, outer_radius))

    inner_radius = outer_radius * 0.58
    inner_pen = QPen(_AMBER_DIM)
    inner_pen.setWidthF(max(1.0, s * 0.022))
    painter.setPen(inner_pen)
    painter.drawPolygon(_diamond(center, inner_radius))

    lens_radius = s * 0.105
    lens_pen = QPen(_AMBER)
    lens_pen.setWidthF(max(1.2, s * 0.035))
    painter.setPen(lens_pen)
    painter.setBrush(QBrush(_BG))
    painter.drawEllipse(center, lens_radius, lens_radius)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(_IVORY))
    painter.drawEllipse(center, max(1.0, s * 0.026), max(1.0, s * 0.026))


def create_app_icon() -> QIcon:
    """Return the generated application icon at common display sizes."""
    icon = QIcon()
    for px in (16, 32, 64, 128, 256, 512):
        pixmap = QPixmap(px, px)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        _draw_mark(painter, px, with_plate=True)
        painter.end()
        icon.addPixmap(pixmap)
    return icon


def create_header_logo_pixmap(size: int = 48) -> QPixmap:
    """Return the plate-free diamond mark used in the control-panel header."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    _draw_mark(painter, size, with_plate=False)
    painter.end()
    return pixmap
