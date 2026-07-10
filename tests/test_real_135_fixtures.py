import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "APP"))

from filmcrop.detector import analyze_image


class Real135FixtureTests(unittest.TestCase):
    NAMES = ("52191.tif", "52194.tif", "SHD4001.tif", "luckyc20013.tif")

    def test_real_135_set_has_safe_six_frame_results(self):
        fixture_root_value = os.environ.get("NEGATIVECUTTER_TEST_135_DIR")
        if not fixture_root_value:
            self.skipTest("NEGATIVECUTTER_TEST_135_DIR is not set")
        fixture_root = Path(fixture_root_value)

        for name in self.NAMES:
            path = fixture_root / name
            with self.subTest(fixture=name):
                self.assertTrue(path.is_file(), path)
                result = analyze_image(
                    str(path),
                    expected_frames=6,
                    original_path=str(path),
                    aspect_ratio=3 / 2,
                    film_format="35mm",
                )
                self.assertNotIn("error", result)
                self.assertEqual(result["frameCount"], 6)
                self.assertFalse(result["needsReview"])
                self.assertLessEqual(abs(result["cropAngle"]), 3.0)
                self.assertIn("rotationEstimate", result["debug"])
                for frame in result["frames"][1:-1]:
                    width = frame["right"] - frame["left"]
                    height = frame["bottom"] - frame["top"]
                    ratio = max(width, height) / min(width, height)
                    self.assertAlmostEqual(ratio, 1.5, delta=0.01)


if __name__ == "__main__":
    unittest.main()
