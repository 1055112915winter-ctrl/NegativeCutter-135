import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from negativecutter_core.detector import _refine_120_gap_edges_multiband


class MediumFormatGapRefinementTests(unittest.TestCase):
    def test_three_band_consensus_rejects_a_single_band_scene_edge(self):
        pixels = np.full((1200, 300), 50, dtype=np.uint8)
        true_edges = [(360, 430), (370, 440), (370, 440)]
        for band, (left, right) in enumerate(true_edges):
            x0 = band * 100
            x1 = x0 + 100
            pixels[left:right, x0:x1] = 220

        # A stronger content stripe exists only in the first band. Median
        # consensus must still follow the two agreeing film-gap positions.
        pixels[350:355, :100] = 255

        refined = _refine_120_gap_edges_multiband(
            pixels,
            False,
            [(365, 445)],
            pitch=400,
            film_region=(0, 300),
        )

        self.assertEqual(refined, [(370, 440)])


if __name__ == "__main__":
    unittest.main()
