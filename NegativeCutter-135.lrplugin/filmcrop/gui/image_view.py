"""
FilmCrop image viewer built on QGraphicsView + QGraphicsScene.
Supports zoom (wheel), pan (middle-drag), and high-resolution TIFF/JPEG/PNG/DNG.
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

Image.MAX_IMAGE_PIXELS = None

_COLORS = [
    QColor(255, 68, 68),    # red
    QColor(68, 255, 68),    # green
    QColor(68, 68, 255),    # blue
    QColor(255, 255, 68),   # yellow
    QColor(255, 68, 255),   # magenta
    QColor(68, 255, 255),   # cyan
]


class ImageView(QGraphicsView):
    """Zoomable/pannable image canvas with draggable frame overlay support."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)

        self._zoom = 1.0
        self._min_zoom = 0.1
        self._max_zoom = 4.0

        self._frame_items: list[DraggableFrameItem] = []
        self._label_items: list[QGraphicsTextItem] = []
        self._selected_idx = -1
        self._on_frame_changed = None  # callback(frame)

    # ------------------------------------------------------------------ #
    # Image loading
    # ------------------------------------------------------------------ #

    def load_image(self, path: str):
        """Load an image file and display it."""
        self.clear_overlays()
        img: Image.Image = Image.open(path)
        if img.mode in ("I;16", "I;16B", "I;16N", "I"):
            arr_16 = np.array(img)
            arr = ((arr_16.astype(np.float32) / 65535.0) * 255).astype(np.uint8)
            img = Image.fromarray(arr, mode="L")
        elif img.mode not in ("RGB", "RGBA", "L"):
            img = img.convert("RGB")

        if img.mode == "L":
            data = img.tobytes()
            qimg = QImage(data, img.width, img.height, img.width, QImage.Format.Format_Grayscale8)
        elif img.mode == "RGBA":
            data = img.tobytes("raw", "RGBA")
            qimg = QImage(data, img.width, img.height, img.width * 4, QImage.Format.Format_RGBA8888)
        else:
            data = img.tobytes("raw", "RGB")
            qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)

        pixmap = QPixmap.fromImage(qimg)
        self._pixmap_item.setPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))
        self._zoom = 1.0
        self.resetTransform()
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    # ------------------------------------------------------------------ #
    # Frame overlays
    # ------------------------------------------------------------------ #

    def set_frame_overlays(self, frames: list, selected_idx: int = 0,
                           on_frame_changed=None, on_frame_released=None):
        """Draw draggable rectangles for each frame boundary."""
        self.clear_overlays()
        self._selected_idx = selected_idx
        self._on_frame_changed = on_frame_changed
        for i, frame in enumerate(frames):
            color = _COLORS[i % len(_COLORS)]
            item = DraggableFrameItem(
                frame, color,
                on_changed=lambda f, idx=i: self._notify_frame_changed(idx),
                on_released=lambda f, idx=i: self._notify_frame_released(idx),
            )
            self._scene.addItem(item)
            self._frame_items.append(item)

            label = QGraphicsTextItem(f"帧{i + 1}")
            label.setDefaultTextColor(color)
            label.setPos(frame["left"] + 4, frame["top"] + 4)
            self._scene.addItem(label)
            self._label_items.append(label)

        self.select_frame(selected_idx)

    def _notify_frame_changed(self, idx: int):
        if self._on_frame_changed:
            self._on_frame_changed(idx)

    def _notify_frame_released(self, idx: int):
        # Forward to the same callback channel; main_window will push undo on release
        if self._on_frame_changed:
            self._on_frame_changed(idx, released=True)

    def clear_overlays(self):
        for item in self._frame_items:
            self._scene.removeItem(item)
        for item in self._label_items:
            self._scene.removeItem(item)
        self._frame_items.clear()
        self._label_items.clear()
        self._selected_idx = -1
        self._on_frame_changed = None

    def select_frame(self, idx: int):
        """Highlight the selected frame, dim others."""
        self._selected_idx = idx
        for i, item in enumerate(self._frame_items):
            item.set_highlighted(i == idx)
            label = self._label_items[i]
            color = _COLORS[i % len(_COLORS)]
            if i != idx:
                color = QColor(color)
                color.setAlpha(120)
            label.setDefaultTextColor(color)

    def update_frame_geometry(self, idx: int):
        """Refresh the rect and label for a single frame after external edit."""
        if 0 <= idx < len(self._frame_items):
            self._frame_items[idx]._update_rect()
            label = self._label_items[idx]
            frame = self._frame_items[idx].frame_data()
            label.setPos(frame["left"] + 4, frame["top"] + 4)

    # ------------------------------------------------------------------ #
    # Zoom
    # ------------------------------------------------------------------ #

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1 / 1.15
        new_zoom = self._zoom * factor
        if self._min_zoom <= new_zoom <= self._max_zoom:
            self._zoom = new_zoom
            self.scale(factor, factor)
        event.accept()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def image_size(self) -> tuple:
        """Return (width, height) of the loaded image, or (0, 0)."""
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
