import math
import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from negativecutter_core.rotation import evaluate_rotation_offsets

sys.path.insert(0, str(ROOT / "APP"))
from filmcrop import detector


class RotationSafetyTests(unittest.TestCase):
    @staticmethod
    def _under_resolved_strip():
        pixels = np.zeros((34, 320), dtype=np.uint8)
        for frame in range(1, 8):
            base = frame * 40
            pixels[8:17, base - 1 : base + 2] = 255
            pixels[17:25, base + 1 : base + 4] = 255
        return pixels

    def test_detector_facade_reports_and_rejects_under_resolved_rotation(self):
        estimate = detector.estimate_rotation_with_diagnostics(
            self._under_resolved_strip(),
            expected_frames=8,
            width=320,
            height=34,
            is_horizontal=True,
            mode="peak",
        )

        self.assertEqual(estimate.angle, 0.0)
        self.assertGreater(abs(estimate.candidate_angle), 8.0)
        self.assertEqual(estimate.rejection_reason, "under_resolved")

    def test_under_resolved_measurement_rejects_historical_large_angle_shape(self):
        estimate = evaluate_rotation_offsets(
            offsets=[1, 2, 2, 1, 2, 1, 2],
            cross_baseline=8.5,
            cross_resolution=34,
            prominences=[0.4] * 7,
        )

        self.assertGreater(abs(estimate.candidate_angle), 8.0)
        self.assertEqual(estimate.angle, 0.0)
        self.assertFalse(estimate.accepted)
        self.assertEqual(estimate.rejection_reason, "under_resolved")

    def test_inconsistent_gap_offsets_are_rejected(self):
        estimate = evaluate_rotation_offsets(
            offsets=[8, -7, 10, -6, 9],
            cross_baseline=250.0,
            cross_resolution=1000,
            prominences=[0.5] * 5,
        )

        self.assertEqual(estimate.angle, 0.0)
        self.assertFalse(estimate.accepted)
        self.assertEqual(estimate.rejection_reason, "inconsistent_offsets")

    def test_consistent_modest_skew_is_preserved(self):
        estimate = evaluate_rotation_offsets(
            offsets=[4, 4, 5, 4, 4],
            cross_baseline=250.0,
            cross_resolution=1000,
            prominences=[0.5, 0.6, 0.55, 0.5, 0.6],
        )

        self.assertTrue(estimate.accepted)
        self.assertIsNone(estimate.rejection_reason)
        self.assertAlmostEqual(estimate.angle, math.degrees(math.atan2(4, 250)), places=6)

    def test_implausible_angle_is_rejected_even_when_offsets_agree(self):
        estimate = evaluate_rotation_offsets(
            offsets=[20, 20, 21, 20, 20],
            cross_baseline=250.0,
            cross_resolution=1000,
            prominences=[0.6] * 5,
        )

        self.assertGreater(abs(estimate.candidate_angle), 3.0)
        self.assertEqual(estimate.angle, 0.0)
        self.assertEqual(estimate.rejection_reason, "angle_limit")


if __name__ == "__main__":
    unittest.main()
