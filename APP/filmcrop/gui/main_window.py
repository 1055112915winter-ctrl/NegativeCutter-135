"""
NegativeCutter Standalone GUI - Main Window (PyQt6).
Darkroom precision-instrument theme, fully self-contained.

Layout:
  ┌──────────────────────────────┬─────────────┐
  │  Image canvas (ImageView)    │ Frame list  │
  │  with zoom + pan + drag      │ + coords    │
  │                              │ + controls  │
  └──────────────────────────────┴─────────────┘
  Status bar: image info / detection perf / zoom level
"""

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from filmcrop.gui.image_view import ImageView
from filmcrop.gui.export_dialog import ExportDialog
from filmcrop.gui.logo import create_app_icon, create_header_logo_pixmap

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
_MAX_UNDO_STEPS = 50
_MIN_FRAME_SIZE = 20

_FORMAT_FOR_SUFFIX = {
    ".tif": "TIFF",
    ".tiff": "TIFF",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
}


def _color_space_from_icc(icc_profile: bytes | None) -> str:
    if not icc_profile:
        return "色彩空间未知"
    text = icc_profile.decode("latin-1", errors="ignore").lower()
    if "adobe" in text:
        return "Adobe RGB"
    if "srgb" in text:
        return "sRGB"
    return "保留原始"


def _srgb_icc_profile() -> bytes:
    from PIL import ImageCms

    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def _bit_depth_from_image(img) -> int:
    tags = getattr(img, "tag_v2", None)
    bits = tags.get(258) if tags is not None else None
    if isinstance(bits, (tuple, list)) and bits:
        return max(int(value) for value in bits)
    if isinstance(bits, int):
        return bits
    if img.mode in ("I;16", "I;16B", "I;16N", "I"):
        return 16
    return 8


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NegativeCutter")
        self.setMinimumSize(1280, 900)
        self.setWindowIcon(create_app_icon())

        # State
        self._image_path: str | None = None
        self._frames: list = []
        self._debug_info: dict | None = None
        self._crop_angle: float = 0.0
        self._is_horizontal = True
        self._undo_stack: list = []
        self._redo_stack: list = []
        self._api_thread = None
        self._api_running = False
        self._api_request_count = 0
        self._api_poll_timer = QTimer(self)
        self._api_poll_timer.timeout.connect(self._on_api_poll)
        self._img_w = 0
        self._img_h = 0
        self._dng_tmp_path: str | None = None

        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
        self._build_shortcuts()

    # ------------------------------------------------------------------ #
    # UI helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _make_card() -> QWidget:
        """Create a styled card container for panel sections."""
        card = QWidget()
        card.setObjectName("card")
        return card

    @staticmethod
    def _section_title(text: str) -> QLabel:
        """Create a styled section title label."""
        lbl = QLabel(text)
        lbl.setObjectName("heading")
        return lbl

    @staticmethod
    def _hint_label(text: str) -> QLabel:
        """Create a styled hint/description label."""
        lbl = QLabel(text)
        lbl.setObjectName("hint")
        return lbl

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self._splitter)

        # --- Left: image view ---
        self._image_view = ImageView()
        self._splitter.addWidget(self._image_view)
        self._splitter.setStretchFactor(0, 3)

        # --- Right: control panel (scrollable) ---
        self._panel = QWidget()
        self._panel.setObjectName("panel")
        panel_layout = QVBoxLayout(self._panel)
        panel_layout.setContentsMargins(18, 18, 18, 18)
        panel_layout.setSpacing(12)

        # Header with logo
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        logo_lbl = QLabel()
        logo_lbl.setPixmap(create_header_logo_pixmap(48))
        logo_lbl.setFixedSize(48, 48)
        header_layout.addWidget(logo_lbl)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        header_text = QLabel("NEGATIVE CUTTER")
        header_text.setObjectName("wordmark")
        brand_text.addWidget(header_text)
        header_subtitle = QLabel("PRECISION FRAME TOOL")
        header_subtitle.setObjectName("brandSubtitle")
        brand_text.addWidget(header_subtitle)
        header_layout.addLayout(brand_text)
        header_layout.addStretch()
        panel_layout.addLayout(header_layout)

        # ── Card 1: 检测设置 ──
        card1 = self._make_card()
        c1 = QVBoxLayout(card1)
        c1.setContentsMargins(15, 14, 15, 15)
        c1.setSpacing(10)

        c1.addWidget(self._section_title("DETECTION"))
        c1.addWidget(QLabel("预期帧数"))
        self._frame_count_spin = QSpinBox()
        self._frame_count_spin.setRange(0, 20)
        self._frame_count_spin.setValue(6)
        self._frame_count_spin.setToolTip("0 = 自动检测")
        c1.addWidget(self._frame_count_spin)

        self._btn_detect = QPushButton("检测帧 (Ctrl+D)")
        self._btn_detect.setObjectName("primary")
        self._btn_detect.setEnabled(False)
        self._btn_detect.clicked.connect(self._on_detect)
        c1.addWidget(self._btn_detect)

        panel_layout.addWidget(card1)

        # ── Card 2: 帧列表 + 坐标编辑 ──
        card2 = self._make_card()
        c2 = QVBoxLayout(card2)
        c2.setContentsMargins(15, 14, 15, 15)
        c2.setSpacing(10)

        c2.addWidget(self._section_title("FRAMES"))
        self._frame_list = QListWidget()
        self._frame_list.setMinimumHeight(120)
        self._frame_list.setMaximumHeight(240)
        self._frame_list.currentRowChanged.connect(self._on_frame_selected)
        c2.addWidget(self._frame_list)

        c2.addWidget(self._section_title("COORDINATES"))
        self._coord_box = QWidget()
        self._coord_box.setObjectName("coordBox")
        coord_grid = QGridLayout(self._coord_box)
        coord_grid.setContentsMargins(0, 0, 0, 0)
        coord_grid.setSpacing(10)
        coord_grid.setColumnStretch(1, 1)
        coord_grid.setColumnStretch(3, 1)
        self._coord_spins = {}
        positions = (
            (("上", "top"), ("左", "left")),
            (("下", "bottom"), ("右", "right")),
        )
        for row_idx, (col_a, col_b) in enumerate(positions):
            for col_idx, (label_text, key) in enumerate((col_a, col_b)):
                lbl = QLabel(f"{label_text}:")
                lbl.setFixedWidth(40)
                spin = QSpinBox()
                spin.setRange(0, 99999)
                spin.setEnabled(False)
                spin.valueChanged.connect(lambda val, k=key: self._on_spinbox_changed(k, val))
                self._coord_spins[key] = spin
                base = col_idx * 2
                coord_grid.addWidget(lbl, row_idx, base)
                coord_grid.addWidget(spin, row_idx, base + 1)
        c2.addWidget(self._coord_box)
        self._coord_box.setEnabled(False)

        add_del_layout = QHBoxLayout()
        add_del_layout.setSpacing(8)
        self._btn_add_frame = QPushButton("+ 添加")
        self._btn_add_frame.setEnabled(False)
        self._btn_add_frame.clicked.connect(self._on_add_frame)
        add_del_layout.addWidget(self._btn_add_frame)
        self._btn_del_frame = QPushButton("- 删除")
        self._btn_del_frame.setEnabled(False)
        self._btn_del_frame.clicked.connect(self._on_del_frame)
        add_del_layout.addWidget(self._btn_del_frame)
        c2.addLayout(add_del_layout)

        panel_layout.addWidget(card2)

        # ── Card 3: 全局调整 ──
        card3 = self._make_card()
        c3 = QVBoxLayout(card3)
        c3.setContentsMargins(15, 14, 15, 15)
        c3.setSpacing(10)

        c3.addWidget(self._section_title("ADJUSTMENT"))
        c3.addWidget(self._hint_label("统一扩张或收缩所有帧的边界"))

        adj_layout = QHBoxLayout()
        adj_layout.setSpacing(8)
        self._adj_dir = QComboBox()
        self._adj_dir.addItems(["全部", "上", "下", "左", "右"])
        adj_layout.addWidget(self._adj_dir)
        self._adj_px = QSpinBox()
        self._adj_px.setRange(-200, 200)
        self._adj_px.setValue(0)
        self._adj_px.setSuffix(" px")
        self._adj_px.setToolTip("正数 = 向外扩张，负数 = 向内收缩")
        adj_layout.addWidget(self._adj_px)
        self._btn_adj_apply = QPushButton("应用")
        self._btn_adj_apply.setEnabled(False)
        self._btn_adj_apply.clicked.connect(self._on_global_adjust)
        adj_layout.addWidget(self._btn_adj_apply)
        c3.addLayout(adj_layout)

        panel_layout.addWidget(card3)

        # ── Card 4: 导出 ──
        card4 = self._make_card()
        c4 = QVBoxLayout(card4)
        c4.setContentsMargins(15, 14, 15, 15)
        c4.setSpacing(10)

        c4.addWidget(self._section_title("OUTPUT"))

        self._btn_export_json = QPushButton("保存坐标数据")
        self._btn_export_json.setEnabled(False)
        self._btn_export_json.clicked.connect(self._on_export_json)
        self._btn_export_json.setToolTip("导出 JSON 坐标文件，供其他程序读取")
        c4.addWidget(self._btn_export_json)

        self._btn_export_xmp = QPushButton("保存裁切信息 (Lightroom)")
        self._btn_export_xmp.setEnabled(False)
        self._btn_export_xmp.clicked.connect(self._on_export_xmp)
        self._btn_export_xmp.setToolTip("导出 XMP 元数据，Lightroom 可直接读取")
        c4.addWidget(self._btn_export_xmp)

        self._btn_export_images = QPushButton("导出裁切图像")
        self._btn_export_images.setObjectName("primary")
        self._btn_export_images.setEnabled(False)
        self._btn_export_images.clicked.connect(self._on_export_images)
        c4.addWidget(self._btn_export_images)

        panel_layout.addWidget(card4)
        panel_layout.addStretch()

        # Wrap panel in scroll area so it never gets squashed
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setMinimumWidth(390)
        scroll.setWidget(self._panel)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._splitter.addWidget(scroll)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([860, 390])

    def _build_menu(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("文件 (&F)")
        open_act = QAction("打开 (&O)...", self)
        open_act.setShortcut(QKeySequence.StandardKey.Open)
        open_act.triggered.connect(self._on_open)
        file_menu.addAction(open_act)
        file_menu.addSeparator()

        export_menu = file_menu.addMenu("导出 (&E)")
        export_json_act = QAction("坐标数据 (&J)", self)
        export_json_act.setShortcut(QKeySequence("Ctrl+J"))
        export_json_act.triggered.connect(self._on_export_json)
        export_menu.addAction(export_json_act)

        export_xmp_act = QAction("裁切信息 (Lightroom) (&X)", self)
        export_xmp_act.setShortcut(QKeySequence("Ctrl+Shift+J"))
        export_xmp_act.triggered.connect(self._on_export_xmp)
        export_menu.addAction(export_xmp_act)

        export_menu.addSeparator()
        export_images_act = QAction("裁切图像 (&C)...", self)
        export_images_act.setShortcut(QKeySequence("Ctrl+Shift+E"))
        export_images_act.triggered.connect(self._on_export_images)
        export_menu.addAction(export_images_act)

        file_menu.addSeparator()
        exit_act = QAction("退出 (&X)", self)
        exit_act.setShortcut(QKeySequence.StandardKey.Quit)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        view_menu = menu_bar.addMenu("视图 (&V)")
        reset_zoom_act = QAction("重置缩放 (&R)", self)
        reset_zoom_act.setShortcut("Ctrl+0")
        reset_zoom_act.triggered.connect(self._image_view.reset_zoom)
        view_menu.addAction(reset_zoom_act)

        tools_menu = menu_bar.addMenu("工具 (&T)")
        detect_act = QAction("检测帧 (&D)", self)
        detect_act.setShortcut(QKeySequence("Ctrl+D"))
        detect_act.triggered.connect(self._on_detect)
        tools_menu.addAction(detect_act)
        tools_menu.addSeparator()
        export_tuning_act = QAction("导出调优数据...", self)
        export_tuning_act.triggered.connect(self._on_export_tuning)
        tools_menu.addAction(export_tuning_act)
        tools_menu.addSeparator()
        self._act_start_api = QAction("启动 API 服务器", self)
        self._act_start_api.triggered.connect(self._on_start_api)
        tools_menu.addAction(self._act_start_api)
        self._act_stop_api = QAction("停止 API 服务器", self)
        self._act_stop_api.setEnabled(False)
        self._act_stop_api.triggered.connect(self._on_stop_api)
        tools_menu.addAction(self._act_stop_api)

    def _build_toolbar(self):
        tb = QToolBar("Main")
        self.addToolBar(tb)
        tb.setMovable(False)

        btn_open = QToolButton()
        btn_open.setText("打开")
        btn_open.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        btn_open.clicked.connect(self._on_open)
        tb.addWidget(btn_open)

        tb.addSeparator()

        btn_reset = QToolButton()
        btn_reset.setText("重置缩放")
        btn_reset.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        btn_reset.clicked.connect(self._image_view.reset_zoom)
        tb.addWidget(btn_reset)

    def _build_statusbar(self):
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("就绪 – 请打开扫描图像文件")

    def _build_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+D"), self, activated=self._on_detect)
        QShortcut(QKeySequence("Ctrl+J"), self, activated=self._on_export_json)
        QShortcut(QKeySequence("Ctrl+Shift+J"), self, activated=self._on_export_xmp)
        QShortcut(QKeySequence("Ctrl+Shift+E"), self, activated=self._on_export_images)
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self._undo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, activated=self._redo)

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #

    def _on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开扫描图像", "",
            "Images (*.tif *.tiff *.jpg *.jpeg *.png *.dng);;All Files (*)",
        )
        if not path:
            return
        self._load_image(path)

    def _load_image(self, path: str):
        self._cleanup_dng_tmp()

        suffix = Path(path).suffix.lower()
        progress = QProgressDialog("正在打开图像...", "取消", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()
        QApplication.processEvents()

        try:
            if suffix == ".dng":
                source_fmt, bit_depth = self._load_dng(path, progress)
            else:
                source_fmt, bit_depth = self._load_standard_image(path, progress)
        except Exception as e:
            self._status.showMessage(f"图像读取失败: {e}")
            self._reset_image_state()
            return
        finally:
            progress.close()

        self._image_path = path
        self._clear_edit_history()
        self._source_fmt = source_fmt
        self._source_bit_depth = bit_depth
        self._btn_export_json.setText(
            "导出原始 DNG 坐标" if suffix == ".dng" else "保存坐标数据"
        )
        self._img_w, self._img_h = self._image_view.image_size()
        self._is_horizontal = self._img_w >= self._img_h
        loader_note = f" ({self._dng_loader})" if suffix == ".dng" else ""
        self._status.showMessage(
            f"{Path(path).name}  {self._img_w}×{self._img_h}  {bit_depth}bit{loader_note}"
        )
        self._btn_detect.setEnabled(True)
        self._frames = []
        for key, max_val in (("top", self._img_h), ("bottom", self._img_h),
                             ("left", self._img_w), ("right", self._img_w)):
            self._coord_spins[key].setMaximum(max_val)
        self._update_frame_list()
        self._update_export_buttons()

    def _cleanup_dng_tmp(self):
        tmp = self._dng_tmp_path
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
        self._dng_tmp_path = None

    def _reset_image_state(self):
        self._cleanup_dng_tmp()
        self._image_path = None
        self._btn_export_json.setText("保存坐标数据")
        self._img_w = self._img_h = 0
        self._frames = []
        self._image_view.clear_image()
        self._clear_edit_history()
        self._btn_detect.setEnabled(False)
        self._update_frame_list()
        self._update_export_buttons()

    def _load_dng(self, path: str, progress: QProgressDialog) -> tuple[str, int]:
        from filmcrop.detector import load_dng_preview_array
        from filmcrop._vendor import tifffile
        from PIL import Image as PILImage

        progress.setLabelText("正在解码 DNG...")
        QApplication.processEvents()
        arr, loader, bit_depth = load_dng_preview_array(path)
        progress.setLabelText(f"正在生成预览 ({loader})...")
        QApplication.processEvents()

        fd, tmp_path = tempfile.mkstemp(suffix=".tif", prefix="negativecutter_dng_")
        os.close(fd)
        self._dng_tmp_path = tmp_path
        if arr.ndim == 3 and arr.shape[2] >= 3:
            rgb = arr[:, :, :3]
            if bit_depth > 8:
                icc_profile = _srgb_icc_profile()
                tifffile.imwrite(
                    tmp_path,
                    rgb,
                    photometric="rgb",
                    metadata=None,
                    extratags=[(34675, "B", len(icc_profile), icc_profile, False)],
                )
            else:
                PILImage.fromarray(rgb.astype("uint8"), mode="RGB").save(tmp_path)
        elif arr.ndim == 3 and arr.shape[2] == 1:
            gray = arr[:, :, 0]
            if bit_depth > 8:
                tifffile.imwrite(tmp_path, gray, metadata=None)
            else:
                PILImage.fromarray(gray.astype("uint8"), mode="L").save(tmp_path)
        elif arr.ndim == 2:
            if bit_depth > 8:
                tifffile.imwrite(tmp_path, arr, metadata=None)
            else:
                PILImage.fromarray(arr.astype("uint8"), mode="L").save(tmp_path)
        else:
            raise ValueError(f"Unsupported DNG preview array shape: {arr.shape}")
        self._dng_loader = loader
        self._source_color_space = "sRGB"
        self._image_view.load_image(tmp_path)
        return "TIFF", bit_depth

    def _load_standard_image(self, path: str, progress: QProgressDialog) -> tuple[str, int]:
        from PIL import Image as PILImage

        progress.setLabelText("正在读取图像...")
        QApplication.processEvents()
        bit_depth = 8
        with PILImage.open(path) as img:
            bit_depth = _bit_depth_from_image(img)
            suffix = Path(path).suffix.lower()
            source_fmt = _FORMAT_FOR_SUFFIX.get(suffix, "TIFF")
            if source_fmt == "JPEG":
                q = img.info.get("quality")
                if isinstance(q, int) and 1 <= q <= 100:
                    self._source_jpeg_quality = q
            self._source_color_space = _color_space_from_icc(img.info.get("icc_profile"))

        progress.setLabelText("正在加载到画布...")
        QApplication.processEvents()
        self._image_view.load_image(path)
        return source_fmt, bit_depth

    def _on_detect(self):
        if not self._image_path:
            return
        expected = self._frame_count_spin.value()
        self._status.showMessage("正在检测帧边界...")
        QTimer.singleShot(50, lambda: self._do_detect(expected))

    def _do_detect(self, expected: int):
        if self._image_path is None:
            return
        from filmcrop.detector import analyze_image
        import traceback

        try:
            import psutil
            HAS_PSUTIL = True
        except ImportError:
            HAS_PSUTIL = False

        t0 = time.time()
        mem_before = psutil.Process().memory_info().rss / 1024 / 1024 if HAS_PSUTIL else 0
        try:
            result = analyze_image(
                self._image_path,
                expected_frames=expected,
                include_review_frames=True,
            )
            detected_frames = result.get("frames", [])
            self._debug_info = result.get("debug")
            self._crop_angle = result.get("cropAngle", 0.0)
        except Exception as e:
            tb = traceback.format_exc()
            self._status.showMessage(f"检测失败: {e}")
            QMessageBox.critical(
                self, "检测失败",
                f"帧检测过程中发生错误:\n\n{str(e)}\n\n{tb}"
            )
            return

        elapsed = time.time() - t0
        if not detected_frames:
            message = result.get("error", "未检测到可用帧，请调整预期帧数后重试。")
            self._status.showMessage(message)
            QMessageBox.warning(self, "检测失败", message)
            return

        self._clear_edit_history()
        self._frames = detected_frames
        mem_info = ""
        if HAS_PSUTIL:
            mem_after = psutil.Process().memory_info().rss / 1024 / 1024
            mem_info = f"  内存 +{mem_after - mem_before:.1f}MB"
        if result.get("needsReview"):
            self._status.showMessage(
                f"检测到 {len(self._frames)} 帧（低置信度，请检查并调整）  "
                f"耗时 {elapsed:.2f}s{mem_info}"
            )
        else:
            self._status.showMessage(f"检测到 {len(self._frames)} 帧  耗时 {elapsed:.2f}s{mem_info}")

        self._update_frame_list()
        self._update_export_buttons()
        self._draw_frame_overlays()

    def _update_frame_list(self):
        previous_row = self._frame_list.currentRow()
        self._frame_list.clear()
        for f in self._frames:
            w = f["right"] - f["left"]
            h = f["bottom"] - f["top"]
            label = f"帧 {f['index']}    {w}×{h} px"
            item = QListWidgetItem(label)
            item.setToolTip(
                f"Top: {f['top']}  Bottom: {f['bottom']}\n"
                f"Left: {f['left']}  Right: {f['right']}\n"
                f"相对: T={f.get('relativeTop', 0):.3f} B={f.get('relativeBottom', 1):.3f} "
                f"L={f.get('relativeLeft', 0):.3f} R={f.get('relativeRight', 1):.3f}"
            )
            self._frame_list.addItem(item)
        if self._frames:
            target_row = previous_row if previous_row >= 0 else 0
            self._frame_list.setCurrentRow(min(target_row, len(self._frames) - 1))
        else:
            self._frame_list.setCurrentRow(-1)

    def _update_export_buttons(self):
        has = bool(self._frames)
        self._btn_export_json.setEnabled(has)
        self._btn_export_xmp.setEnabled(has)
        self._btn_export_images.setEnabled(has)
        self._btn_add_frame.setEnabled(has)
        self._btn_del_frame.setEnabled(has and len(self._frames) > 1)
        self._coord_box.setEnabled(has)
        self._btn_adj_apply.setEnabled(has)
        for spin in self._coord_spins.values():
            spin.setEnabled(has)

    def _draw_frame_overlays(self):
        if not self._frames:
            self._image_view.clear_overlays()
            return
        sel = self._frame_list.currentRow()
        if sel < 0:
            sel = 0
        self._image_view.set_frame_overlays(
            self._frames, selected_idx=sel,
            on_frame_changed=self._on_canvas_frame_changed
        )
        self._sync_spinboxes(sel)

    def _on_frame_selected(self, row: int):
        if 0 <= row < len(self._frames):
            self._image_view.select_frame(row)
            self._btn_del_frame.setEnabled(len(self._frames) > 1)
            self._sync_spinboxes(row)

    def _sync_spinboxes(self, row: int):
        """Load current frame coords into spinboxes without triggering signals."""
        if not (0 <= row < len(self._frames)):
            return
        f = self._frames[row]
        for key, spin in self._coord_spins.items():
            spin.blockSignals(True)
            spin.setValue(f.get(key, 0))
            spin.blockSignals(False)

    def _on_spinbox_changed(self, key: str, val: int):
        """User edited a coordinate via spinbox."""
        row = self._frame_list.currentRow()
        if not (0 <= row < len(self._frames)):
            return
        self._push_undo()
        f = self._frames[row]
        f[key] = val
        if key in ("top", "left"):
            opposite = {"top": "bottom", "left": "right"}[key]
            f[opposite] = max(f[opposite], val + _MIN_FRAME_SIZE)
        else:
            opposite = {"bottom": "top", "right": "left"}[key]
            f[opposite] = min(f[opposite], val - _MIN_FRAME_SIZE)
        self._recalc_relative(f)
        self._update_frame_list()
        self._image_view.update_frame_geometry(row)
        self._sync_spinboxes(row)

    def _on_canvas_frame_changed(
        self,
        idx: int,
        released: bool = False,
        previous_frame: dict | None = None,
    ):
        """Callback from ImageView when user drags a frame edge."""
        if not (0 <= idx < len(self._frames)):
            return
        if released and previous_frame is not None:
            snapshot = [dict(f) for f in self._frames]
            snapshot[idx] = dict(previous_frame)
            self._recalc_relative(snapshot[idx])
            self._push_undo(snapshot)
        self._sync_spinboxes(idx)
        self._recalc_relative(self._frames[idx])
        self._update_frame_list()
        self._image_view.update_frame_geometry(idx)

    def _recalc_relative(self, f: dict):
        """Recompute relative coords after pixel change."""
        f["relativeTop"] = round(f["top"] / self._img_h, 6) if self._img_h else 0.0
        f["relativeBottom"] = round(f["bottom"] / self._img_h, 6) if self._img_h else 1.0
        f["relativeLeft"] = round(f["left"] / self._img_w, 6) if self._img_w else 0.0
        f["relativeRight"] = round(f["right"] / self._img_w, 6) if self._img_w else 1.0

    # ------------------------------------------------------------------ #
    # Undo / Redo
    # ------------------------------------------------------------------ #

    def _clear_edit_history(self):
        self._undo_stack.clear()
        self._redo_stack.clear()

    def _push_undo(self, snapshot: list[dict] | None = None):
        state = snapshot if snapshot is not None else self._frames
        self._undo_stack.append([dict(f) for f in state])
        if len(self._undo_stack) > _MAX_UNDO_STEPS:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _undo(self):
        if not self._undo_stack:
            return
        self._redo_stack.append([dict(f) for f in self._frames])
        self._frames = self._undo_stack.pop()
        self._update_frame_list()
        self._draw_frame_overlays()
        self._status.showMessage("已撤销")

    def _redo(self):
        if not self._redo_stack:
            return
        self._undo_stack.append([dict(f) for f in self._frames])
        self._frames = self._redo_stack.pop()
        self._update_frame_list()
        self._draw_frame_overlays()
        self._status.showMessage("已重做")

    # ------------------------------------------------------------------ #
    # Frame management
    # ------------------------------------------------------------------ #

    def _renumber_frames(self):
        for i, fr in enumerate(self._frames, start=1):
            fr["index"] = i

    def _on_add_frame(self):
        if not self._frames:
            return
        self._push_undo()
        row = self._frame_list.currentRow()
        if row < 0:
            row = len(self._frames) - 1
        cur = self._frames[row]
        if self._is_horizontal:
            mid = (cur["left"] + cur["right"]) // 2
            new_frame = {
                "index": 0, "top": cur["top"], "bottom": cur["bottom"],
                "left": mid, "right": cur["right"],
                "relativeTop": cur["relativeTop"], "relativeBottom": cur["relativeBottom"],
                "relativeLeft": round(mid / self._img_w, 6) if self._img_w else 0,
                "relativeRight": cur["relativeRight"],
            }
            cur["right"] = mid
            cur["relativeRight"] = round(mid / self._img_w, 6) if self._img_w else 0
        else:
            mid = (cur["top"] + cur["bottom"]) // 2
            new_frame = {
                "index": 0, "top": mid, "bottom": cur["bottom"],
                "left": cur["left"], "right": cur["right"],
                "relativeTop": round(mid / self._img_h, 6) if self._img_h else 0,
                "relativeBottom": cur["relativeBottom"],
                "relativeLeft": cur["relativeLeft"],
                "relativeRight": cur["relativeRight"],
            }
            cur["bottom"] = mid
            cur["relativeBottom"] = round(mid / self._img_h, 6) if self._img_h else 0

        self._frames.insert(row + 1, new_frame)
        self._renumber_frames()
        self._update_frame_list()
        self._frame_list.setCurrentRow(row + 1)
        self._draw_frame_overlays()
        self._status.showMessage(f"添加帧 {row + 2}")

    def _on_del_frame(self):
        if len(self._frames) <= 1:
            return
        self._push_undo()
        row = self._frame_list.currentRow()
        if row < 0:
            row = len(self._frames) - 1
        del self._frames[row]
        self._renumber_frames()
        self._update_frame_list()
        new_row = min(row, len(self._frames) - 1)
        self._frame_list.setCurrentRow(new_row)
        self._draw_frame_overlays()
        self._status.showMessage(f"删除帧 {row + 1}")

    def _on_global_adjust(self):
        """Expand or shrink all frame boundaries by a uniform amount."""
        if not self._frames:
            return
        direction = self._adj_dir.currentText()
        px = self._adj_px.value()
        if px == 0:
            return

        self._push_undo()
        for f in self._frames:
            if direction in ("全部", "上"):
                f["top"] = max(0, f["top"] - px)
            if direction in ("全部", "下"):
                f["bottom"] = min(self._img_h, f["bottom"] + px)
            if direction in ("全部", "左"):
                f["left"] = max(0, f["left"] - px)
            if direction in ("全部", "右"):
                f["right"] = min(self._img_w, f["right"] + px)

            if f["bottom"] - f["top"] < _MIN_FRAME_SIZE:
                if direction in ("全部", "下"):
                    f["bottom"] = min(self._img_h, f["top"] + _MIN_FRAME_SIZE)
                else:
                    f["top"] = max(0, f["bottom"] - _MIN_FRAME_SIZE)
            if f["right"] - f["left"] < _MIN_FRAME_SIZE:
                if direction in ("全部", "右"):
                    f["right"] = min(self._img_w, f["left"] + _MIN_FRAME_SIZE)
                else:
                    f["left"] = max(0, f["right"] - _MIN_FRAME_SIZE)

            self._recalc_relative(f)

        self._update_frame_list()
        self._draw_frame_overlays()
        self._status.showMessage(f"全局调整: {direction} {px:+d}px")
        self._record_tuning(direction, px)

    def _record_tuning(self, direction: str, px: int) -> None:
        """Persist global adjustment data for future detector tuning.

        Each record contains the image dimensions, scan orientation, frame
        count, and the direction / magnitude of the manual correction.
        Over time this creates a dataset that reveals systematic biases in
        the automatic detector (e.g. "left edge usually needs +20 px").
        """
        if not self._frames:
            return
        tuning_dir = Path.home() / ".negativecutter"
        tuning_dir.mkdir(parents=True, exist_ok=True)
        tuning_file = tuning_dir / "tuning.json"

        avg_w = sum(f["right"] - f["left"] for f in self._frames) / len(self._frames)
        avg_h = sum(f["bottom"] - f["top"] for f in self._frames) / len(self._frames)

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "2.4.4",
            "image_width": self._img_w,
            "image_height": self._img_h,
            "is_horizontal": self._is_horizontal,
            "frame_count": len(self._frames),
            "direction": direction,
            "px": px,
            "avg_frame_width": round(avg_w, 2),
            "avg_frame_height": round(avg_h, 2),
        }

        data: dict = {"adjustments": []}
        if tuning_file.exists():
            try:
                data = json.loads(tuning_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        data["adjustments"].append(record)
        tuning_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _on_export_tuning(self) -> None:
        """Export the accumulated tuning data to a user-selected location."""
        tuning_file = Path.home() / ".negativecutter" / "tuning.json"
        if not tuning_file.exists():
            QMessageBox.information(self, "无调优数据", "尚未记录任何全局调整数据。")
            return
        default = str(Path.home() / "Desktop" / "negativecutter_tuning.json")
        path, _ = QFileDialog.getSaveFileName(self, "导出调优数据", default, "JSON (*.json)")
        if not path:
            return
        import shutil
        shutil.copy(str(tuning_file), path)
        self._status.showMessage(f"调优数据已导出: {path}")

    # ------------------------------------------------------------------ #
    # API server
    # ------------------------------------------------------------------ #

    def _on_start_api(self):
        if self._api_running:
            return
        from filmcrop.api import has_api, run_server

        if not has_api():
            QMessageBox.critical(
                self,
                "FastAPI 未安装",
                "无法启动 API 服务器。请安装依赖:\n\npip install fastapi uvicorn",
            )
            return

        import threading

        self._api_request_count = 0
        self._api_thread = threading.Thread(
            target=run_server, kwargs={"host": "127.0.0.1", "port": 8765}, daemon=True
        )
        self._api_thread.start()
        self._api_running = True
        self._act_start_api.setEnabled(False)
        self._act_stop_api.setEnabled(True)
        self._api_poll_timer.start(1000)
        self._status.showMessage("API 服务器已启动: http://127.0.0.1:8765  请求: 0")

    def _on_stop_api(self):
        if not self._api_running:
            return
        from filmcrop.api import stop_server

        stop_server()
        self._api_running = False
        self._api_poll_timer.stop()
        self._act_start_api.setEnabled(True)
        self._act_stop_api.setEnabled(False)
        self._status.showMessage(
            f"API 服务器已停止  总请求: {self._api_request_count}"
        )

    def _on_api_poll(self):
        if not self._api_running:
            return
        from filmcrop.api import get_request_count

        self._api_request_count = get_request_count()
        self._status.showMessage(
            f"API 服务器运行中: http://127.0.0.1:8765  请求: {self._api_request_count}"
        )

    # ------------------------------------------------------------------ #
    # Export
    # ------------------------------------------------------------------ #

    def _on_export_json(self):
        if not self._image_path or not self._frames:
            return
        from filmcrop.export import to_json
        default = str(Path(self._image_path).with_suffix(".negativecutter.json"))
        path, _ = QFileDialog.getSaveFileName(self, "导出 JSON 边车", default, "JSON (*.json)")
        if not path:
            return
        json_str = to_json(self._frames, self._img_w, self._img_h, debug=self._debug_info)
        Path(path).write_text(json_str, encoding="utf-8")
        self._status.showMessage(f"JSON 已保存: {path}")

    def _on_export_xmp(self):
        if not self._image_path or not self._frames:
            return
        from filmcrop.export import to_xmp
        default = str(Path(self._image_path).with_suffix(".negativecutter.xmp"))
        path, _ = QFileDialog.getSaveFileName(self, "导出 XMP 边车", default, "XMP (*.xmp)")
        if not path:
            return
        xmp_str = to_xmp(self._frames, self._img_w, self._img_h, Path(self._image_path).stem, self._crop_angle)
        Path(path).write_text(xmp_str, encoding="utf-8")
        self._status.showMessage(f"XMP 已保存: {path}")

    def closeEvent(self, event):
        self._cleanup_dng_tmp()
        if self._api_running:
            self._on_stop_api()
        event.accept()

    def _on_export_images(self):
        if not self._image_path or not self._frames:
            return

        dialog = ExportDialog(
            self._image_path,
            self,
            default_format=getattr(self, "_source_fmt", "TIFF"),
            default_color_space=getattr(self, "_source_color_space", "sRGB"),
            default_jpeg_quality=getattr(self, "_source_jpeg_quality", 95),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        opts = dialog.options()
        from filmcrop.export import crop_and_save

        out_dir = opts["output_dir"]
        if not out_dir:
            return

        progress = QProgressDialog("正在导出裁切图像...", "取消", 0, len(self._frames), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()

        paths: list[str] = []

        def _on_frame(i: int, _path: str) -> None:
            progress.setValue(i - 1)
            progress.setLabelText(f"正在导出帧 {i}/{len(self._frames)}...")
            QApplication.processEvents()

        try:
            # For DNG we export from the decoded preview TIFF; the original DNG
            # cannot be cropped directly by Pillow in a reliable way.
            image_path = self._dng_tmp_path if Path(self._image_path).suffix.lower() == ".dng" else self._image_path
            paths = crop_and_save(
                image_path,
                self._frames,
                out_dir,
                fmt=opts["format"],
                quality=opts["quality"],
                color_space=opts["color_space"],
                on_frame=_on_frame,
            )
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"图像导出失败: {e}")

        progress.setValue(len(self._frames))
        self._status.showMessage(f"已导出 {len(paths)} 张图像到 {out_dir}")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("NegativeCutter")
    app.setApplicationDisplayName("NegativeCutter")
    app.setWindowIcon(create_app_icon())

    from filmcrop.gui.style_sheet import build_stylesheet
    app.setStyleSheet(build_stylesheet())

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
