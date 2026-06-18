# DNG sRGB-Preserving Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export DNG crops as pixel-preserving 16-bit sRGB TIFFs with ICC metadata, preserve ordinary TIFF color metadata honestly, and reuse the coordinate button for DNG sidecars.

**Architecture:** Make rawpy's sRGB contract explicit at decode time, attach a generated standard sRGB ICC profile to the temporary TIFF, and rely on the existing array-slice export path to preserve samples and profile bytes. Keep TIFF handling profile-preserving rather than assuming an unknown space, and make the coordinate button label source-format aware.

**Tech Stack:** Python 3.14, rawpy, Pillow/ImageCms, vendored tifffile, PyQt6, unittest, PyInstaller.

---

### Task 1: Explicit DNG sRGB contract

**Files:**
- Modify: `tests/test_gui_dng_color.py`
- Modify: `APP/filmcrop/detector.py`

- [ ] Add a test asserting `raw.postprocess()` receives `output_bps=16` and `output_color=rawpy.ColorSpace.sRGB`.
- [ ] Run `QT_QPA_PLATFORM=offscreen PYTHONPATH=APP python3 -m unittest tests.test_gui_dng_color -v` and confirm the new assertion fails because `output_color` is absent.
- [ ] Add the explicit `output_color` argument with no other rawpy behavior changes.
- [ ] Re-run the targeted test and confirm it passes.

### Task 2: ICC-tagged DNG temporary and cropped TIFFs

**Files:**
- Modify: `tests/test_gui_dng_color.py`
- Modify: `APP/filmcrop/gui/main_window.py`

- [ ] Extend the DNG GUI test to assert the temporary TIFF contains an ICC profile, the export contains identical ICC bytes, and crop samples equal the corresponding temporary samples.
- [ ] Run the targeted test and confirm it fails because the temporary TIFF is untagged.
- [ ] Add a small helper that creates standard sRGB ICC bytes through Pillow/ImageCms.
- [ ] Pass ICC bytes to tifffile as TIFF tag 34675 when writing the 16-bit RGB DNG temporary TIFF.
- [ ] Re-run the targeted test and confirm it passes.

### Task 3: Honest ordinary TIFF color-space handling

**Files:**
- Modify: `tests/test_gui_color_export.py`
- Modify: `tests/test_gui_frame_editing.py`
- Modify: `APP/filmcrop/gui/main_window.py`

- [ ] Add tests proving an untagged 16-bit TIFF export remains untagged and its GUI source color space is `色彩空间未知`.
- [ ] Run the targeted tests and confirm the GUI test fails because missing ICC currently maps to sRGB.
- [ ] Change the missing-profile label to `色彩空间未知`; retain existing ICC detection and export preservation.
- [ ] Re-run targeted tests and confirm they pass.

### Task 4: Source-aware coordinate button

**Files:**
- Modify: `tests/test_gui_frame_editing.py`
- Modify: `APP/filmcrop/gui/main_window.py`

- [ ] Add tests asserting the button label becomes `导出原始 DNG 坐标` for DNG and remains `保存坐标数据` for TIFF.
- [ ] Run the tests and confirm the DNG assertion fails.
- [ ] Update the label after successful image loading based on source suffix; do not change `_on_export_json()` behavior.
- [ ] Re-run targeted tests and confirm they pass.

### Task 5: Full verification and handoff

**Files:**
- Modify: `.claude/handoffs/negativecutter-standalone-gui-v2.4.4-final-20260611.md`
- Modify: `task_plan.md`
- Modify: `findings.md`
- Modify: `progress.md`

- [ ] Run `QT_QPA_PLATFORM=offscreen PYTHONPATH=APP python3 -m unittest discover -s tests -p 'test_gui_*.py' -v`.
- [ ] Run `PYTHONPATH=APP python3 -m unittest discover -s tests -p 'test_package_app.py' -v`.
- [ ] Run `APP/scripts/package_app.sh`.
- [ ] Run `codesign --verify --deep --strict --verbose=2 APP/NegativeCutter.app`.
- [ ] Record exact results and remaining manual boundaries in the handoff and planning files.

### Task 6: Targeted master commit

- [ ] Review `git diff` and `git status`.
- [ ] Stage only relevant APP source, tests, spec, plan, handoff, and planning files.
- [ ] Confirm staged diff excludes `APP/NegativeCutter.app`, `test_files/`, `.superpowers/`, `NegativeCutter-135.lrplugin/`, and other unrelated files.
- [ ] Commit on `master` using the repository's concise imperative message style.
