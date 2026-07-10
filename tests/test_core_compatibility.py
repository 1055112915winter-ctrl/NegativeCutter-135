import importlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _import_product_detector(product_root: Path):
    for name in list(sys.modules):
        if name == "filmcrop" or name.startswith("filmcrop."):
            del sys.modules[name]
    original_path = list(sys.path)
    try:
        sys.path.insert(0, str(product_root))
        return importlib.import_module("filmcrop.detector")
    finally:
        sys.path[:] = original_path


class CoreCompatibilityTests(unittest.TestCase):
    def tearDown(self):
        for name in list(sys.modules):
            if name == "filmcrop" or name.startswith("filmcrop."):
                del sys.modules[name]

    def test_pyinstaller_specs_bundle_the_canonical_core(self):
        for spec_path in (
            ROOT / "APP" / "NegativeCutter.spec",
            ROOT / "NegativeCutter-135.lrplugin" / "NegativeCutter.spec",
        ):
            source = spec_path.read_text(encoding="utf-8")
            with self.subTest(spec=spec_path):
                self.assertIn("negativecutter_core.detector", source)
                self.assertIn("negativecutter_core.rotation", source)
                self.assertIn("negativecutter_core.formats", source)
                self.assertRegex(source, r"pathex=.*src")

    def test_app_detector_is_the_canonical_core_module(self):
        detector = _import_product_detector(ROOT / "APP")

        self.assertEqual(detector.__name__, "negativecutter_core.detector")
        self.assertEqual(detector.analyze_image.__module__, "negativecutter_core.detector")

    def test_plugin_detector_is_the_same_canonical_core_module(self):
        app_detector = _import_product_detector(ROOT / "APP")
        plugin_detector = _import_product_detector(ROOT / "NegativeCutter-135.lrplugin")

        self.assertIs(plugin_detector, app_detector)
        self.assertIs(plugin_detector.analyze_image, app_detector.analyze_image)
        self.assertIs(
            plugin_detector.estimate_rotation_with_diagnostics,
            app_detector.estimate_rotation_with_diagnostics,
        )


if __name__ == "__main__":
    unittest.main()
