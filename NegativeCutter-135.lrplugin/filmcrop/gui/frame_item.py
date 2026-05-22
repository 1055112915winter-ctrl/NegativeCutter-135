"""
Draggable frame boundary overlay for QGraphicsScene.
Each frame is a rectangle whose edges can be dragged to adjust crop boundaries.
"""

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPen, QColor, QCursor
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsItem

_EDGE_TOLERANCE = 8.0  # pixels in scene coords


class DraggableFrameItem(QGraphicsRectItem):
    """
    A frame rectangle with draggable edges.
    Emits boundary changes via a callback.
    """

    def __init__(self, frame: dict, color: QColor, on_changed, on_released=None, parent=None):
        super().__init__(parent)
        self._frame = frame
        self._color = color
        self._on_changed = on_changed
        self._on_released = on_released
        self._drag_edge = None  # 'top', 'bottom', 'left', 'right'
        self._drag_start_pos = None
        self._drag_start_value = 0

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
        pen.setWidth(3 if is_hovered else 1)
        self.setPen(pen)
        self.setBrush(Qt.BrushStyle.NoBrush)

    def _edge_at(self, pos: QPointF):
        """Return which edge is near *pos* (scene coords), or None."""
        rect = self.rect()
        tol = _EDGE_TOLERANCE
        if abs(pos.y() - rect.top()) < tol:
            return "top"
        if abs(pos.y() - rect.bottom()) < tol:
            return "bottom"
        if abs(pos.x() - rect.left()) < tol:
            return "left"
        if abs(pos.x() - rect.right()) < tol:
            return "right"
        return None

    # ------------------------------------------------------------------ #
    # Hover
    # ------------------------------------------------------------------ #

    def hoverMoveEvent(self, event):
        edge = self._edge_at(event.pos())
        if edge in ("top", "bottom"):
            self.setCursor(QCursor(Qt.CursorShape.SizeVerCursor))
        elif edge in ("left", "right"):
            self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
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
                self._drag_start_value = {
                    "top": self._frame["top"],
                    "bottom": self._frame["bottom"],
                    "left": self._frame["left"],
                    "right": self._frame["right"],
                }[edge]
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_edge:
            delta = event.scenePos() - self._drag_start_pos
            if self._drag_edge == "top":
                new_val = self._drag_start_value + int(delta.y())
                new_val = max(0, min(new_val, self._frame["bottom"] - 20))
                self._frame["top"] = new_val
            elif self._drag_edge == "bottom":
                new_val = self._drag_start_value + int(delta.y())
                new_val = max(self._frame["top"] + 20, new_val)
                self._frame["bottom"] = new_val
            elif self._drag_edge == "left":
                new_val = self._drag_start_value + int(delta.x())
                new_val = max(0, min(new_val, self._frame["right"] - 20))
                self._frame["left"] = new_val
            elif self._drag_edge == "right":
                new_val = self._drag_start_value + int(delta.x())
                new_val = max(self._frame["left"] + 20, new_val)
                self._frame["right"] = new_val

            self._update_rect()
            if self._on_changed:
                self._on_changed(self._frame)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_edge:
            self._drag_edge = None
            self._drag_start_pos = None
            if self._on_released:
                self._on_released(self._frame)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------ #
    # Selection
    # ------------------------------------------------------------------ #

    def set_highlighted(self, highlighted: bool):
        pen = self.pen()
        pen.setWidth(4 if highlighted else 1)
        color = QColor(self._color)
        if not highlighted:
            color.setAlpha(100)
        pen.setColor(color)
        self.setPen(pen)

    def frame_data(self) -> dict:
        """Return the underlying frame dict."""
        return self._frame
