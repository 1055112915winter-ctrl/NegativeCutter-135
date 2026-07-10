import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from negativecutter_core.formats import (
    FILM_FORMATS,
    MEDIUM_FORMAT_CODES,
    format_aspect_ratio,
    format_family,
)
from negativecutter_core.medium_format import should_use_medium_format


class FormatRegistryTests(unittest.TestCase):
    def test_all_supported_120_formats_are_registered(self):
        self.assertEqual(
            MEDIUM_FORMAT_CODES,
            frozenset({"645", "6x6", "6x7", "6x8", "6x9"}),
        )
        self.assertTrue(all(FILM_FORMATS[code].family == "120" for code in MEDIUM_FORMAT_CODES))

    def test_equal_ratios_do_not_erase_format_family(self):
        self.assertEqual(format_aspect_ratio("35mm"), format_aspect_ratio("6x9"))
        self.assertEqual(format_family("35mm"), "135")
        self.assertEqual(format_family("6x9"), "120")

    def test_registry_uses_normalized_codes(self):
        self.assertEqual(format_family(" 6X7 "), "120")
        self.assertEqual(format_aspect_ratio(" 6X7 "), 7 / 6)
        self.assertIsNone(format_family(None))
        self.assertIsNone(format_aspect_ratio("unknown"))

    def test_medium_format_route_is_family_first_and_axis_independent(self):
        for code in MEDIUM_FORMAT_CODES:
            for width, height in ((3000, 1000), (1000, 3000)):
                with self.subTest(code=code, width=width, height=height):
                    self.assertEqual(
                        should_use_medium_format(width, height, 4, code),
                        (True, "explicit_format"),
                    )
        self.assertEqual(
            should_use_medium_format(3000, 1000, 0, "35mm"),
            (False, "explicit_35mm"),
        )
        self.assertEqual(
            should_use_medium_format(3000, 1000, 0, None),
            (True, "auto_geometry"),
        )


if __name__ == "__main__":
    unittest.main()
