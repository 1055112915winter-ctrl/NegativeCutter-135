"""Export options dialog for cropped image export."""

from pathlib import Path

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import (
    QCheckBox,
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

    _SETTINGS_ORGANIZATION = "NegativeCutter"
    _SETTINGS_APPLICATION = "NegativeCutter"
    _FORMAT_KEY = "export/default_format"
    _QUALITY_KEY = "export/default_jpeg_quality"
    _COLOR_SPACE_KEY = "export/default_color_space"
    _FORMAT_LABELS = {
        "tif": "TIFF",
        "tiff": "TIFF",
        "jpg": "JPEG",
        "jpeg": "JPEG",
        "png": "PNG",
    }
    _COLOR_SPACE_LABELS = {
        "srgb": "sRGB",
        "adobe rgb": "Adobe RGB",
        "preserve": "保留原始",
        "保留原始": "保留原始",
    }

    @classmethod
    def _settings(cls) -> QSettings:
        return QSettings(cls._SETTINGS_ORGANIZATION, cls._SETTINGS_APPLICATION)

    @classmethod
    def _load_defaults(
        cls,
        default_format: str,
        default_color_space: str,
        default_jpeg_quality: int,
    ) -> tuple[str, str, int]:
        format_label = cls._normalize_format(default_format)
        color_space_label = cls._normalize_color_space(default_color_space)
        jpeg_quality = cls._normalize_quality(default_jpeg_quality)

        settings = cls._settings()
        stored_format = settings.value(cls._FORMAT_KEY, None)
        if isinstance(stored_format, str):
            format_label = cls._normalize_format(stored_format, format_label)

        stored_color_space = settings.value(cls._COLOR_SPACE_KEY, None)
        if isinstance(stored_color_space, str):
            color_space_label = cls._normalize_color_space(
                stored_color_space, color_space_label
            )

        stored_quality = settings.value(cls._QUALITY_KEY, None)
        if stored_quality is not None:
            try:
                jpeg_quality = cls._normalize_quality(stored_quality, jpeg_quality)
            except (TypeError, ValueError):
                pass

        return format_label, color_space_label, jpeg_quality

    @classmethod
    def _save_defaults(
        cls,
        format_label: str,
        color_space_label: str,
        jpeg_quality: int,
    ) -> None:
        settings = cls._settings()
        settings.setValue(cls._FORMAT_KEY, format_label)
        settings.setValue(cls._COLOR_SPACE_KEY, color_space_label)
        settings.setValue(cls._QUALITY_KEY, jpeg_quality)
        settings.sync()

    @classmethod
    def _normalize_format(cls, value: object, fallback: str = "TIFF") -> str:
        return cls._FORMAT_LABELS.get(str(value or "").strip().lower(), fallback)

    @classmethod
    def _normalize_color_space(
        cls, value: object, fallback: str = "sRGB"
    ) -> str:
        return cls._COLOR_SPACE_LABELS.get(str(value or "").strip().lower(), fallback)

    @staticmethod
    def _normalize_quality(value: object, fallback: int = 95) -> int:
        try:
            quality = int(value)
        except (TypeError, ValueError):
            return fallback
        return max(1, min(100, quality))

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
        default_format, default_color_space, default_jpeg_quality = self._load_defaults(
            default_format,
            default_color_space,
            default_jpeg_quality,
        )

        layout = QFormLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self._format_combo = QComboBox()
        self._format_combo.addItems(["TIFF", "JPEG", "PNG"])
        self._format_combo.setCurrentText(default_format)
        self._format_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._format_combo.setMinimumWidth(100)
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
        self._color_space_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._color_space_combo.setMinimumWidth(120)
        layout.addRow("色彩空间:", self._color_space_combo)

        self._save_defaults_check = QCheckBox("将当前选项设为默认")
        self._save_defaults_check.setMinimumHeight(40)
        self._save_defaults_check.setToolTip(
            "点击“导出”后保存格式、JPEG 质量和色彩空间；输出目录仍按当前图像确定"
        )
        layout.addRow(self._save_defaults_check)

        self._output_dir_edit = QLabel()
        self._output_dir_edit.setWordWrap(True)
        layout.addRow("输出目录:", self._output_dir_edit)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._accept)
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

    def _accept(self):
        if self._save_defaults_check.isChecked():
            self._save_defaults(
                self._format_combo.currentText(),
                self._color_space_combo.currentText(),
                self._quality_spin.value(),
            )
        self.accept()

    def options(self) -> dict:
        fmt_map = {"TIFF": "tiff", "JPEG": "jpeg", "PNG": "png"}
        cs_map = {"sRGB": "sRGB", "Adobe RGB": "Adobe RGB", "保留原始": "preserve"}
        return {
            "format": fmt_map.get(self._format_combo.currentText(), "tiff"),
            "quality": self._quality_spin.value(),
            "color_space": cs_map.get(self._color_space_combo.currentText(), "sRGB"),
            "output_dir": self._output_dir,
        }
