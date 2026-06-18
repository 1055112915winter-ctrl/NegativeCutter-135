import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "APP"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from filmcrop.detector import analyze_image


class GuiDetectionReviewTest(unittest.TestCase):
    def test_detector_can_return_reviewable_frames_for_manual_gui_editing(self):
        height, width = 1200, 300
        pixels = np.full((height, width, 3), 220, dtype=np.uint8)
        pixels[:, :15] = 15
        pixels[:, -15:] = 15
        for index, start in enumerate((20, 215, 410, 605, 800, 995)):
            pixels[start : start + 175, 20:280] = 50 + index * 15

        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "strip.png"
            Image.fromarray(pixels).save(image_path)
            with patch("filmcrop.detector._FRAME_CONFIDENCE_REVIEW_THRESHOLD", 1.0):
                result = analyze_image(
                    str(image_path),
                    expected_frames=6,
                    include_review_frames=True,
                )

        self.assertTrue(result["needsReview"])
        self.assertIn("error", result)
        self.assertEqual(result["frameCount"], 6)
        self.assertEqual(len(result["frames"]), 6)


if __name__ == "__main__":
    unittest.main()
