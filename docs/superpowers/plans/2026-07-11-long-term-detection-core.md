# FilmCrop Long-Term Detection Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make 135 rotation safe, establish one canonical detector core, and
ship verified single-strip 120 format routing without regressing real 135
fixtures.

**Architecture:** A root `negativecutter_core` package owns detector policy;
APP and Lightroom plugin packages become compatibility adapters. High-risk
rotation, format routing, and orientation behavior are extracted and tested,
while the verified 135 projection algorithm is preserved.

**Tech Stack:** Python 3.14, NumPy, Pillow, unittest, LuaJIT Lightroom mocks,
PyInstaller, shell packaging scripts.

---

### Task 1: Add 135 rotation regression and safety tests

**Files:**
- Create: `tests/test_rotation_safety.py`
- Create: `NegativeCutter-135.lrplugin/tests/test_applier_rotation_safety.lua`
- Modify: `NegativeCutter-135.lrplugin/tests/run_with_system_luajit.py`

- [ ] Add a synthetic low-resolution test that makes the legacy estimator
  return an unsafe angle and expects the public estimate to be rejected to 0.
- [ ] Add an inconsistent multi-gap test expecting rejection diagnostics.
- [ ] Add a consistent modest-skew test expecting a non-zero accepted angle.
- [ ] Add Lua cases for finite <=3-degree acceptance, >3-degree rejection,
  non-finite rejection, and existing <=0.5-degree cleanup.
- [ ] Run focused Python and Lua tests and verify RED for missing policy.

Run: `python3 -m unittest tests.test_rotation_safety -v`

Expected: FAIL because structured rotation validation is missing.

### Task 2: Implement the minimal rotation contract

**Files:**
- Create: `src/negativecutter_core/__init__.py`
- Create: `src/negativecutter_core/rotation.py`
- Modify: `APP/filmcrop/detector.py`
- Modify: `NegativeCutter-135.lrplugin/filmcrop/detector.py`
- Modify: `NegativeCutter-135.lrplugin/ApplierAgent.lua`

- [ ] Implement structured robust rotation estimates with resolution, sample,
  spread, prominence, and 3-degree safety gates.
- [ ] Keep the existing `estimate_rotation(...) -> float` facade.
- [ ] Add rotation diagnostics to detector debug output.
- [ ] Add the independent Lua application fuse.
- [ ] Run focused tests to GREEN, then run the four real 135 fixtures and prove
  frame geometry is unchanged.

### Task 3: Establish the canonical core and compatibility adapters

**Files:**
- Create: `tests/test_core_compatibility.py`
- Create: `src/negativecutter_core/detector.py`
- Create: `src/negativecutter_core/formats.py`
- Create: `src/negativecutter_core/medium_format.py`
- Modify: `APP/filmcrop/detector.py`
- Modify: `NegativeCutter-135.lrplugin/filmcrop/detector.py`
- Modify: `APP/NegativeCutter.spec`
- Modify: `NegativeCutter-135.lrplugin/NegativeCutter.spec`
- Modify: `APP/scripts/build_app.sh`
- Modify: `NegativeCutter-135.lrplugin/build.sh`

- [ ] Write RED tests proving APP and plugin adapters expose the same canonical
  detector functions and format registry.
- [ ] Move the APP detector superset into the canonical package.
- [ ] Move 120-specific functions into `medium_format.py` without behavior
  changes.
- [ ] Make both product detector modules thin compatibility adapters.
- [ ] Update build paths so PyInstaller includes `src` deterministically.
- [ ] Run compatibility, APP, plugin, syntax, and build-script tests.

### Task 4: Integrate and complete the 120 format matrix

**Files:**
- Modify: `src/negativecutter_core/formats.py`
- Modify: `src/negativecutter_core/medium_format.py`
- Modify: `NegativeCutter-135.lrplugin/detect_thumb.py`
- Modify: `tests/test_gui_120_detection.py`
- Modify: `NegativeCutter-135.lrplugin/tests/test_medium_format_detection.py`
- Modify: `NegativeCutter-135.lrplugin/tests/test_medium_format_real_fixtures.py`

- [ ] Preserve the already-green explicit-format and frame-hint tests.
- [ ] Add RED matrix cases for 645, 6x6, 6x7, 6x8, and 6x9 across both storage
  axes and for the 35mm/6x9 equal-ratio distinction.
- [ ] Implement the minimal registry-driven routing behavior.
- [ ] Run synthetic tests and both real 120 fixtures to GREEN.
- [ ] Prove raw0014 and four real 135 fixtures remain on the 135 path.

### Task 5: Make orientation mapping an explicit contract

**Files:**
- Create: `src/negativecutter_core/orientation.py`
- Create: `tests/test_orientation_contract.py`
- Modify: `NegativeCutter-135.lrplugin/ProcessAgent.lua`
- Modify: `NegativeCutter-135.lrplugin/tests/test_direction_align_fourway.lua`

- [ ] Write RED EXIF 1-8 rectangle round-trip/property tests.
- [ ] Encode AB/BC/CD/DA transforms and angle sign changes in one table-driven
  contract.
- [ ] Replace width/height-only decisions with explicit orientation delta when
  metadata is available; retain a documented fallback for absent metadata.
- [ ] Run Python properties, Lua formulas, and orientation 5/7 fixture checks.

### Task 6: Separate unit, fixture, and Lightroom E2E tests

**Files:**
- Create: `scripts/run_unit_tests.sh`
- Create: `scripts/run_fixture_tests.sh`
- Modify: `NegativeCutter-135.lrplugin/tests/test_dng_decode_gate.py`
- Modify: `.gitignore`

- [ ] Make the SubIFD test disable rawpy explicitly instead of depending on the
  developer environment.
- [ ] Ensure unit discovery cannot import scripts that operate Lightroom UI.
- [ ] Provide explicit fixture environment variables and commands.
- [ ] Keep Lightroom E2E opt-in and separately documented.
- [ ] Run both deterministic scripts from a clean shell.

### Task 7: Documentation and evidence-backed cleanup

**Files:**
- Create: `docs/ARCHITECTURE.md`
- Create: `docs/DETECTION_PIPELINE.md`
- Create: `docs/TESTING.md`
- Create: `docs/ADDING_FILM_FORMATS.md`
- Create: `docs/REPOSITORY_HYGIENE.md`
- Modify: `README.md`
- Modify: `NegativeCutter-135.lrplugin/README.md`
- Modify: `NegativeCutter-135.lrplugin/INSTALL.md`

- [ ] Document ownership, data flow, rotation safety, format registry, testing,
  packaging, and release boundaries.
- [ ] Produce a keep/consolidate/remove inventory with measured sizes.
- [ ] Remove only regenerated caches/previews and clean obsolete worktrees whose
  status and reachability have been verified.
- [ ] Do not delete fixtures, feedback evidence, or dirty worktrees.
- [ ] Run `git diff --check` and inspect the final tracked/untracked inventory.

### Task 8: Final verification

- [ ] Run deterministic unit tests.
- [ ] Run real 135/120 fixture tests and record frame counts, angles, ratios,
  route, and review flags.
- [ ] Run Lua adapter tests.
- [ ] Run package/build-script tests and a PyInstaller import smoke test.
- [ ] Verify APP/plugin API compatibility.
- [ ] Re-read the design and plan line by line; record any unmet boundary.
- [ ] Only then claim completion.
