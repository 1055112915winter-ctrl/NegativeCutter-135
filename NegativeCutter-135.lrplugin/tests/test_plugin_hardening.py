import os
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]


class PluginHardeningTests(unittest.TestCase):
    def _write_manifest(self, plugin: Path):
        entries = []
        for path in sorted(plugin.rglob("*")):
            if path.is_file() and path.name != "RELEASE-MANIFEST.sha256":
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                entries.append(f"{digest}  {path.relative_to(plugin).as_posix()}\n")
        (plugin / "RELEASE-MANIFEST.sha256").write_text("".join(entries), encoding="utf-8")

    def _fixture_plugin(self, root: Path, name="NegativeCutter-135.lrplugin"):
        plugin = root / name
        (plugin / "NegativeCutter").mkdir(parents=True)
        (plugin / "NegativeCutter" / "NegativeCutter").write_text(
            "#!/usr/bin/env sh\nexit 0\n", encoding="utf-8"
        )
        (plugin / "NegativeCutter" / "NegativeCutter").chmod(0o755)
        (plugin / "Info.lua").write_text("return {}\n", encoding="utf-8")
        self._write_manifest(plugin)
        return plugin

    def _codesign_env(self, root: Path, exit_code=0):
        bin_dir = root / "bin"
        bin_dir.mkdir(exist_ok=True)
        codesign = bin_dir / "codesign"
        codesign.write_text(f"#!/usr/bin/env sh\nexit {exit_code}\n", encoding="utf-8")
        codesign.chmod(0o755)
        return {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}

    def test_release_contracts_require_allowlist_manifest_and_fixture_smoke_gates(self):
        source = (PLUGIN / "build.sh").read_text(encoding="utf-8")
        for required in (
            "RELEASE-MANIFEST.sha256",
            "NEGATIVECUTTER_RELEASE_135_FIXTURE",
            "NEGATIVECUTTER_RELEASE_120_FIXTURE",
            "codesign --verify --deep --strict",
            "zipfile.ZipFile",
            "install.sh",
        ):
            self.assertIn(required, source)
        self.assertIn("exact release file set", source.lower())

    def test_install_rejects_malformed_or_tampered_manifest_before_target_change(self):
        installer = PLUGIN / "install.sh"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._fixture_plugin(root / "release")
            modules = root / "modules"
            modules.mkdir()
            target = modules / source.name
            target.mkdir()
            (target / "old.txt").write_text("old bytes", encoding="utf-8")
            before = (target / "old.txt").read_bytes()
            (source / "RELEASE-MANIFEST.sha256").write_text(
                "not-a-checksum  ../../escape\n", encoding="utf-8"
            )
            proc = subprocess.run(
                [str(installer), str(source)], env={**self._codesign_env(root), "NEGATIVECUTTER_MODULES_DIR": str(modules), "NEGATIVECUTTER_TEST_SKIP_CODESIGN": "1"},
                check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual((target / "old.txt").read_bytes(), before)

    def test_install_rejects_duplicate_extra_and_root_escaping_manifest_paths(self):
        installer = PLUGIN / "install.sh"
        cases = (
            "0" * 64 + "  Info.lua\n" + "0" * 64 + "  Info.lua\n",
            "0" * 64 + "  extra.txt\n",
            "0" * 64 + "  /absolute.txt\n",
            "0" * 64 + "  nested/../../escape.txt\n",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, manifest in enumerate(cases):
                with self.subTest(index=index):
                    source = self._fixture_plugin(root / str(index))
                    (source / "RELEASE-MANIFEST.sha256").write_text(manifest, encoding="utf-8")
                    modules = root / f"modules-{index}"; modules.mkdir()
                    target = modules / source.name; target.mkdir()
                    (target / "keep").write_bytes(b"unchanged")
                    proc = subprocess.run([str(installer), str(source)], env={**self._codesign_env(root), "NEGATIVECUTTER_MODULES_DIR": str(modules), "NEGATIVECUTTER_TEST_SKIP_CODESIGN": "1"}, check=False, capture_output=True, text=True)
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertEqual((target / "keep").read_bytes(), b"unchanged")

    def test_install_rejects_bad_signature_and_preserves_target(self):
        installer = PLUGIN / "install.sh"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._fixture_plugin(root / "release")
            modules = root / "modules"
            modules.mkdir()
            target = modules / source.name
            target.mkdir()
            (target / "old.txt").write_text("old bytes", encoding="utf-8")
            proc = subprocess.run(
                [str(installer), str(source)], env={**self._codesign_env(root, exit_code=1), "NEGATIVECUTTER_MODULES_DIR": str(modules)},
                check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual((target / "old.txt").read_text(encoding="utf-8"), "old bytes")

    def test_install_copies_verified_plugin_and_rolls_back_on_second_rename_failure(self):
        installer = PLUGIN / "install.sh"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._fixture_plugin(root / "release")
            modules = root / "modules"
            modules.mkdir()
            target = modules / source.name
            target.mkdir()
            (target / "old.txt").write_text("old bytes", encoding="utf-8")
            env = {**self._codesign_env(root), "NEGATIVECUTTER_MODULES_DIR": str(modules), "NEGATIVECUTTER_TEST_SKIP_CODESIGN": "1"}
            success = subprocess.run([str(installer), str(source)], env=env, check=False, capture_output=True, text=True)
            self.assertEqual(success.returncode, 0, success.stderr)
            self.assertFalse((target / "old.txt").exists())
            self.assertTrue((target / "NegativeCutter" / "NegativeCutter").is_file())

            (target / "old.txt").write_text("preserve me", encoding="utf-8")
            failed = subprocess.run(
                [str(installer), str(source)],
                env={**env, "NEGATIVECUTTER_TEST_FAIL_SECOND_RENAME": "1"},
                check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual((target / "old.txt").read_bytes(), b"preserve me")

    def test_install_restores_backup_after_post_swap_failure(self):
        installer = PLUGIN / "install.sh"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = self._fixture_plugin(root / "release")
            modules = root / "modules"; modules.mkdir(); target = modules / source.name; target.mkdir()
            (target / "old.bin").write_bytes(b"old target bytes\x00")
            env = {**self._codesign_env(root), "NEGATIVECUTTER_MODULES_DIR": str(modules), "NEGATIVECUTTER_TEST_SKIP_CODESIGN": "1", "NEGATIVECUTTER_TEST_FAIL_AFTER_SWAP": "1"}
            proc = subprocess.run([str(installer), str(source)], env=env, check=False, capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual((target / "old.bin").read_bytes(), b"old target bytes\x00")

    def test_release_fixture_override_is_a_regular_file(self):
        fixture = os.environ.get("NEGATIVECUTTER_RELEASE_135_FIXTURE")
        if fixture:
            self.assertTrue(Path(fixture).is_file())

    def test_build_defaults_required_release_fixtures_and_json_smoke_contract(self):
        source = (PLUGIN / "build.sh").read_text(encoding="utf-8")
        for required in ("52191.tif", "Untitled (3).tif", "--frames 6 --format 35mm --original", "--frames 4 --format 645 --original", "needsReview", "frameCount"):
            self.assertIn(required, source)

    def test_release_gates_both_fixture_smokes_before_archive_and_after_extract(self):
        source = (PLUGIN / "build.sh").read_text(encoding="utf-8")
        staged_120 = 'smoke "$STAGE/$PLUGIN_DIR" "$FIXTURE_120" 4 645'
        archive = '( cd "$STAGE" && zip -qr "$OUTPUT_ZIP" install.sh "$PLUGIN_DIR" )'
        extracted_135 = 'smoke "$EXTRACTED/$PLUGIN_DIR" "$FIXTURE_135" 6 35mm'
        self.assertLess(source.index(staged_120), source.index(archive))
        self.assertLess(source.index(archive), source.index(extracted_135))
        self.assertGreaterEqual(source.count("codesign --verify --deep --strict"), 2)
        self.assertIn("SOURCE_ALLOWLIST", source)

    def test_installer_exit_trap_rolls_back_until_commit(self):
        source = (PLUGIN / "install.sh").read_text(encoding="utf-8")
        self.assertIn("trap finish EXIT", source)
        self.assertIn("trap 'exit 1' INT TERM", source)
        self.assertLess(source.index("committed=1"), source.index("trap - EXIT INT TERM"))

    def test_build_signal_trap_cleans_up_and_fails(self):
        source = (PLUGIN / "build.sh").read_text(encoding="utf-8")
        self.assertIn("trap 'cleanup_failure; exit 1' INT TERM", source)

    def test_build_ad_hoc_signs_fresh_pyinstaller_runtime_before_staging(self):
        source = (PLUGIN / "build.sh").read_text(encoding="utf-8")
        build = "python3 -m PyInstaller NegativeCutter.spec"
        sign = "codesign --force --deep --sign - dist/NegativeCutter"
        stage = 'mkdir -p "$STAGE/$PLUGIN_DIR"'
        self.assertIn(sign, source)
        self.assertLess(source.index(build), source.index(sign))
        self.assertLess(source.index(sign), source.index(stage))

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
        self.assertIn("ALLOWLIST", source)
        self.assertIn("missing or symlinked allowlist entry", source)

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
