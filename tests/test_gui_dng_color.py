import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image
from PyQt6.QtWidgets import QApplication, QProgressDialog


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "APP"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from filmcrop import detector
from filmcrop._vendor import tifffile
from filmcrop.export import crop_and_save
from filmcrop.gui.main_window import MainWindow
from filmcrop.gui.style_sheet import build_stylesheet


class _FakeRawFile:
    def __init__(self, preview: np.ndarray):
        self.preview = preview
        self.postprocess_kwargs: dict | None = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def postprocess(self, **kwargs):
        self.postprocess_kwargs = kwargs
        return self.preview


class DngColorWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(build_stylesheet())

    def setUp(self):
        self.window = MainWindow()

    def tearDown(self):
        self.window.close()

    def test_load_dng_preview_array_uses_rawpy_postprocess_for_rgb_preview(self):
        preview = np.zeros((4, 6, 3), dtype=np.uint16)
        preview[:, :, 0] = 65535
        preview[:, :, 1] = 32768
        fake_raw = _FakeRawFile(preview)
        srgb = object()
        fake_rawpy = types.SimpleNamespace(
            imread=lambda _path: fake_raw,
            ColorSpace=types.SimpleNamespace(sRGB=srgb),
        )

        with patch.dict(sys.modules, {"rawpy": fake_rawpy}):
            arr, loader, bit_depth = detector.load_dng_preview_array("scan.dng")

        self.assertEqual(loader, "rawpy")
        self.assertEqual(bit_depth, 16)
        np.testing.assert_array_equal(arr, preview)
        self.assertEqual(fake_raw.postprocess_kwargs["output_bps"], 16)
        self.assertIs(fake_raw.postprocess_kwargs.get("output_color"), srgb)
        self.assertNotIn("use_camera_wb", fake_raw.postprocess_kwargs)
        self.assertNotIn("use_auto_wb", fake_raw.postprocess_kwargs)
        self.assertNotIn("no_auto_bright", fake_raw.postprocess_kwargs)

    def test_real_raw0014_preview_stays_close_to_embedded_preview_warmth(self):
        fixture = ROOT / "test_files" / "raw0014.dng"
        if "rawpy" not in sys.modules:
            try:
                __import__("rawpy")
            except ImportError:
                self.skipTest("rawpy unavailable")

        arr, loader, bit_depth = detector.load_dng_preview_array(str(fixture))
        if loader != "rawpy":
            self.skipTest(f"expected rawpy loader, got {loader}")

        with Image.open(fixture) as embedded_img:
            embedded = np.asarray(embedded_img.convert("RGB"), dtype=np.float64)

        preview = np.asarray(arr, dtype=np.float64)
        embedded_mean = embedded.reshape(-1, 3).mean(axis=0)
        preview_mean = preview.reshape(-1, 3).mean(axis=0)
        embedded_ratios = (
            embedded_mean[0] / embedded_mean[1],
            embedded_mean[0] / embedded_mean[2],
            embedded_mean[1] / embedded_mean[2],
        )
        preview_ratios = (
            preview_mean[0] / preview_mean[1],
            preview_mean[0] / preview_mean[2],
            preview_mean[1] / preview_mean[2],
        )
        ratio_delta = sum(
            abs(float(preview_ratios[idx] - embedded_ratios[idx]))
            for idx in range(3)
        )

        self.assertEqual(bit_depth, 16)
        self.assertLess(
            ratio_delta,
            0.45,
            f"preview ratios drifted too far from embedded preview warmth: {preview_ratios} vs {embedded_ratios}",
        )

    def test_load_dng_writes_color_temp_tiff_for_preview_and_export(self):
        preview = np.zeros((8, 12, 3), dtype=np.uint16)
        preview[:, :, 0] = 65535
        preview[:, :, 1] = 28000
        preview[:, :, 2] = 9000
        progress = QProgressDialog()

        with (
            patch(
                "filmcrop.detector.load_dng_preview_array",
                return_value=(preview, "rawpy", 16),
                create=True,
            ),
            patch(
                "filmcrop.detector._load_raw_dng_array",
                side_effect=AssertionError("preview path should not use detector grayscale"),
            ),
        ):
            source_fmt, bit_depth = self.window._load_dng("scan.dng", progress)

        self.assertEqual(source_fmt, "TIFF")
        self.assertEqual(bit_depth, 16)
        self.assertIsNotNone(self.window._dng_tmp_path)

        with Image.open(self.window._dng_tmp_path) as preview_img:
            self.assertEqual(preview_img.mode, "RGB")
            self.assertEqual(tuple(preview_img.tag_v2.get(258)), (16, 16, 16))
            preview_icc = preview_img.info.get("icc_profile")
            preview_pixel = preview_img.getpixel((2, 2))

        self.assertTrue(preview_icc)
        self.assertNotEqual(preview_pixel[0], preview_pixel[1])
        self.assertNotEqual(preview_pixel[1], preview_pixel[2])

        frame = {"index": 1, "left": 2, "top": 1, "right": 10, "bottom": 7}
        with tempfile.TemporaryDirectory() as tmp:
            [written] = crop_and_save(self.window._dng_tmp_path, [frame], tmp, fmt="tiff")
            with Image.open(written) as exported:
                self.assertEqual(exported.mode, "RGB")
                self.assertEqual(tuple(exported.tag_v2.get(258)), (16, 16, 16))
                self.assertEqual(exported.info.get("icc_profile"), preview_icc)
                exported_pixel = exported.getpixel((1, 1))

            preview_array = tifffile.imread(self.window._dng_tmp_path)
            exported_array = tifffile.imread(written)

        np.testing.assert_array_equal(exported_array, preview_array[1:7, 2:10])
        self.assertNotEqual(exported_pixel[0], exported_pixel[1])
        self.assertNotEqual(exported_pixel[1], exported_pixel[2])


if __name__ == "__main__":
    unittest.main()
