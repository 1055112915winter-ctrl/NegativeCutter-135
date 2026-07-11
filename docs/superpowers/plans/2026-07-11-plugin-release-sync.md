# Plugin Release Synchronization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a Lightroom plugin ZIP whose bundled engine is rebuilt from the current source, proven against real 135/120 scans, and installed through a rollback-safe full replacement.

**Architecture:** `build.sh` becomes the release gate: it rebuilds the PyInstaller runtime, stages an explicit allowlist, emits a complete plugin-relative SHA-256 manifest, validates the staged and extracted release, then creates the ZIP. A new top-level `install.sh` validates the packaged manifest in a sibling staging directory and atomically replaces the installed plugin with backup/rollback protection.

**Tech Stack:** Bash, Python 3 standard library, PyInstaller, macOS `shasum`, `codesign`, `zip`/`unzip`, Python `unittest`.

---

### Task 1: Define release-sync contracts

**Files:**
- Modify: `NegativeCutter-135.lrplugin/tests/test_plugin_hardening.py`
- Modify: `NegativeCutter-135.lrplugin/build.sh`
- Create: `NegativeCutter-135.lrplugin/install.sh`

- [ ] **Step 1: Write failing static contract tests**

Add tests requiring `build.sh` to remove the stale runtime, invoke staged/extracted smoke validation, generate `RELEASE-MANIFEST.sha256`, require exact top-level ZIP entries, and reject `.claude`/`marketing`. Add tests requiring `install.sh` to use a sibling staging directory, `target -> backup -> target` replacement, rollback, trap cleanup, and manifest verification.

- [ ] **Step 2: Run the contract tests and confirm failure**

Run: `PYTHONPATH=NegativeCutter-135.lrplugin python3 -m unittest NegativeCutter-135.lrplugin/tests/test_plugin_hardening.py -v`

Expected: FAIL because the release manifest, staged/extracted checks, and canonical installer do not yet exist.

- [ ] **Step 3: Add minimal build/installer implementation**

Implement only the tested shell helpers: explicit staging allowlist, manifest writer/verifier, smoke validator, extracted ZIP validator, and rollback-safe installer. Keep fixture paths configurable through `NEGATIVECUTTER_RELEASE_135_FIXTURE` / `NEGATIVECUTTER_RELEASE_120_FIXTURE`.

- [ ] **Step 4: Re-run contract tests and shell syntax checks**

Run: `PYTHONPATH=NegativeCutter-135.lrplugin python3 -m unittest NegativeCutter-135.lrplugin/tests/test_plugin_hardening.py -v && bash -n NegativeCutter-135.lrplugin/build.sh && bash -n NegativeCutter-135.lrplugin/install.sh`

Expected: PASS, then both syntax checks exit 0.

### Task 2: Verify release gates with a real build

**Files:**
- Modify: `NegativeCutter-135.lrplugin/build.sh`
- Test: `NegativeCutter-135.lrplugin/tests/test_plugin_hardening.py`

- [ ] **Step 1: Run deterministic plugin and fixture regression suites**

Run: `scripts/run_unit_tests.sh && FILMCROP_FIXTURE_ROOT="$PWD/test_files" scripts/run_fixture_tests.sh`

Expected: existing detector, adapter, 135, DNG, and 120 tests pass before packaging.

- [ ] **Step 2: Build the release ZIP with real fixtures**

Run: `NEGATIVECUTTER_RELEASE_135_FIXTURE="$PWD/test_files/52191.tif" NEGATIVECUTTER_RELEASE_120_FIXTURE="$PWD/test_files/Untitled (3).tif" NegativeCutter-135.lrplugin/build.sh`

Expected: staged 135/120 smoke tests pass, ZIP extraction validation passes, and a single `NegativeCutter-135-v2.4.5.zip` is produced.

- [ ] **Step 3: Independently inspect final artifact**

Run: inspect ZIP inventory, manifest, extracted `codesign --verify --deep --strict`, and both extracted engine smoke outputs.

Expected: exactly `install.sh` and `NegativeCutter-135.lrplugin/` at ZIP root; no `.claude`, `marketing`, test/build/log artifacts; expected 6/4 safe-frame JSON outputs.

### Task 3: Document and hand off the install path

**Files:**
- Modify: `NegativeCutter-135.lrplugin/INSTALL.md`
- Modify: `NegativeCutter-135.lrplugin/README.md`
- Test: `NegativeCutter-135.lrplugin/tests/test_plugin_hardening.py`

- [ ] **Step 1: Add failing documentation-contract test if needed**

Require the installation documentation to name the packaged top-level `install.sh`, full replacement behavior, and Lightroom restart requirement.

- [ ] **Step 2: Update documentation minimally**

Replace obsolete manual-only/old ZIP version wording with the validated release installer workflow; retain manual Plugin Manager fallback.

- [ ] **Step 3: Run full verification suite**

Run: `scripts/run_unit_tests.sh && FILMCROP_FIXTURE_ROOT="$PWD/test_files" scripts/run_fixture_tests.sh && PYTHONPATH=NegativeCutter-135.lrplugin python3 -m unittest NegativeCutter-135.lrplugin/tests/test_plugin_hardening.py -v && bash -n NegativeCutter-135.lrplugin/build.sh && bash -n NegativeCutter-135.lrplugin/install.sh && git diff --check`

Expected: all checks exit 0.

- [ ] **Step 4: Commit deliberate source/docs changes**

Run: `git add NegativeCutter-135.lrplugin/build.sh NegativeCutter-135.lrplugin/install.sh NegativeCutter-135.lrplugin/tests/test_plugin_hardening.py NegativeCutter-135.lrplugin/INSTALL.md NegativeCutter-135.lrplugin/README.md docs/superpowers/plans/2026-07-11-plugin-release-sync.md && git commit -m "fix: synchronize plugin release runtime"`

Expected: a focused commit that does not include generated release ZIPs, runtime binaries, `marketing/`, `.claude/`, or sample files.
