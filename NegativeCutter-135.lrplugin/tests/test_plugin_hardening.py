import os
import subprocess
import sys
import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]


class PluginHardeningTests(unittest.TestCase):
    def test_api_module_imports_without_fastapi(self):
        code = f"""
import importlib.abc
import importlib.util
import sys

class BlockOptionalApi(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'fastapi' or fullname.startswith('fastapi.') or fullname == 'pydantic':
            raise ModuleNotFoundError(fullname)
        return None

sys.meta_path.insert(0, BlockOptionalApi())
spec = importlib.util.spec_from_file_location('filmcrop_api_without_fastapi', {str(PLUGIN / 'filmcrop' / 'api.py')!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(module.has_api())
"""
        proc = subprocess.run(
            [sys.executable, "-c", code],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "False")

    def test_cli_does_not_write_log_without_opt_in(self):
        legacy_log = PLUGIN / "detect_debug.log"
        legacy_log.unlink(missing_ok=True)
        env = os.environ.copy()
        env.pop("NEGATIVECUTTER_DEBUG_LOG", None)

        subprocess.run(
            [sys.executable, str(PLUGIN / "detect_thumb.py"), "/missing/input.dng"],
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertFalse(legacy_log.exists())

    def test_engine_runs_in_place_with_system_failure_fallback(self):
        source = (PLUGIN / "ProcessAgent.lua").read_text(encoding="utf-8")
        self.assertIn("local exePath = localExePath", source)
        self.assertIn(":gsub('%$', '\\\\$')", source)
        self.assertIn("isSystemFailure", source)
        self.assertIn("cp -RL", source)

    def test_release_menu_does_not_reference_test_scripts(self):
        info = (PLUGIN / "Info.lua").read_text(encoding="utf-8")
        self.assertNotIn('file = "tests/', info)

    def test_build_removes_and_rejects_development_artifacts(self):
        source = (PLUGIN / "build.sh").read_text(encoding="utf-8")
        for artifact in (
            "tests",
            "detect_debug.log",
            "debug_visualize.py",
            "CLAUDE.md",
            "WORK",
        ):
            self.assertIn(artifact, source)
        self.assertIn("rm -rf tests WORK", source)
        self.assertIn("forbidden", source.lower())
        self.assertIn('TMP_PACKAGE_DIR="${TMPDIR:-/tmp}/filmcrop-build-$$"', source)
        self.assertIn("Info.lua references missing files", source)

    def test_pyinstaller_spec_omits_removed_numpy_compatibility_modules(self):
        removed_modules = (
            "numpy.core._multiarray_tests",
            "numpy.core._operand_flag_tests",
            "numpy.core._rational_tests",
            "numpy.core._struct_ufunc_tests",
            "numpy.core._umath_tests",
            "numpy.core.memmap",
            "numpy.lib.polynomial",
            "numpy.lib.shape_base",
            "numpy.lib.twodim_base",
            "numpy.lib.type_check",
            "numpy.lib.ufunclike",
            "numpy.lib.utils",
        )
        specs = (PLUGIN / "NegativeCutter.spec", PLUGIN.parent / "APP" / "NegativeCutter.spec")
        for spec in specs:
            source = spec.read_text(encoding="utf-8")
            for module in removed_modules:
                self.assertNotIn(f"'{module}'", source, str(spec))


if __name__ == "__main__":
    unittest.main()
