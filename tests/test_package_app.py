import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "APP/scripts/package_app.sh"
BUILD_SCRIPT = ROOT / "APP/scripts/build_app.sh"
SPEC = ROOT / "APP/NegativeCutter.spec"


VER = "2.4.5"


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
        self.assertIn("--version", result.stdout)
        self.assertNotIn("--no-open", result.stdout)

    def test_build_script_exposes_version_flag(self):
        source = BUILD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("--version", source)
        self.assertIn("VERSION=$(python3", source)
        self.assertIn("from filmcrop import __version__", source)

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

    def test_main_window_displays_version(self):
        mw = ROOT / "APP/filmcrop/gui/main_window.py"
        source = mw.read_text(encoding="utf-8")
        self.assertIn("from filmcrop import __version__", source)
        self.assertIn('"NegativeCutter v{__version__}"', source)

    def test_build_generates_canonical_icon_before_pyinstaller(self):
        source = BUILD_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('python3 "${APP_DIR}/generate_icns.py"', source)
        generate_pos = source.index('python3 "${APP_DIR}/generate_icns.py"')
        pyinstaller_pos = source.index("python3 -m PyInstaller")

        self.assertLess(generate_pos, pyinstaller_pos)
        self.assertIn('ICON="${APP_DIR}/NegativeCutter.icns"', source)
        self.assertIn('if [[ ! -f "$ICON" ]]', source)

    def test_spec_requires_local_icon_without_worktree_fallback(self):
        source = SPEC.read_text(encoding="utf-8")

        self.assertIn("os.path.join(app_dir, 'NegativeCutter.icns')", source)
        self.assertIn("raise FileNotFoundError", source)
        self.assertNotIn(".claude", source)
        self.assertNotIn("worktrees", source)


if __name__ == "__main__":
    unittest.main()
