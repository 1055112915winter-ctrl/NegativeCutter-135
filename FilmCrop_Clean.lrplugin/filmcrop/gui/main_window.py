"""
FilmCrop Standalone GUI – Main Window (PyQt6).

Layout:
  ┌──────────────────────────────┬─────────────┐
  │  Image canvas (ImageView)    │ Frame list  │
  │  with zoom + pan + drag      │ + coords    │
  │                              │ + controls  │
  └──────────────────────────────┴─────────────┘
  Status bar: image info / detection perf / zoom level
"""

import sys
import time
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from filmcrop.gui.image_view import ImageView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FilmCrop – Standalone Engine")
        self.setMinimumSize(1200, 800)

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

        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
        self._build_shortcuts()

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self._splitter)

        # --- Left: image view ---
        self._image_view = ImageView()
        self._splitter.addWidget(self._image_view)
        self._splitter.setStretchFactor(0, 3)

        # --- Right: control panel ---
        self._panel = QWidget()
        panel_layout = QVBoxLayout(self._panel)
        panel_layout.setContentsMargins(8, 8, 8, 8)

        # Frame count selector
        panel_layout.addWidget(QLabel("预期帧数:"))
        self._frame_count_spin = QSpinBox()
        self._frame_count_spin.setRange(0, 20)
        self._frame_count_spin.setValue(6)
        self._frame_count_spin.setToolTip("0 = 自动检测")
        panel_layout.addWidget(self._frame_count_spin)

        # Detect button
        self._btn_detect = QPushButton("检测帧 (Detect)")
        self._btn_detect.setEnabled(False)
        self._btn_detect.clicked.connect(self._on_detect)
        panel_layout.addWidget(self._btn_detect)

        panel_layout.addSpacing(12)

        # Frame list
        panel_layout.addWidget(QLabel("帧列表:"))
        self._frame_list = QListWidget()
        self._frame_list.setMaximumHeight(200)
        self._frame_list.currentRowChanged.connect(self._on_frame_selected)
        panel_layout.addWidget(self._frame_list)

        # Coordinate editor
        self._coord_box = QWidget()
        coord_layout = QVBoxLayout(self._coord_box)
        coord_layout.setContentsMargins(0, 0, 0, 0)
        coord_layout.addWidget(QLabel("坐标编辑 (像素):"))

        self._coord_spins = {}
        for label_text, key in (("Top:", "top"), ("Bottom:", "bottom"), ("Left:", "left"), ("Right:", "right")):
            row = QHBoxLayout()
            row.addWidget(QLabel(label_text))
            spin = QSpinBox()
            spin.setRange(0, 99999)
            spin.setEnabled(False)
            spin.valueChanged.connect(lambda val, k=key: self._on_spinbox_changed(k, val))
            self._coord_spins[key] = spin
            row.addWidget(spin)
            coord_layout.addLayout(row)

        panel_layout.addWidget(self._coord_box)
        self._coord_box.setEnabled(False)

        # Add / Delete buttons
        add_del_layout = QHBoxLayout()
        self._btn_add_frame = QPushButton("+ 添加")
        self._btn_add_frame.setEnabled(False)
        self._btn_add_frame.clicked.connect(self._on_add_frame)
        add_del_layout.addWidget(self._btn_add_frame)

        self._btn_del_frame = QPushButton("- 删除")
        self._btn_del_frame.setEnabled(False)
        self._btn_del_frame.clicked.connect(self._on_del_frame)
        add_del_layout.addWidget(self._btn_del_frame)
        panel_layout.addLayout(add_del_layout)

        panel_layout.addSpacing(12)

        # Export buttons
        self._btn_export_json = QPushButton("导出 JSON 边车")
        self._btn_export_json.setEnabled(False)
        self._btn_export_json.clicked.connect(self._on_export_json)
        panel_layout.addWidget(self._btn_export_json)

        self._btn_export_xmp = QPushButton("导出 XMP 边车")
        self._btn_export_xmp.setEnabled(False)
        self._btn_export_xmp.clicked.connect(self._on_export_xmp)
        panel_layout.addWidget(self._btn_export_xmp)

        self._btn_export_images = QPushButton("导出裁切图像")
        self._btn_export_images.setEnabled(False)
        self._btn_export_images.clicked.connect(self._on_export_images)
        panel_layout.addWidget(self._btn_export_images)

        panel_layout.addStretch()
        self._splitter.addWidget(self._panel)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([900, 300])

    def _build_menu(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("文件 (&F)")
        open_act = QAction("打开 (&O)...", self)
        open_act.setShortcut(QKeySequence.StandardKey.Open)
        open_act.triggered.connect(self._on_open)
        file_menu.addAction(open_act)
        file_menu.addSeparator()

        export_menu = file_menu.addMenu("导出 (&E)")
        export_json_act = QAction("JSON 边车 (&J)", self)
        export_json_act.setShortcut(QKeySequence("Ctrl+J"))
        export_json_act.triggered.connect(self._on_export_json)
        export_menu.addAction(export_json_act)

        export_xmp_act = QAction("XMP 边车 (&X)", self)
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
        tb.addAction("打开", self._on_open)
        tb.addSeparator()
        tb.addAction("检测", self._on_detect)
        tb.addSeparator()
        tb.addAction("重置缩放", self._image_view.reset_zoom)

    def _build_statusbar(self):
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("就绪 – 请打开图像文件")

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
        self._image_path = path
        t0 = time.time()
        suffix = Path(path).suffix.lower()
        bit_depth = 8
        if suffix == ".dng":
            try:
                import rawpy
                with rawpy.imread(path) as raw:
                    rgb = raw.postprocess()
                    from PIL import Image as PILImage
                    tmp = PILImage.fromarray(rgb)
                    tmp_path = "/tmp/filmcrop_dng_preview.tif"
                    tmp.save(tmp_path)
                    self._image_view.load_image(tmp_path)
            except ImportError:
                self._status.showMessage("DNG 需要 rawpy: pip install rawpy")
                return
            except Exception as e:
                self._status.showMessage(f"DNG 读取失败: {e}")
                return
        else:
            from PIL import Image as PILImage
            img = PILImage.open(path)
            if img.mode in ("I;16", "I;16B", "I;16N", "I"):
                bit_depth = 16
            img.close()
            self._image_view.load_image(path)

        self._img_w, self._img_h = self._image_view.image_size()
        self._is_horizontal = self._img_w >= self._img_h
        load_time = time.time() - t0
        self._status.showMessage(
            f"{Path(path).name}  {self._img_w}×{self._img_h}  {bit_depth}bit  加载 {load_time:.2f}s"
        )
        self._btn_detect.setEnabled(True)
        self._frames = []
        # Set spinbox max values based on image size
        self._coord_spins["top"].setMaximum(self._img_h)
        self._coord_spins["bottom"].setMaximum(self._img_h)
        self._coord_spins["left"].setMaximum(self._img_w)
        self._coord_spins["right"].setMaximum(self._img_w)
        self._update_frame_list()
        self._update_export_buttons()

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
            result = analyze_image(self._image_path, expected_frames=expected)
            self._frames = result.get("frames", [])
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
        mem_info = ""
        if HAS_PSUTIL:
            mem_after = psutil.Process().memory_info().rss / 1024 / 1024
            mem_info = f"  内存 +{mem_after - mem_before:.1f}MB"
        self._status.showMessage(f"检测到 {len(self._frames)} 帧  耗时 {elapsed:.2f}s{mem_info}")

        self._update_frame_list()
        self._update_export_buttons()
        self._draw_frame_overlays()

    def _update_frame_list(self):
        self._frame_list.clear()
        for f in self._frames:
            rt = f.get("relativeTop", 0.0)
            rb = f.get("relativeBottom", 1.0)
            rl = f.get("relativeLeft", 0.0)
            rr = f.get("relativeRight", 1.0)
            label = (
                f"帧{f['index']}:  "
                f"T={f['top']} B={f['bottom']}  "
                f"L={f['left']} R={f['right']}  |  "
                f"rT={rt:.3f} rB={rb:.3f}  "
                f"rL={rl:.3f} rR={rr:.3f}"
            )
            self._frame_list.addItem(label)

    def _update_export_buttons(self):
        has = bool(self._frames)
        self._btn_export_json.setEnabled(has)
        self._btn_export_xmp.setEnabled(has)
        self._btn_export_images.setEnabled(has)
        self._btn_add_frame.setEnabled(has)
        self._btn_del_frame.setEnabled(has and len(self._frames) > 1)
        self._coord_box.setEnabled(has)
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
        # Enforce min size and update relative coords
        if key in ("top", "left"):
            opposite = {"top": "bottom", "left": "right"}[key]
            f[opposite] = max(f[opposite], val + 20)
        else:
            opposite = {"bottom": "top", "right": "left"}[key]
            f[opposite] = min(f[opposite], val - 20)
        self._recalc_relative(f)
        self._update_frame_list()
        self._image_view.update_frame_geometry(row)
        self._sync_spinboxes(row)

    def _on_canvas_frame_changed(self, idx: int, released: bool = False):
        """Callback from ImageView when user drags a frame edge."""
        if not (0 <= idx < len(self._frames)):
            return
        if released:
            self._push_undo()
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

    def _push_undo(self):
        self._undo_stack.append([dict(f) for f in self._frames])
        if len(self._undo_stack) > 50:
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
        for i, fr in enumerate(self._frames):
            fr["index"] = i + 1
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
        for i, fr in enumerate(self._frames):
            fr["index"] = i + 1
        self._update_frame_list()
        new_row = min(row, len(self._frames) - 1)
        self._frame_list.setCurrentRow(new_row)
        self._draw_frame_overlays()
        self._status.showMessage(f"删除帧 {row + 1}")

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
        default = str(Path(self._image_path).with_suffix(".filmcrop.json"))
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
        default = str(Path(self._image_path).with_suffix(".filmcrop.xmp"))
        path, _ = QFileDialog.getSaveFileName(self, "导出 XMP 边车", default, "XMP (*.xmp)")
        if not path:
            return
        xmp_str = to_xmp(self._frames, self._img_w, self._img_h, Path(self._image_path).stem, self._crop_angle)
        Path(path).write_text(xmp_str, encoding="utf-8")
        self._status.showMessage(f"XMP 已保存: {path}")

    def _on_export_images(self):
        if not self._image_path or not self._frames:
            return

        dialog = ExportDialog(self)
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
        for i, frame in enumerate(self._frames):
            if progress.wasCanceled():
                break
            progress.setValue(i)
            progress.setLabelText(f"正在导出帧 {i + 1}/{len(self._frames)}...")
            QApplication.processEvents()
            try:
                p = crop_and_save(
                    self._image_path,
                    [frame],
                    out_dir,
                    fmt=opts["format"],
                    quality=opts["quality"],
                    color_space=opts["color_space"],
                )
                paths.extend(p)
            except Exception as e:
                QMessageBox.warning(self, "导出失败", f"帧 {i + 1} 导出失败: {e}")

        progress.setValue(len(self._frames))
        self._status.showMessage(f"已导出 {len(paths)} 张图像到 {out_dir}")


class ExportDialog(QDialog):
    """Options dialog for cropped image export."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("导出裁切图像")
        self.setMinimumWidth(320)

        layout = QFormLayout(self)

        self._format_combo = QComboBox()
        self._format_combo.addItems(["TIFF", "JPEG", "PNG"])
        self._format_combo.setCurrentText("TIFF")
        self._format_combo.currentTextChanged.connect(self._on_format_changed)
        layout.addRow("格式:", self._format_combo)

        self._quality_spin = QSpinBox()
        self._quality_spin.setRange(1, 100)
        self._quality_spin.setValue(95)
        self._quality_spin.setEnabled(False)
        layout.addRow("JPEG 质量:", self._quality_spin)

        self._color_space_combo = QComboBox()
        self._color_space_combo.addItems(["sRGB", "Adobe RGB", "保留原始"])
        layout.addRow("色彩空间:", self._color_space_combo)

        self._output_dir_edit = QLabel()
        self._output_dir_edit.setWordWrap(True)
        layout.addRow("输出目录:", self._output_dir_edit)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        ok_btn = btn_box.button(QDialogButtonBox.StandardButton.Ok)
        cancel_btn = btn_box.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_btn is not None:
            ok_btn.setText("导出")
        if cancel_btn is not None:
            cancel_btn.setText("取消")

        # Pick output directory
        pick_btn = QPushButton("选择目录...")
        pick_btn.clicked.connect(self._pick_dir)
        layout.addRow(pick_btn)
        layout.addRow(btn_box)

        self._output_dir = ""
        self._set_default_dir()

    def _set_default_dir(self):
        parent = self.parent()
        image_path = ""
        if isinstance(parent, MainWindow):
            image_path = parent._image_path or ""
        if image_path:
            default = str(Path(image_path).parent / "cropped")
        else:
            default = str(Path.home() / "Desktop")
        self._output_dir = default
        self._output_dir_edit.setText(default)

    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择导出目录", self._output_dir)
        if d:
            self._output_dir = d
            self._output_dir_edit.setText(d)

    def _on_format_changed(self, text: str):
        self._quality_spin.setEnabled(text == "JPEG")

    def options(self) -> dict:
        fmt_map = {"TIFF": "tiff", "JPEG": "jpeg", "PNG": "png"}
        cs_map = {"sRGB": "sRGB", "Adobe RGB": "Adobe RGB", "保留原始": "preserve"}
        return {
            "format": fmt_map.get(self._format_combo.currentText(), "tiff"),
            "quality": self._quality_spin.value(),
            "color_space": cs_map.get(self._color_space_combo.currentText(), "sRGB"),
            "output_dir": self._output_dir,
        }


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("FilmCrop")
    app.setApplicationDisplayName("FilmCrop Standalone")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
