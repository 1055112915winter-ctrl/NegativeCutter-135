import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestCommandContractTests(unittest.TestCase):
    def test_unit_runner_never_discovers_lightroom_e2e_scripts(self):
        source = (ROOT / "scripts" / "run_unit_tests.sh").read_text(encoding="utf-8")

        self.assertNotIn("discover -s NegativeCutter-135.lrplugin/tests -p 'test_*.py'", source)
        self.assertIn("test_plugin_hardening.py", source)
        self.assertIn("test_medium_format_detection.py", source)
        self.assertIn("test_applier_rotation_safety.lua", source)
        self.assertIn("test_process_agent_orientation.lua", source)

    def test_fixture_runner_declares_all_real_recognition_assets(self):
        source = (ROOT / "scripts" / "run_fixture_tests.sh").read_text(encoding="utf-8")

        self.assertIn("NEGATIVECUTTER_TEST_DNG", source)
        self.assertIn("NEGATIVECUTTER_TEST_120_A", source)
        self.assertIn("NEGATIVECUTTER_TEST_120_B", source)
        self.assertIn("tests.test_real_135_fixtures", source)


if __name__ == "__main__":
    unittest.main()
