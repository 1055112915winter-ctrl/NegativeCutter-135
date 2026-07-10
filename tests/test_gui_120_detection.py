import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image
from PyQt6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "APP"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from filmcrop import detector
from filmcrop.gui.main_window import MainWindow


class _TrackingImage:
    def __init__(self, image):
        self._image = image
        self.closed = False

    def __getattr__(self, name):
        return getattr(self._image, name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        self.closed = True
        self._image.close()


class GuiMediumFormatRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_gui_exposes_every_supported_film_format(self):
        window = MainWindow()
        try:
            values = [window._film_format_combo.itemData(i) for i in range(window._film_format_combo.count())]
            self.assertEqual(values, [None, "35mm", "645", "6x6", "6x7", "6x8", "6x9"])
            self.assertEqual(window._film_format_combo.currentData(), "35mm")
            self.assertGreaterEqual(window._film_format_combo.minimumHeight(), 40)
        finally:
            window.close()

    def test_gui_forwards_selected_format_and_ratio(self):
        window = MainWindow()
        window._image_path = "scan.tif"
        index = window._film_format_combo.findData("6x7")
        window._film_format_combo.setCurrentIndex(index)
        frame = {
            "index": 1,
            "top": 0,
            "bottom": 60,
            "left": 0,
            "right": 70,
            "relativeTop": 0.0,
            "relativeBottom": 1.0,
            "relativeLeft": 0.0,
            "relativeRight": 1.0,
        }

        with patch("filmcrop.detector.analyze_image", return_value={"frames": [frame]}) as analyze:
            window._do_detect(expected=4)
        window.close()

        self.assertEqual(analyze.call_args.kwargs["film_format"], "6x7")
        self.assertEqual(analyze.call_args.kwargs["aspect_ratio"], 7 / 6)

    def _should_use_120(self, width, height, expected_frames, film_format):
        if not hasattr(detector, "_should_use_120"):
            self.fail("APP detector._should_use_120 is not implemented")
        return detector._should_use_120(
            width,
            height,
            expected_frames,
            film_format,
        )

    def _analyze(self, *args, **kwargs):
        try:
            return detector.analyze_image(*args, **kwargs)
        except TypeError as exc:
            if "film_format" in str(exc):
                self.fail("APP analyze_image does not accept film_format")
            raise

    def test_explicit_120_format_selects_medium_format_route(self):
        use_120, reason = self._should_use_120(3000, 1000, 4, "6x7")

        self.assertTrue(use_120)
        self.assertEqual(reason, "explicit_format")

    def test_explicit_35mm_stays_on_135_route(self):
        use_120, reason = self._should_use_120(3000, 1000, 0, "35mm")

        self.assertFalse(use_120)
        self.assertEqual(reason, "explicit_35mm")

    def test_horizontal_auto_strip_selects_medium_format_route(self):
        use_120, reason = self._should_use_120(3000, 1000, 0, None)

        self.assertTrue(use_120)
        self.assertEqual(reason, "auto_geometry")

    def test_explicit_count_is_forwarded_without_losing_review_option(self):
        pixels = np.zeros((1000, 3000), dtype=np.uint8)
        sentinel = {"frameCount": 4, "frames": [], "debug": {}}

        with patch.object(
            detector,
            "_load_image_array",
            return_value=(pixels, "test"),
        ), patch.object(
            detector,
            "analyze_image_120",
            return_value=sentinel,
        ) as analyze_120:
            result = self._analyze(
                "scan.tif",
                expected_frames=4,
                aspect_ratio=7 / 6,
                include_review_frames=True,
                film_format="6x7",
            )

        self.assertIs(result, sentinel)
        analyze_120.assert_called_once_with(
            "scan.tif",
            None,
            7 / 6,
            expected_frames_hint=4,
            film_format="6x7",
            route_reason="explicit_format",
        )

    def test_pillow_loader_closes_source_file(self):
        pixels = np.zeros((32, 96, 3), dtype=np.uint8)

        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "strip.tif"
            Image.fromarray(pixels).save(image_path)
            with Image.open(image_path) as source:
                tracked = _TrackingImage(source.copy())
            with patch.object(detector.Image, "open", return_value=tracked):
                detector._load_pillow_image_array(str(image_path))

        self.assertTrue(tracked.closed)


if __name__ == "__main__":
    unittest.main()
