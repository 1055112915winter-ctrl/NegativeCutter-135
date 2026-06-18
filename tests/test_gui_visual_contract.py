import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "APP"
sys.path.insert(0, str(APP_ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class GuiVisualContractTest(unittest.TestCase):
    def test_darkroom_palette_and_component_geometry(self):
        from filmcrop.gui import theme
        from filmcrop.gui.style_sheet import build_stylesheet

        self.assertEqual(theme.PAGE_BG, "#101315")
        self.assertEqual(theme.CANVAS_BG, "#050708")
        self.assertEqual(theme.BRAND, "#d7a75e")

        stylesheet = build_stylesheet()
        self.assertIn("QWidget#card", stylesheet)
        self.assertIn("border-radius: 5px", stylesheet)
        self.assertNotIn("border-left: 3px", stylesheet)
        self.assertIn("QLabel#wordmark", stylesheet)
        self.assertIn("QLabel#brandSubtitle", stylesheet)

    def test_main_window_uses_approved_brand_language(self):
        source = (APP_ROOT / "filmcrop/gui/main_window.py").read_text(encoding="utf-8")

        for text in (
            "NEGATIVE CUTTER",
            "PRECISION FRAME TOOL",
            "DETECTION",
            "FRAMES",
            "COORDINATES",
            "ADJUSTMENT",
            "OUTPUT",
        ):
            self.assertIn(f'"{text}"', source)

        self.assertIn('QPushButton("检测帧 (Ctrl+D)")', source)
        self.assertIn('QPushButton("导出裁切图像")', source)

    def test_logo_renders_amber_diamond_and_header_mark(self):
        from PyQt6.QtWidgets import QApplication
        from filmcrop.gui.logo import create_app_icon, create_header_logo_pixmap
        from filmcrop.gui.theme import BRAND

        app = QApplication.instance() or QApplication([])
        icon = create_app_icon()
        header = create_header_logo_pixmap(64)

        self.assertFalse(icon.isNull())
        self.assertFalse(header.isNull())
        image = header.toImage()
        brand_rgb = tuple(int(BRAND[i : i + 2], 16) for i in (1, 3, 5))
        amber_pixels = 0
        for y in range(image.height()):
            for x in range(image.width()):
                color = image.pixelColor(x, y)
                if color.alpha() and (
                    abs(color.red() - brand_rgb[0]) <= 8
                    and abs(color.green() - brand_rgb[1]) <= 8
                    and abs(color.blue() - brand_rgb[2]) <= 8
                ):
                    amber_pixels += 1

        self.assertGreater(amber_pixels, 100)
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
