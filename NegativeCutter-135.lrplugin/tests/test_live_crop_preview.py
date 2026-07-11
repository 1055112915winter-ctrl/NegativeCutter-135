import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN))

from filmcrop.preview import adjust_frames, render_preview


class LiveCropPreviewTests(unittest.TestCase):
    def test_adjust_frames_uses_canonical_oriented_pixel_math(self):
        frames = [{"index": 1, "relativeTop": .10, "relativeBottom": .90,
                   "relativeLeft": .20, "relativeRight": .80}]

        adjusted = adjust_frames(
            frames, 1000, 500,
            {"top": 10, "bottom": 20, "left": -30, "right": 40},
        )

        frame = adjusted[0]
        self.assertEqual((frame["top"], frame["bottom"], frame["left"], frame["right"]), (40, 470, 230, 840))
        self.assertEqual((frame["relativeTop"], frame["relativeBottom"], frame["relativeLeft"], frame["relativeRight"]), (.08, .94, .23, .84))

    def test_adjust_frames_prefers_canonical_relative_fields_over_stale_absolute_fields(self):
        frame = {"top": 1, "bottom": 2, "left": 3, "right": 4,
                 "relativeTop": .1, "relativeBottom": .9,
                 "relativeLeft": .2, "relativeRight": .8}

        adjusted = adjust_frames([frame], 100, 60, {"top": 0, "bottom": 0, "left": 0, "right": 0})[0]

        self.assertEqual((adjusted["top"], adjusted["bottom"], adjusted["left"], adjusted["right"]), (6, 54, 20, 80))

    def test_adjust_frames_clamps_and_enforces_minimum_twenty_pixels(self):
        frame = {"top": 2, "bottom": 3, "left": 98, "right": 99}

        adjusted = adjust_frames([frame], 100, 100, {"top": 90, "bottom": -90, "left": 90, "right": -90})[0]

        self.assertEqual((adjusted["top"], adjusted["bottom"]), (0, 20))
        self.assertEqual((adjusted["left"], adjusted["right"]), (8, 28))

    def test_adjust_frames_uses_full_axis_when_source_dimension_is_smaller_than_twenty(self):
        adjusted = adjust_frames(
            [{"top": 4, "bottom": 5, "left": 2, "right": 3}], 15, 10,
            {"top": 0, "bottom": 0, "left": 0, "right": 0},
        )[0]

        self.assertEqual((adjusted["top"], adjusted["bottom"], adjusted["left"], adjusted["right"]), (0, 10, 0, 15))

    def test_adjust_frames_ignores_non_finite_or_non_numeric_offsets(self):
        frame = {"top": 10, "bottom": 90, "left": 20, "right": 80}

        adjusted = adjust_frames(
            [frame], 100, 100,
            {"top": float("nan"), "bottom": float("inf"), "left": "bad", "right": None},
        )[0]

        self.assertEqual((adjusted["top"], adjusted["bottom"], adjusted["left"], adjusted["right"]), (10, 90, 20, 80))

    def test_adjust_frames_does_not_mutate_the_input(self):
        frames = [{"top": 10, "bottom": 90, "left": 20, "right": 80, "extra": {"keep": True}}]
        original = copy.deepcopy(frames)

        adjust_frames(frames, 100, 100, {"top": 5, "bottom": 5, "left": 5, "right": 5})

        self.assertEqual(frames, original)

    def test_adjust_frames_canonical_coordinates_are_orientation_independent(self):
        frames = [{"relativeTop": .1, "relativeBottom": .9, "relativeLeft": .2, "relativeRight": .8}]
        for orientation_name in ("normal", "rotated_180", "rotated_90_cw", "rotated_90_ccw"):
            with self.subTest(orientation=orientation_name):
                adjusted = adjust_frames(frames, 100, 50, {"top": 0, "bottom": 0, "left": 0, "right": 0})[0]
                self.assertEqual((adjusted["top"], adjusted["bottom"], adjusted["left"], adjusted["right"]), (5, 45, 20, 80))

    def test_render_preview_writes_labeled_jpeg_with_long_edge_at_most_1200(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.png"
            output = Path(temp_dir) / "preview.jpg"
            Image.new("RGB", (2400, 800), "white").save(source)

            render_preview(source, [{"index": 3, "top": 100, "bottom": 700, "left": 100, "right": 900}], output)

            with Image.open(output) as preview:
                self.assertEqual(preview.format, "JPEG")
                self.assertLessEqual(max(preview.size), 1200)
                self.assertNotEqual(preview.getpixel((50, 50)), (255, 255, 255))

    def test_render_preview_maps_relative_coordinates_to_the_actual_preview_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.png"
            output = Path(temp_dir) / "preview.jpg"
            Image.new("RGB", (100, 60), "white").save(source)

            render_preview(source, [{"index": 1, "left": 500, "top": 0, "right": 700,
                                     "bottom": 600, "relativeLeft": .5, "relativeTop": 0,
                                     "relativeRight": .7, "relativeBottom": 1}], output)

            with Image.open(output) as preview:
                self.assertNotEqual(preview.getpixel((50, 0)), (255, 255, 255))
                self.assertEqual(preview.getpixel((49, 30)), (255, 255, 255))

    def test_render_preview_module_does_not_import_detector(self):
        source = (PLUGIN / "filmcrop" / "preview.py").read_text(encoding="utf-8")
        self.assertNotIn("detector", source)

    def test_preview_import_does_not_load_any_recognition_module(self):
        code = """
import json
import sys
from pathlib import Path
sys.path.insert(0, {plugin!r})
import filmcrop.preview
print(json.dumps({{
    'filmcrop.detector': 'filmcrop.detector' in sys.modules,
    'negativecutter_core.detector': 'negativecutter_core.detector' in sys.modules,
}}, separators=(',', ':')))
""".format(plugin=str(PLUGIN))
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), {
            "filmcrop.detector": False,
            "negativecutter_core.detector": False,
        })

    def test_render_preview_cli_returns_compact_json_and_does_not_invoke_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = root / "input.png"; Image.new("RGB", (100, 60), "white").save(image)
            frames = root / "frames.json"; frames.write_text(json.dumps([{"index": 1, "top": 10, "bottom": 50, "left": 20, "right": 80}]), encoding="utf-8")
            output = root / "preview.jpg"
            proc = subprocess.run([
                sys.executable, str(PLUGIN / "detect_thumb.py"), "--render-preview", "--input", str(image),
                "--frames-json", str(frames), "--source-width", "100", "--source-height", "60",
                "--top-px", "0", "--bottom-px", "0", "--left-px", "0", "--right-px", "0", "--output", str(output),
            ], capture_output=True, text=True, check=False)

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stderr, "")
            payload = json.loads(proc.stdout)
            self.assertEqual(payload, {
                "previewPath": str(output),
                "frameCount": 1,
                "frames": [{"index": 1, "top": 10, "bottom": 50, "left": 20, "right": 80,
                            "relativeTop": 0.166667, "relativeBottom": 0.833333,
                            "relativeLeft": 0.2, "relativeRight": 0.8}],
            })
            self.assertTrue(output.is_file())

    def test_render_preview_cli_returns_json_error_and_exit_two_for_validation_failure(self):
        proc = subprocess.run(
            [sys.executable, str(PLUGIN / "detect_thumb.py"), "--render-preview"],
            capture_output=True, text=True, check=False,
        )

        self.assertEqual(proc.returncode, 2)
        self.assertIn("error", json.loads(proc.stdout))
        self.assertTrue(proc.stderr)


if __name__ == "__main__":
    unittest.main()
