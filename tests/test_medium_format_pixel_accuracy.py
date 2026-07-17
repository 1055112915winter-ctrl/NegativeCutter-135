import hashlib
import json
import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from negativecutter_core.detector import analyze_image


TRUTH_PATH = ROOT / "tests" / "fixtures" / "120_edge_truth.json"


def distance_to_band(value, band):
    low, high = band
    if value < low:
        return low - value
    if value > high:
        return value - high
    return 0


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class MediumFormatPixelAccuracyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.truth = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))

    def _fixture(self, entry):
        value = os.environ.get(entry["environmentVariable"])
        if not value:
            self.skipTest(f"{entry['environmentVariable']} is not set")
        path = Path(value)
        self.assertTrue(path.is_file(), path)
        self.assertEqual(sha256(path), entry["sha256"])
        return path

    def test_auto_120_edges_stay_inside_reviewed_pixel_bands(self):
        for entry in self.truth["fixtures"]:
            with self.subTest(fixture=entry["fileName"]):
                path = self._fixture(entry)
                result = analyze_image(
                    str(path),
                    expected_frames=0,
                    original_path=str(path),
                    aspect_ratio=None,
                )
                self.assertEqual(result["frameCount"], entry["frameCount"])
                gaps = result["debug"]["gapEdges"]
                self.assertEqual(len(gaps), len(entry["gapEdgeBands"]))
                for actual, expected in zip(gaps, entry["gapEdgeBands"]):
                    self.assertEqual(distance_to_band(actual[0], expected["left"]), 0)
                    self.assertEqual(distance_to_band(actual[1], expected["right"]), 0)

                near, far = result["debug"]["longEdges"]
                cross = entry["crossAxisEdgeBands"]
                self.assertEqual(distance_to_band(near, cross["near"]), 0)
                self.assertEqual(distance_to_band(far, cross["far"]), 0)


if __name__ == "__main__":
    unittest.main()
