"""
Draggable frame boundary overlay for QGraphicsScene.
Dark-warm theme with corner handles and glow effects.
"""

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPen, QColor, QCursor
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsItem

from filmcrop.gui.theme import frame_color

_EDGE_TOLERANCE = 12.0
_HANDLE_SIZE = 8.0


class DraggableFrameItem(QGraphicsRectItem):
    """A frame rectangle with draggable edges and corner handles."""

    def __init__(self, frame: dict, color_idx: int, on_changed, on_released=None, parent=None):
        super().__init__(parent)
        self._frame = frame
        self._color_idx = color_idx
        self._color = frame_color(color_idx)
        self._on_changed = on_changed
        self._on_released = on_released
        self._drag_edge = None
        self._drag_start_pos = None
        self._drag_start_values: dict[str, int] = {}
        self._drag_start_frame: dict | None = None

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self._update_rect()
        self._update_pen()

    def _update_rect(self):
        self.setRect(
            QRectF(
                self._frame["left"],
                self._frame["top"],
                self._frame["right"] - self._frame["left"],
                self._frame["bottom"] - self._frame["top"],
            )
        )

    def _update_pen(self, is_hovered=False):
        pen = QPen(self._color)
        pen.setWidth(3 if is_hovered else 2)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        self.setPen(pen)
        # Subtle fill when highlighted
        fill = QColor(self._color)
        fill.setAlpha(15 if is_hovered else 0)
        self.setBrush(fill)

    _CURSOR_MAP: dict[str | None, Qt.CursorShape] = {
        "top": Qt.CursorShape.SizeVerCursor,
        "bottom": Qt.CursorShape.SizeVerCursor,
        "left": Qt.CursorShape.SizeHorCursor,
        "right": Qt.CursorShape.SizeHorCursor,
        "tl": Qt.CursorShape.SizeFDiagCursor,
        "br": Qt.CursorShape.SizeFDiagCursor,
        "tr": Qt.CursorShape.SizeBDiagCursor,
        "bl": Qt.CursorShape.SizeBDiagCursor,
        None: Qt.CursorShape.ArrowCursor,
    }

    def _edge_at(self, pos: QPointF) -> str | None:
        """Return which edge or handle is near *pos*, or None."""
        rect = self.rect()
        tol = _EDGE_TOLERANCE
        hs = _HANDLE_SIZE / 2

        corners = [
            ("tl", rect.left(), rect.top()),
            ("tr", rect.right(), rect.top()),
            ("bl", rect.left(), rect.bottom()),
            ("br", rect.right(), rect.bottom()),
        ]
        for name, x, y in corners:
            if QRectF(x - hs, y - hs, _HANDLE_SIZE, _HANDLE_SIZE).contains(pos):
                return name

        edges = [
            ("top", abs(pos.y() - rect.top())),
            ("bottom", abs(pos.y() - rect.bottom())),
            ("left", abs(pos.x() - rect.left())),
            ("right", abs(pos.x() - rect.right())),
        ]
        return next((name for name, dist in edges if dist < tol), None)

    def _cursor_for(self, edge: str | None) -> Qt.CursorShape:
        return self._CURSOR_MAP.get(edge, Qt.CursorShape.ArrowCursor)

    # ------------------------------------------------------------------ #
    # Hover
    # ------------------------------------------------------------------ #

    def hoverMoveEvent(self, event):
        edge = self._edge_at(event.pos())
        self.setCursor(QCursor(self._cursor_for(edge)))
        self._update_pen(is_hovered=edge is not None)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self._update_pen(is_hovered=False)
        super().hoverLeaveEvent(event)

    # ------------------------------------------------------------------ #
    # Drag
    # ------------------------------------------------------------------ #

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            edge = self._edge_at(event.pos())
            if edge:
                self._drag_edge = edge
                self._drag_start_pos = event.scenePos()
                self._drag_start_frame = dict(self._frame)
                self._drag_start_values = {
                    "top": self._frame["top"],
                    "bottom": self._frame["bottom"],
                    "left": self._frame["left"],
                    "right": self._frame["right"],
                }
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self._drag_edge:
            super().mouseMoveEvent(event)
            return

        delta = event.scenePos() - self._drag_start_pos
        dx, dy = int(delta.x()), int(delta.y())

        _EDGE_LIMITS = {
            "top": ("top", dy, 0, lambda: self._frame["bottom"] - 20),
            "bottom": ("bottom", dy, lambda: self._frame["top"] + 20, None),
            "left": ("left", dx, 0, lambda: self._frame["right"] - 20),
            "right": ("right", dx, lambda: self._frame["left"] + 20, None),
        }
        corner_map = {
            "tl": ("top", "left"),
            "tr": ("top", "right"),
            "bl": ("bottom", "left"),
            "br": ("bottom", "right"),
        }
        keys = corner_map.get(self._drag_edge, (self._drag_edge,))
        for key in keys:
            limits = _EDGE_LIMITS[key]
            _, delta_px, lo, hi = limits
            new_val = self._drag_start_values[key] + delta_px
            lo_val = lo() if callable(lo) else lo
            hi_val = hi() if callable(hi) else hi
            if hi_val is None:
                new_val = max(lo_val, new_val)
            else:
                new_val = max(lo_val, min(new_val, hi_val))
            self._frame[key] = new_val

        self._update_rect()
        if self._on_changed:
            self._on_changed(self._frame)
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag_edge:
            previous_frame = self._drag_start_frame
            self._drag_edge = None
            self._drag_start_pos = None
            self._drag_start_frame = None
            if self._on_released:
                self._on_released(self._frame, previous_frame)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------ #
    # Selection
    # ------------------------------------------------------------------ #

    def set_highlighted(self, highlighted: bool):
        pen = self.pen()
        pen.setWidth(4 if highlighted else 2)
        color = QColor(self._color)
        if not highlighted:
            color.setAlpha(120)
        pen.setColor(color)
        self.setPen(pen)

        fill = QColor(self._color)
        fill.setAlpha(25 if highlighted else 0)
        self.setBrush(fill)

    def frame_data(self) -> dict:
        return self._frame

    # ------------------------------------------------------------------ #
    # Corner handles (painted on top)
    # ------------------------------------------------------------------ #

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        # Draw corner handles
        rect = self.rect()
        hs = _HANDLE_SIZE
        handle_color = QColor(self._color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(handle_color)

        for x, y in [
            (rect.left(), rect.top()),
            (rect.right() - hs, rect.top()),
            (rect.left(), rect.bottom() - hs),
            (rect.right() - hs, rect.bottom() - hs),
        ]:
            painter.drawRect(QRectF(x, y, hs, hs))
