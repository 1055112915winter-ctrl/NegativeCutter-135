import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "APP"))

from filmcrop.export import crop_and_save
from filmcrop._vendor import tifffile


class GuiColorExportTest(unittest.TestCase):
    def test_tiff_export_preserves_16bit_rgb_samples(self):
        source = FIXTURES / "rgb16_top_left.tif"
        frame = {
            "index": 1,
            "left": 2,
            "top": 2,
            "right": 14,
            "bottom": 10,
        }

        with tempfile.TemporaryDirectory() as tmp:
            with Image.open(source) as source_image:
                source_icc = source_image.info.get("icc_profile")
            [written] = crop_and_save(
                str(source),
                [frame],
                tmp,
                fmt="tiff",
                color_space="preserve",
            )
            with Image.open(written) as exported:
                bits_per_sample = exported.tag_v2.get(258)
                self.assertEqual(exported.mode, "RGB")
                self.assertEqual(tuple(bits_per_sample), (16, 16, 16))
                self.assertEqual(
                    exported.info.get("icc_profile"),
                    source_icc,
                )
                color = exported.getpixel((4, 3))

        self.assertNotEqual(color[0], color[1])
        self.assertNotEqual(color[1], color[2])

    def test_untagged_16bit_tiff_export_remains_untagged(self):
        pixels = np.zeros((8, 12, 3), dtype=np.uint16)
        pixels[:, :, 0] = 50000
        pixels[:, :, 1] = 25000
        frame = {"index": 1, "left": 2, "top": 1, "right": 10, "bottom": 7}

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "untagged.tif"
            tifffile.imwrite(source, pixels, photometric="rgb", metadata=None)
            [written] = crop_and_save(str(source), [frame], tmp, fmt="tiff")
            with Image.open(written) as exported:
                self.assertIsNone(exported.info.get("icc_profile"))

    def test_tiff_export_uses_same_orientation_as_gui_coordinates(self):
        source = FIXTURES / "rgb16_orientation7.tif"
        frame = {
            "index": 1,
            "left": 1,
            "top": 2,
            "right": 7,
            "bottom": 8,
        }
        with Image.open(source) as displayed_source:
            expected = displayed_source.getpixel((3, 4))

        with tempfile.TemporaryDirectory() as tmp:
            [written] = crop_and_save(str(source), [frame], tmp, fmt="tiff")
            with Image.open(written) as exported:
                self.assertEqual(exported.size, (6, 6))
                self.assertEqual(tuple(exported.tag_v2.get(258)), (16, 16, 16))
                actual = exported.getpixel((2, 2))

        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
