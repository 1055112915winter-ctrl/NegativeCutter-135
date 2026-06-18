import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "APP/scripts/package_app.sh"


class PackageAppScriptTest(unittest.TestCase):
    def test_script_exposes_expected_cli(self):
        self.assertTrue(SCRIPT.is_file())
        self.assertTrue(SCRIPT.stat().st_mode & 0o111)

        result = subprocess.run(
            [str(SCRIPT), "--help"],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("--target-arch", result.stdout)
        self.assertNotIn("--no-open", result.stdout)

    def test_script_builds_without_launching_application(self):
        source = SCRIPT.read_text(encoding="utf-8")
        steps = [
            "python3 -m unittest discover",
            '"$BUILD_SCRIPT"',
            "codesign --verify --deep --strict",
        ]
        positions = [source.index(step) for step in steps]

        self.assertEqual(positions, sorted(positions))
        self.assertIn("set -euo pipefail", source)
        self.assertIn('if [[ ${#BUILD_ARGS[@]} -gt 0 ]]', source)
        self.assertNotIn('open "$APP_BUNDLE"', source)


if __name__ == "__main__":
    unittest.main()
