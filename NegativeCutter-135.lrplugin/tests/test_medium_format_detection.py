import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from filmcrop import detector


class _TrackingImage:
    def __init__(self, image):
        self._image = image
        self.closed = False

    def __getattr__(self, name):
        return getattr(self._image, name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        self.closed = True
        self._image.close()


class MediumFormatRoutingTests(unittest.TestCase):
    def _should_use_120(self, width, height, expected_frames, film_format):
        if not hasattr(detector, "_should_use_120"):
            self.fail("detector._should_use_120 is not implemented")
        return detector._should_use_120(
            width,
            height,
            expected_frames,
            film_format,
        )

    def _analyze(self, *args, **kwargs):
        try:
            return detector.analyze_image(*args, **kwargs)
        except TypeError as exc:
            if "film_format" in str(exc):
                self.fail("analyze_image does not accept film_format")
            raise

    def test_explicit_645_uses_120_with_explicit_frame_count(self):
        use_120, reason = self._should_use_120(1000, 3000, 4, "645")

        self.assertTrue(use_120)
        self.assertEqual(reason, "explicit_format")

    def test_explicit_35mm_stays_on_135_route(self):
        use_120, reason = self._should_use_120(1000, 3000, 0, "35mm")

        self.assertFalse(use_120)
        self.assertEqual(reason, "explicit_35mm")

    def test_horizontal_auto_strip_uses_120_geometry_route(self):
        use_120, reason = self._should_use_120(3000, 1000, 0, None)

        self.assertTrue(use_120)
        self.assertEqual(reason, "auto_geometry")

    def test_vertical_auto_strip_uses_120_geometry_route(self):
        use_120, reason = self._should_use_120(1000, 3000, 0, None)

        self.assertTrue(use_120)
        self.assertEqual(reason, "auto_geometry")

    def test_explicit_frame_count_is_forwarded_to_120_detector(self):
        pixels = np.zeros((3000, 1000), dtype=np.uint8)
        sentinel = {"frameCount": 4, "frames": [], "debug": {}}

        with patch.object(
            detector,
            "_load_image_array",
            return_value=(pixels, "test"),
        ), patch.object(
            detector,
            "analyze_image_120",
            return_value=sentinel,
        ) as analyze_120:
            result = self._analyze(
                "scan.tif",
                expected_frames=4,
                aspect_ratio=4 / 3,
                film_format="645",
            )

        self.assertIs(result, sentinel)
        analyze_120.assert_called_once_with(
            "scan.tif",
            None,
            4 / 3,
            expected_frames_hint=4,
            film_format="645",
            route_reason="explicit_format",
        )

    def test_pillow_loader_closes_source_file(self):
        pixels = np.zeros((32, 96, 3), dtype=np.uint8)

        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "strip.tif"
            Image.fromarray(pixels).save(image_path)
            with Image.open(image_path) as source:
                tracked = _TrackingImage(source.copy())
            with patch.object(detector.Image, "open", return_value=tracked):
                detector._load_pillow_image_array(str(image_path))

        self.assertTrue(tracked.closed)


if __name__ == "__main__":
    unittest.main()
