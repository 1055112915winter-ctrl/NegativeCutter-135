# 120 Single-Strip Detection Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make v2.4.5 reliably route and detect single-strip 120 scans for automatic and explicit medium-format selections in either orientation.

**Architecture:** Preserve the film-format family at the CLI boundary and use it to select the existing isolated 120 detector. Extend the 120 detector only with an optional explicit frame-count hint and orientation-independent auto routing; leave the 135 pipeline untouched.

**Tech Stack:** Python 3, unittest, NumPy, Pillow, existing NegativeCutter detector and CLI.

---

### Task 1: Add failing plugin routing tests

**Files:**
- Create: NegativeCutter-135.lrplugin/tests/test_medium_format_detection.py
- Test: NegativeCutter-135.lrplugin/filmcrop/detector.py

- [ ] Write a test proving explicit 645 selects the 120 route even with four expected frames.
- [ ] Write a test proving a horizontal automatic medium-format strip selects the 120 route.
- [ ] Write a test proving explicit 35mm remains on the 135 route.
- [ ] Write a test proving an explicit frame count is forwarded to the 120 detector.
- [ ] Run the focused tests and verify they fail because the format code and frame hint are unsupported.

Run: PYTHONPATH=NegativeCutter-135.lrplugin python3 -m unittest NegativeCutter-135.lrplugin/tests/test_medium_format_detection.py -v

Expected: FAIL on the missing film_format and frame-count routing behavior.

### Task 2: Implement the minimal plugin route

**Files:**
- Modify: NegativeCutter-135.lrplugin/detect_thumb.py
- Modify: NegativeCutter-135.lrplugin/filmcrop/detector.py

- [ ] Add film_format to analyze_image().
- [ ] Pass the CLI format code through unchanged.
- [ ] Route explicit 120 codes to analyze_image_120().
- [ ] Replace the vertical-only auto heuristic with a long/short ratio check.
- [ ] Add an optional expected-frame hint to _detect_120_gaps() and analyze_image_120().
- [ ] Add route diagnostics without changing the frame schema.
- [ ] Run the focused test until green.
- [ ] Run all plugin Python tests, including the real raw0014 regression.

Expected: all tests pass; raw0014 remains six frames.

### Task 3: Keep standalone APP behavior aligned

**Files:**
- Modify: APP/filmcrop/detector.py
- Create: tests/test_gui_120_detection.py

- [ ] Add equivalent RED routing tests against the APP detector.
- [ ] Verify RED.
- [ ] Mirror the minimal routing and explicit-count behavior while preserving APP-only review-frame support.
- [ ] Verify the focused APP test is green.
- [ ] Run all test_gui_*.py tests.

Run: QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -p test_gui_*.py -v

Expected: all GUI tests pass.

### Task 4: Validate both real 120 fixtures

**Files:**
- Create: NegativeCutter-135.lrplugin/tests/test_medium_format_real_fixtures.py

- [ ] Add environment-gated tests for Untitled (3).tif and 未标题(1).tif.
- [ ] Assert four frames, no error, no review warning, three ordered gaps, and near-full cross-axis coverage.
- [ ] Run both real-fixture tests against the source detector.
- [ ] Run detect_thumb.py --frames 0 on both fixtures and parse stdout JSON.
- [ ] Generate final frame overlays from returned coordinates.

Expected: both fixtures produce four correct frames with full-width crops.

### Task 5: Documentation and final verification

**Files:**
- Modify: NegativeCutter-135.lrplugin/README.md
- Modify: NegativeCutter-135.lrplugin/INSTALL.md

- [ ] Replace the 135-only statement with the verified single-strip 120 scope.
- [ ] State that multi-row 120 remains unsupported.
- [ ] Run plugin tests, GUI tests, syntax checks, py_compile, and git diff --check.
- [ ] Inspect the final diff for unrelated changes.
- [ ] Record verified and unverified boundaries in the project handoff.

Expected: all applicable checks pass; no claim is made for double-row or real Lightroom E2E behavior.
