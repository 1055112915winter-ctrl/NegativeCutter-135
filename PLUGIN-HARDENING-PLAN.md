# NegativeCutter Plugin Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development and superpowers:verification-before-completion for every behavior change.

**Goal:** Fix the confirmed non-GUI reliability, packaging, and detection issues without overlapping the concurrent GUI refresh.

**Architecture:** Keep Lightroom orchestration in Lua and detector behavior in Python. Add small testable helpers for runtime cache identity and auto-frame scoring, move diagnostics to an opt-in temp location, and make the release build explicitly remove development artifacts before validating the staged package.

**Tech Stack:** Lightroom Lua SDK, Python 3, NumPy/Pillow/rawpy, Bash, unittest.

---

### Task 1: Establish committed regression tests

**Files:**
- Create: `NegativeCutter-135.lrplugin/tests/test_plugin_hardening.py`
- Create: `NegativeCutter-135.lrplugin/tests/test_auto_frame_detection.py`

- [x] Add tests for FastAPI-absent import, debug logging defaults, runtime cache version identity, and release exclusions.
- [x] Add a raw0014 auto-frame regression test using `NEGATIVECUTTER_TEST_DNG` so the large fixture remains external.
- [x] Run each test and confirm it fails for the intended missing behavior.

### Task 2: Fix auto-frame selection

**Files:**
- Modify: `NegativeCutter-135.lrplugin/filmcrop/detector.py`
- Test: `NegativeCutter-135.lrplugin/tests/test_auto_frame_detection.py`

- [x] Reject over-segmented candidates whose inter-frame gaps are implausibly narrow relative to candidate pitch.
- [x] Confirm raw0014 returns six frames in auto mode and retains explicit `--frames 6` behavior.

### Task 3: Version the Lightroom runtime cache

**Files:**
- Modify: `NegativeCutter-135.lrplugin/ProcessAgent.lua`
- Test: `NegativeCutter-135.lrplugin/tests/test_plugin_hardening.py`

- [x] Derive the runtime directory from the plugin version or a build-generated bundle identifier.
- [x] Keep manifest completeness validation and the single rebuild retry.
- [x] Ensure concurrent versions cannot silently reuse the same cached engine.

### Task 4: Make diagnostics opt-in and private

**Files:**
- Modify: `NegativeCutter-135.lrplugin/detect_thumb.py`
- Test: `NegativeCutter-135.lrplugin/tests/test_plugin_hardening.py`

- [x] Disable file logging unless `NEGATIVECUTTER_DEBUG_LOG` is explicitly set.
- [x] Write only to the requested path and cap retained output.
- [x] Keep JSON stdout diagnostics required by Lightroom.

### Task 5: Harden optional API import

**Files:**
- Modify: `NegativeCutter-135.lrplugin/filmcrop/api.py`
- Test: `NegativeCutter-135.lrplugin/tests/test_plugin_hardening.py`

- [x] Allow module import when FastAPI/Pydantic are unavailable.
- [x] Register routes only when the optional dependencies exist.
- [x] Keep `has_api()` and `run_server()` behavior explicit.

### Task 6: Clean and validate the release stage

**Files:**
- Modify: `NegativeCutter-135.lrplugin/build.sh`
- Test: `NegativeCutter-135.lrplugin/tests/test_plugin_hardening.py`

- [x] Remove tests, debug logs, local instructions, work directories, and debug scripts from staging.
- [x] Fail the build if `Info.lua` references a staged file that is absent.
- [x] Fail the build if forbidden development artifacts remain.

### Task 7: Full verification and handoff

- [x] Run Python unit tests.
- [x] Run the packaged detector against raw0014.
- [x] Run shell syntax validation and build-stage tests.
- [x] Review the branch diff for GUI overlap.
- [x] Write a handoff listing changed files, verified behavior, and merge/review instructions for the GUI branch.
