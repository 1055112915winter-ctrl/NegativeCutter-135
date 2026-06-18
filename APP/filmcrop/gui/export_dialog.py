"""Export options dialog for cropped image export."""

from pathlib import Path

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QWidget,
)


class ExportDialog(QDialog):
    """Options dialog for cropped image export."""

    def __init__(
        self,
        image_path: str | None = None,
        parent: QWidget | None = None,
        default_format: str = "TIFF",
        default_color_space: str = "sRGB",
        default_jpeg_quality: int = 95,
    ):
        super().__init__(parent)
        self.setWindowTitle("导出裁切图像")
        self.setMinimumWidth(360)
        self._image_path = image_path

        layout = QFormLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self._format_combo = QComboBox()
        self._format_combo.addItems(["TIFF", "JPEG", "PNG"])
        self._format_combo.setCurrentText(default_format)
        self._format_combo.currentTextChanged.connect(self._on_format_changed)
        layout.addRow("格式:", self._format_combo)

        self._quality_spin = QSpinBox()
        self._quality_spin.setRange(1, 100)
        self._quality_spin.setValue(default_jpeg_quality)
        self._quality_spin.setEnabled(default_format == "JPEG")
        layout.addRow("JPEG 质量:", self._quality_spin)

        self._color_space_combo = QComboBox()
        self._color_space_combo.addItems(["sRGB", "Adobe RGB", "保留原始"])
        self._color_space_combo.setCurrentText(default_color_space)
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
            ok_btn.setObjectName("primary")
        if cancel_btn is not None:
            cancel_btn.setText("取消")

        pick_btn = QPushButton("选择目录...")
        pick_btn.clicked.connect(self._pick_dir)
        layout.addRow(pick_btn)
        layout.addRow(btn_box)

        self._output_dir = ""
        self._set_default_dir()

    def _set_default_dir(self):
        if self._image_path:
            default = str(Path(self._image_path).parent / "cropped")
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
