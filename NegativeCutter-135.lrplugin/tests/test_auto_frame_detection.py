import os
import unittest
from pathlib import Path

from filmcrop.detector import analyze_image


class AutoFrameDetectionTests(unittest.TestCase):
    def test_raw0014_auto_detection_prefers_six_real_frames(self):
        fixture = os.environ.get("NEGATIVECUTTER_TEST_DNG")
        if not fixture:
            self.skipTest("NEGATIVECUTTER_TEST_DNG is not set")

        image_path = Path(fixture)
        self.assertTrue(image_path.is_file(), fixture)

        result = analyze_image(
            str(image_path),
            expected_frames=0,
            cleanup_scale=0.5,
            lr_width=28859,
            lr_height=3128,
        )

        self.assertEqual(result["debug"]["autoDetectedFrames"], 6)
        self.assertNotIn("error", result)
        self.assertEqual(result["frameCount"], 6)


if __name__ == "__main__":
    unittest.main()
