import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LuaAdapterContractTests(unittest.TestCase):
    def test_shared_process_path_applies_crop_cleanup_once(self):
        source = (ROOT / "NegativeCutter-135.lrplugin" / "ProcessAgent.lua").read_text(
            encoding="utf-8"
        )
        call = "CropCleaner.cleanFrames(result.frames, previewWidth, previewHeight, filmType)"

        self.assertEqual(source.count(call), 1)
        self.assertLess(source.index(call), source.index("ProcessAgent.directionAlign(deepCopy(result), photo)"))


if __name__ == "__main__":
    unittest.main()
