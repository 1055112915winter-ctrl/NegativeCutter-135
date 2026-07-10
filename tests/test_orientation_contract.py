import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from negativecutter_core.orientation import transform_angle, transform_rect


class OrientationContractTests(unittest.TestCase):
    RECT = (0.1, 0.4, 0.0, 0.6)

    def test_ab_is_identity(self):
        self.assertEqual(transform_rect(self.RECT, "AB"), self.RECT)
        self.assertEqual(transform_angle(1.25, "AB"), 1.25)

    def test_bc_is_clockwise_quarter_turn(self):
        self.assertEqual(transform_rect(self.RECT, "BC"), (0.4, 1.0, 0.1, 0.4))
        self.assertEqual(transform_angle(1.25, "BC"), -1.25)

    def test_cd_is_half_turn(self):
        self.assertEqual(transform_rect(self.RECT, "CD"), (0.6, 0.9, 0.4, 1.0))
        self.assertEqual(transform_angle(1.25, "CD"), 1.25)

    def test_da_is_counterclockwise_quarter_turn(self):
        self.assertEqual(transform_rect(self.RECT, "DA"), (0.0, 0.6, 0.6, 0.9))
        self.assertEqual(transform_angle(1.25, "DA"), -1.25)

    def test_four_quarter_turns_round_trip(self):
        rect = self.RECT
        for _ in range(4):
            rect = transform_rect(rect, "BC")
        for expected, actual in zip(self.RECT, rect):
            self.assertAlmostEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
