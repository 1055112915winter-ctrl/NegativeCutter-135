import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "APP"))

from filmcrop import api


class FormatApiRoutingTests(unittest.TestCase):
    def test_api_preserves_6x9_family_instead_of_only_3_to_2_ratio(self):
        with tempfile.NamedTemporaryFile(suffix=".tif") as image_file:
            request = SimpleNamespace(
                image_path=image_file.name,
                expected_frames=4,
                cleanup_scale=0.5,
                original_path=None,
                aspect_ratio=None,
                format_hint="6x9",
                lr_width=None,
                lr_height=None,
            )
            with patch("filmcrop.detector.analyze_image", return_value={"frameCount": 4}) as analyze:
                result = api.analyze(request)

        self.assertEqual(result["frameCount"], 4)
        self.assertEqual(analyze.call_args.kwargs["aspect_ratio"], 3 / 2)
        self.assertEqual(analyze.call_args.kwargs["film_format"], "6x9")


if __name__ == "__main__":
    unittest.main()
