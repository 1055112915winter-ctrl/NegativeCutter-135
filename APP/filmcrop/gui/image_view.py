"""
NegativeCutter image viewer built on QGraphicsView + QGraphicsScene.
Dark canvas, metallic frame overlays, zoom + pan + drag.
"""

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QImage, QPixmap, QPen, QColor
from PyQt6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsTextItem,
)

import numpy as np
from PIL import Image

from filmcrop.gui.frame_item import DraggableFrameItem
from filmcrop.gui.theme import CANVAS_BG, BORDER_WARM, frame_color, TEXT_PRIMARY

Image.MAX_IMAGE_PIXELS = None


def _normalize_16bit_array(arr: np.ndarray) -> Image.Image:
    arr = np.asarray(arr)
    if arr.ndim == 3 and arr.shape[2] >= 3:
        display = arr[:, :, :3]
        mode = "RGB"
    elif arr.ndim == 3 and arr.shape[2] == 1:
        display = arr[:, :, 0]
        mode = "L"
    elif arr.ndim == 2:
        display = arr
        mode = "L"
    else:
        raise ValueError(f"Unsupported image array shape: {arr.shape}")

    display = np.clip(display, 0, 65535).astype(np.float32)
    display = (display / 65535.0 * 255.0).astype(np.uint8)
    return Image.fromarray(display, mode=mode)


class ImageView(QGraphicsView):
    """Zoomable/pannable image canvas with draggable frame overlay support."""

    ZOOM_BTN_STYLE = (
        "QPushButton {"
        "  background: rgba(40,40,40,180); color: #ddd; border: 1px solid #555;"
        "  border-radius: 3px; font-size: 14px; font-weight: bold;"
        "  padding: 2px 8px; min-width: 24px; max-width: 24px; min-height: 22px; max-height: 22px;"
        "}"
        "QPushButton:hover { background: rgba(60,60,60,200); border-color: #999; }"
        "QPushButton:pressed { background: rgba(80,80,80,220); }"
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        # Manual pan replaces ScrollHandDrag to avoid gesture conflicts.
        self._panning = False
        self._last_pan_pos = None
        self._last_pinch_value = 0.0

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # Dark canvas background
        self.setStyleSheet(
            f"background-color: {CANVAS_BG}; border: 1px solid {BORDER_WARM}; border-radius: 4px;"
        )

        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)

        self._zoom = 1.0
        self._min_zoom = 0.05
        self._max_zoom = 8.0

        self._frame_items: list[DraggableFrameItem] = []
        self._label_items: list[QGraphicsTextItem] = []
        self._selected_idx = -1
        self._on_frame_changed = None
        self._on_frame_released = None

        from PyQt6.QtWidgets import QPushButton

        self._zoom_in_btn = QPushButton("+", self)
        self._zoom_in_btn.setStyleSheet(self.ZOOM_BTN_STYLE)
        self._zoom_in_btn.setToolTip("放大 (] / +)")
        self._zoom_in_btn.clicked.connect(self.zoom_in)

        self._zoom_out_btn = QPushButton("−", self)
        self._zoom_out_btn.setStyleSheet(self.ZOOM_BTN_STYLE)
        self._zoom_out_btn.setToolTip("缩小 ([ / -)")
        self._zoom_out_btn.clicked.connect(self.zoom_out)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        margin = 8
        self._zoom_out_btn.move(margin, self.height() - self._zoom_out_btn.height() - margin)
        self._zoom_in_btn.move(
            margin + self._zoom_out_btn.width() + 4,
            self.height() - self._zoom_in_btn.height() - margin,
        )

    # ------------------------------------------------------------------ #
    # Image loading
    # ------------------------------------------------------------------ #

    def load_image(self, path: str):
        """Load an image file and display it."""
        self.clear_overlays()
        with Image.open(path) as img:
            if img.mode in ("I;16", "I;16B", "I;16N", "I"):
                pil_img = _normalize_16bit_array(np.array(img))
            elif img.mode in ("RGB", "RGBA", "L"):
                pil_img = img.copy()
            else:
                pil_img = img.convert("RGB")

        qimg = self._pil_to_qimage(pil_img)
        pixmap = QPixmap.fromImage(qimg)
        self._pixmap_item.setPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))
        self._zoom = 1.0
        self.resetTransform()
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def clear_image(self):
        """Clear the current image and all overlays."""
        self.clear_overlays()
        self._pixmap_item.setPixmap(QPixmap())
        self._scene.setSceneRect(QRectF())
        self._zoom = 1.0
        self.resetTransform()

    @staticmethod
    def _pil_to_qimage(img: Image.Image) -> QImage:
        data = img.tobytes() if img.mode == "L" else img.tobytes("raw", img.mode)
        bytes_per_line = img.width * ({"L": 1, "RGBA": 4, "RGB": 3}.get(img.mode, 3))
        fmt = {
            "L": QImage.Format.Format_Grayscale8,
            "RGBA": QImage.Format.Format_RGBA8888,
            "RGB": QImage.Format.Format_RGB888,
        }[img.mode]
        return QImage(data, img.width, img.height, bytes_per_line, fmt)

    # ------------------------------------------------------------------ #
    # Frame overlays
    # ------------------------------------------------------------------ #

    def set_frame_overlays(self, frames: list, selected_idx: int = 0,
                           on_frame_changed=None, on_frame_released=None):
        """Draw draggable rectangles for each frame boundary."""
        self.clear_overlays()
        self._selected_idx = selected_idx
        self._on_frame_changed = on_frame_changed
        self._on_frame_released = on_frame_released or on_frame_changed
        for i, frame in enumerate(frames):
            item = DraggableFrameItem(
                frame, i,
                on_changed=lambda f, idx=i: self._notify_frame_changed(idx),
                on_released=lambda f, previous, idx=i: self._notify_frame_released(idx, previous),
            )
            self._scene.addItem(item)
            self._frame_items.append(item)

            label = QGraphicsTextItem(f"帧{i + 1}")
            label.setDefaultTextColor(frame_color(i))
            label.setPos(frame["left"] + 4, frame["top"] + 4)
            # Make labels more readable on dark background
            label.setZValue(10)
            self._scene.addItem(label)
            self._label_items.append(label)

        self.select_frame(selected_idx)

    def _notify_frame_changed(self, idx: int):
        if self._on_frame_changed:
            self._on_frame_changed(idx)

    def _notify_frame_released(self, idx: int, previous_frame: dict | None):
        if self._on_frame_released:
            self._on_frame_released(
                idx,
                released=True,
                previous_frame=previous_frame,
            )

    def clear_overlays(self):
        for item in self._frame_items:
            self._scene.removeItem(item)
        for item in self._label_items:
            self._scene.removeItem(item)
        self._frame_items.clear()
        self._label_items.clear()
        self._selected_idx = -1
        self._on_frame_changed = None
        self._on_frame_released = None

    def select_frame(self, idx: int):
        """Highlight the selected frame, dim others."""
        self._selected_idx = idx
        for i, item in enumerate(self._frame_items):
            item.set_highlighted(i == idx)
            label = self._label_items[i]
            color = frame_color(i)
            if i != idx:
                color = QColor(color)
                color.setAlpha(120)
            label.setDefaultTextColor(color)
            label.setZValue(11 if i == idx else 10)

    def update_frame_geometry(self, idx: int):
        """Refresh the rect and label for a single frame after external edit."""
        if 0 <= idx < len(self._frame_items):
            self._frame_items[idx]._update_rect()
            label = self._label_items[idx]
            frame = self._frame_items[idx].frame_data()
            label.setPos(frame["left"] + 4, frame["top"] + 4)

    # ------------------------------------------------------------------ #
    # Pan (manual, replaces ScrollHandDrag to avoid gesture conflicts)
    # ------------------------------------------------------------------ #

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.pos())
            # Pan on empty canvas or pixmap; frame items handled by super
            if item is None or item is self._pixmap_item:
                self._panning = True
                self._last_pan_pos = event.pos()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning and self._last_pan_pos is not None:
            delta = event.pos() - self._last_pan_pos
            self._last_pan_pos = event.pos()
            self.translate(delta.x(), delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._panning:
            self._panning = False
            self._last_pan_pos = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------ #
    # Zoom
    # ------------------------------------------------------------------ #

    def event(self, event):
        """Intercept native gesture events (trackpad pinch) before the base class."""
        import PyQt6.QtCore as _QtCore
        from PyQt6.QtGui import QNativeGestureEvent

        if isinstance(event, QNativeGestureEvent):
            gesture_type = event.gestureType()
            if gesture_type == _QtCore.Qt.NativeGestureType.ZoomNativeGesture:
                self._apply_pinch(event.value())
                event.accept()
                return True
            elif gesture_type in (
                _QtCore.Qt.NativeGestureType.BeginNativeGesture,
                _QtCore.Qt.NativeGestureType.EndNativeGesture,
            ):
                if gesture_type == _QtCore.Qt.NativeGestureType.BeginNativeGesture:
                    self._last_pinch_value = 0.0
                event.accept()
                return True
        return super().event(event)

    def wheelEvent(self, event):
        # Two-finger trackpad scroll → pan
        pixel = event.pixelDelta()
        if not pixel.isNull():
            self.translate(pixel.x(), pixel.y())
            event.accept()
            return

        # Mouse wheel → zoom
        delta = event.angleDelta().y()
        if delta == 0:
            event.accept()
            return
        factor = 1.15 if delta > 0 else 1 / 1.15
        self._apply_zoom_factor(factor)
        event.accept()

    def _apply_pinch(self, value: float):
        """Apply a pinch magnification step."""
        prev = getattr(self, '_last_pinch_value', 0.0)
        self._last_pinch_value = value
        delta = value - prev
        if abs(delta) < 0.001:
            return
        factor = 1.0 + delta
        if factor <= 0:
            return
        self._apply_zoom_factor(factor)

    def _apply_zoom_factor(self, factor: float):
        new_zoom = self._zoom * factor
        if new_zoom < self._min_zoom:
            new_zoom = self._min_zoom
        elif new_zoom > self._max_zoom:
            new_zoom = self._max_zoom
        if new_zoom != self._zoom:
            effective = new_zoom / self._zoom
            self._zoom = new_zoom
            self.scale(effective, effective)

    def zoom_in(self):
        self._apply_zoom_factor(1.25)

    def zoom_out(self):
        self._apply_zoom_factor(1 / 1.25)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_BracketRight:
            self.zoom_in()
        elif event.key() == Qt.Key.Key_BracketLeft:
            self.zoom_out()
        elif event.key() == Qt.Key.Key_Minus or event.key() == Qt.Key.Key_Underscore:
            self.zoom_out()
        elif event.key() == Qt.Key.Key_Equal or event.key() == Qt.Key.Key_Plus:
            self.zoom_in()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def image_size(self) -> tuple:
        pm = self._pixmap_item.pixmap()
        if pm.isNull():
            return 0, 0
        return pm.width(), pm.height()

    def reset_zoom(self):
        self._zoom = 1.0
        self.resetTransform()
        rect = self._scene.sceneRect()
        if rect.width() > 0 and rect.height() > 0:
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
