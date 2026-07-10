import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from filmcrop.detector import analyze_image


PLUGIN = Path(__file__).resolve().parents[1]


class MediumFormatRealFixtureTests(unittest.TestCase):
    def _fixtures(self):
        paths = []
        for variable in (
            "NEGATIVECUTTER_TEST_120_A",
            "NEGATIVECUTTER_TEST_120_B",
        ):
            value = os.environ.get(variable)
            if not value:
                self.skipTest(f"{variable} is not set")
            path = Path(value)
            self.assertTrue(path.is_file(), path)
            paths.append(path)
        return paths

    def _assert_four_frame_result(self, result):
        self.assertNotIn("error", result)
        self.assertEqual(result["frameCount"], 4)
        self.assertFalse(result["needsReview"])
        self.assertEqual(len(result["debug"]["gapEdges"]), 3)

        gaps = result["debug"]["gapEdges"]
        self.assertTrue(all(left < right for left, right in gaps))
        self.assertEqual(gaps, sorted(gaps))

        near, far = result["debug"]["longEdges"]
        cross_size = (
            result["sourceHeight"]
            if result["debug"]["isHorizontal"]
            else result["sourceWidth"]
        )
        self.assertGreaterEqual((far - near) / cross_size, 0.95)

    def test_auto_mode_detects_both_four_frame_120_strips(self):
        for fixture in self._fixtures():
            with self.subTest(fixture=fixture.name):
                result = analyze_image(
                    str(fixture),
                    expected_frames=0,
                    original_path=str(fixture),
                    aspect_ratio=None,
                )

                self._assert_four_frame_result(result)
                self.assertEqual(result["debug"]["routeReason"], "auto_geometry")
                self.assertIsNone(result["debug"]["expectedFramesHint"])

    def test_cli_explicit_645_and_four_frames_use_120_route(self):
        for fixture in self._fixtures():
            with self.subTest(fixture=fixture.name):
                proc = subprocess.run(
                    [
                        sys.executable,
                        str(PLUGIN / "detect_thumb.py"),
                        str(fixture),
                        "--frames",
                        "4",
                        "--format",
                        "645",
                        "--original",
                        str(fixture),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertEqual(proc.returncode, 0, proc.stderr)
                result = json.loads(proc.stdout)
                self._assert_four_frame_result(result)
                self.assertEqual(result["debug"]["routeReason"], "explicit_format")
                self.assertEqual(result["debug"]["filmFormat"], "645")
                self.assertEqual(result["debug"]["expectedFramesHint"], 4)


if __name__ == "__main__":
    unittest.main()
