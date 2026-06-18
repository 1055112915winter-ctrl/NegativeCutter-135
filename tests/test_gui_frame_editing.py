import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "APP"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from PIL import Image

from filmcrop.gui.image_view import ImageView
from filmcrop.gui.main_window import MainWindow
from filmcrop.gui.style_sheet import build_stylesheet
from filmcrop.detector import _stretch_uint8
from filmcrop._vendor import tifffile


def _frame(index: int, left: int, right: int) -> dict:
    return {
        "index": index,
        "top": 10,
        "bottom": 90,
        "left": left,
        "right": right,
        "relativeTop": 0.1,
        "relativeBottom": 0.9,
        "relativeLeft": left / 100,
        "relativeRight": right / 100,
    }


class GuiFrameEditingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(build_stylesheet())

    def setUp(self):
        self.window = MainWindow()
        self.window._img_w = 100
        self.window._img_h = 100

    def tearDown(self):
        self.window.close()

    def test_frame_list_selects_first_frame_and_preserves_selection(self):
        self.window._frames = [_frame(1, 0, 40), _frame(2, 50, 90)]

        self.window._update_frame_list()
        self.assertEqual(self.window._frame_list.currentRow(), 0)

        self.window._frame_list.setCurrentRow(1)
        self.window._update_frame_list()
        self.assertEqual(self.window._frame_list.currentRow(), 1)

    def test_drag_release_stores_pre_drag_state_for_undo(self):
        original = _frame(1, 10, 60)
        self.window._frames = [dict(original)]
        self.window._update_frame_list()

        self.window._frames[0]["left"] = 25
        self.window._on_canvas_frame_changed(
            0,
            released=True,
            previous_frame=original,
        )
        self.window._undo()

        self.assertEqual(self.window._frames[0]["left"], 10)

    def test_image_view_forwards_pre_drag_snapshot_on_release(self):
        original = _frame(1, 10, 60)
        frames = [dict(original)]
        events = []
        view = ImageView()
        view.set_frame_overlays(
            frames,
            on_frame_changed=lambda idx, released=False, previous_frame=None: events.append(
                (idx, released, previous_frame)
            ),
        )

        frames[0]["left"] = 25
        view._frame_items[0]._on_released(frames[0], original)

        self.assertEqual(events, [(0, True, original)])

    def test_reset_image_state_clears_canvas_and_edit_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "scan.png"
            Image.new("RGB", (20, 10), "white").save(image_path)
            self.window._image_view.load_image(str(image_path))

        self.window._undo_stack = [[_frame(1, 0, 40)]]
        self.window._redo_stack = [[_frame(1, 10, 50)]]
        self.window._reset_image_state()

        self.assertEqual(self.window._image_view.image_size(), (0, 0))
        self.assertEqual(self.window._undo_stack, [])
        self.assertEqual(self.window._redo_stack, [])

    def test_failed_dng_load_removes_temporary_preview(self):
        fd, tmp_path = tempfile.mkstemp(suffix=".tif")
        os.close(fd)

        def fail_after_creating_preview(_path, _progress):
            self.window._dng_tmp_path = tmp_path
            raise RuntimeError("preview failed")

        with patch.object(self.window, "_load_dng", side_effect=fail_after_creating_preview):
            self.window._load_image("broken.dng")

        self.assertFalse(Path(tmp_path).exists())

    def test_loading_new_image_clears_previous_edit_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "scan.png"
            Image.new("RGB", (20, 10), "white").save(image_path)
            self.window._undo_stack = [[_frame(1, 0, 40)]]
            self.window._redo_stack = [[_frame(1, 10, 50)]]

            self.window._load_image(str(image_path))

        self.assertEqual(self.window._undo_stack, [])
        self.assertEqual(self.window._redo_stack, [])

    def test_redetecting_frames_clears_previous_edit_history(self):
        detected = _frame(1, 5, 55)
        self.window._image_path = "scan.tif"
        self.window._undo_stack = [[_frame(1, 0, 40)]]
        self.window._redo_stack = [[_frame(1, 10, 50)]]

        with patch("filmcrop.detector.analyze_image", return_value={"frames": [detected]}):
            self.window._do_detect(expected=1)

        self.assertEqual(self.window._undo_stack, [])
        self.assertEqual(self.window._redo_stack, [])

    def test_detector_normalizes_multichannel_raw_array_to_grayscale(self):
        raw = np.zeros((8, 12, 3), dtype=np.uint16)
        raw[:, :, 0] = 65535

        result = _stretch_uint8(raw, contrast_enhance=False)

        self.assertEqual(result.shape, (8, 12))
        self.assertEqual(result.dtype, np.uint8)

    def test_image_view_preserves_color_in_multichannel_16_bit_array(self):
        from filmcrop.gui.image_view import _normalize_16bit_array

        raw = np.zeros((8, 12, 3), dtype=np.uint16)
        raw[:, :, 0] = 65535
        raw[:, :, 1] = 32768

        result = _normalize_16bit_array(raw)

        self.assertEqual(result.mode, "RGB")
        self.assertEqual(result.size, (12, 8))
        self.assertEqual(result.getpixel((0, 0)), (255, 127, 0))

    def test_loading_16bit_rgb_tiff_reports_depth_and_preserves_color(self):
        image_path = FIXTURES / "rgb16_top_left.tif"

        self.window._load_image(str(image_path))

        self.assertEqual(self.window._source_bit_depth, 16)
        self.assertEqual(self.window._source_color_space, "Adobe RGB")
        self.assertEqual(self.window._btn_export_json.text(), "保存坐标数据")
        pixmap = self.window._image_view._pixmap_item.pixmap()
        color = pixmap.toImage().pixelColor(8, 6)
        self.assertNotEqual(color.red(), color.green())
        self.assertNotEqual(color.green(), color.blue())

    def test_loading_untagged_tiff_reports_unknown_color_space(self):
        pixels = np.zeros((8, 12, 3), dtype=np.uint16)
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "untagged.tif"
            tifffile.imwrite(image_path, pixels, photometric="rgb", metadata=None)
            self.window._load_image(str(image_path))

        self.assertEqual(self.window._source_color_space, "色彩空间未知")

    def test_loading_dng_relabels_existing_coordinate_export_button(self):
        self.window._dng_loader = "rawpy"
        with patch.object(self.window, "_load_dng", return_value=("TIFF", 16)):
            self.window._load_image("scan.dng")

        self.assertEqual(self.window._btn_export_json.text(), "导出原始 DNG 坐标")

    def test_reviewable_detection_keeps_frames_and_warns_user(self):
        detected = _frame(1, 5, 55)
        self.window._image_path = "scan.tif"

        with patch(
            "filmcrop.detector.analyze_image",
            return_value={
                "frames": [detected],
                "frameCount": 1,
                "needsReview": True,
                "error": "low confidence",
                "debug": {"reason": "confidence"},
            },
        ) as analyze:
            self.window._do_detect(expected=1)

        analyze.assert_called_once_with(
            "scan.tif",
            expected_frames=1,
            include_review_frames=True,
        )
        self.assertEqual(self.window._frames, [detected])
        self.assertIn("低置信度", self.window._status.currentMessage())


if __name__ == "__main__":
    unittest.main()
