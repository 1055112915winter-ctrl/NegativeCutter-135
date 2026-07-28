import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "APP"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from filmcrop.gui.export_dialog import ExportDialog


class ExportDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_saved_defaults_are_loaded_and_updated_from_dialog(self):
        stored = {
            ExportDialog._FORMAT_KEY: "JPEG",
            ExportDialog._COLOR_SPACE_KEY: "preserve",
            ExportDialog._QUALITY_KEY: 88,
        }
        settings = MagicMock()

        def read_value(key, fallback=None):
            return stored.get(key, fallback)

        settings.value.side_effect = read_value

        # Other compatibility tests intentionally reload the ``filmcrop``
        # package between cases. Patch the dialog's settings seam directly so
        # this test remains isolated from that module-cache cleanup.
        with patch.object(ExportDialog, "_settings", return_value=settings):
            dialog = ExportDialog(
                image_path="/tmp/scan.tif",
                default_format="TIFF",
                default_color_space="sRGB",
                default_jpeg_quality=95,
            )
            self.addCleanup(dialog.close)

            self.assertEqual(dialog._format_combo.currentText(), "JPEG")
            self.assertEqual(dialog._color_space_combo.currentText(), "保留原始")
            self.assertEqual(dialog._quality_spin.value(), 88)
            self.assertTrue(dialog._quality_spin.isEnabled())

            dialog._format_combo.setCurrentText("PNG")
            dialog._color_space_combo.setCurrentText("Adobe RGB")
            dialog._quality_spin.setValue(76)
            dialog._save_defaults_check.setChecked(True)
            dialog._accept()

        settings.setValue.assert_any_call(ExportDialog._FORMAT_KEY, "PNG")
        settings.setValue.assert_any_call(ExportDialog._COLOR_SPACE_KEY, "Adobe RGB")
        settings.setValue.assert_any_call(ExportDialog._QUALITY_KEY, 76)
        settings.sync.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
