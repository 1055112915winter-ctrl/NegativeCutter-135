import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = ROOT / "scripts" / "verify_non_computer_use.sh"


class TestCommandContractTests(unittest.TestCase):
    def test_unit_runner_has_only_deterministic_test_groups(self):
        source = (ROOT / "scripts" / "run_unit_tests.sh").read_text(encoding="utf-8")

        self.assertNotIn("discover -s NegativeCutter-135.lrplugin/tests -p 'test_*.py'", source)
        self.assertNotIn("test_real_135_fixtures.py", source)
        self.assertNotIn("test_medium_format_pixel_accuracy.py", source)
        self.assertNotIn("test_medium_format_real_fixtures.py", source)
        self.assertNotIn("test_auto_frame_detection.py", source)
        self.assertIn("test_plugin_hardening.py", source)
        self.assertIn("test_medium_format_detection.py", source)
        self.assertIn("test_applier_rotation_safety.lua", source)
        self.assertIn("test_process_agent_orientation.lua", source)
        self.assertTrue(
            (ROOT / "NegativeCutter-135.lrplugin/tests/test_applier_rotation_safety.lua").is_file()
        )
        self.assertTrue(
            (ROOT / "NegativeCutter-135.lrplugin/tests/test_process_agent_orientation.lua").is_file()
        )

    def test_fixture_runner_declares_all_real_recognition_assets(self):
        source = (ROOT / "scripts" / "run_fixture_tests.sh").read_text(encoding="utf-8")

        self.assertIn("NEGATIVECUTTER_TEST_DNG", source)
        self.assertIn("NEGATIVECUTTER_TEST_120_A", source)
        self.assertIn("NEGATIVECUTTER_TEST_120_B", source)
        self.assertIn("tests.test_real_135_fixtures", source)
        self.assertIn("tests.test_medium_format_pixel_accuracy", source)
        self.assertIn("test_auto_frame_detection.py", source)
        self.assertIn("test_medium_format_real_fixtures.py", source)

    def test_every_root_test_file_is_classified(self):
        root_tests = {
            path.name
            for path in (ROOT / "tests").glob("test_*.py")
            if path.name != "test_test_commands.py"
        }
        deterministic = {
            "test_core_compatibility.py",
            "test_format_api_routing.py",
            "test_format_registry.py",
            "test_lua_adapter_contracts.py",
            "test_medium_format_gap_refinement.py",
            "test_orientation_contract.py",
            "test_package_app.py",
            "test_rotation_safety.py",
        }
        deterministic.update(
            path.name for path in (ROOT / "tests").glob("test_gui_*.py")
        )
        fixture = {
            "test_medium_format_pixel_accuracy.py",
            "test_real_135_fixtures.py",
        }
        self.assertEqual(root_tests, deterministic | fixture)

    def test_non_computer_use_driver_is_the_composed_entrypoint(self):
        self.assertTrue(VERIFY_SCRIPT.is_file())
        self.assertTrue(VERIFY_SCRIPT.stat().st_mode & 0o111)
        source = VERIFY_SCRIPT.read_text(encoding="utf-8")
        for required in (
            "run_unit_tests.sh",
            "run_fixture_tests.sh",
            "PYTHONPYCACHEPREFIX",
            "compileall",
            'git -C "$ROOT" diff --check',
        ):
            self.assertIn(required, source)


if __name__ == "__main__":
    unittest.main()
