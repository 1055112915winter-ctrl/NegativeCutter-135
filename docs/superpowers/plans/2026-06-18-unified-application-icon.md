# Unified Application Icon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the approved symmetric NegativeCutter icon deterministically in every macOS app build.

**Architecture:** Generate the canonical ICNS locally before PyInstaller runs, and make the spec fail closed when that exact asset is absent. Remove cross-worktree discovery so stale icons cannot enter a build.

**Tech Stack:** Python, Pillow, ICNS, PyInstaller, shell, unittest, macOS Quick Look and codesign.

---

### Task 1: Lock the packaging contract

**Files:**
- Modify: `tests/test_package_app.py`
- Modify: `APP/scripts/build_app.sh`
- Modify: `APP/NegativeCutter.spec`

- [ ] Add assertions that the build script runs `generate_icns.py` before PyInstaller.
- [ ] Add assertions that the spec uses only `APP/NegativeCutter.icns`, rejects a missing icon, and contains no `.claude/worktrees` fallback.
- [ ] Run the package-contract tests and confirm RED failures for the missing contract.
- [ ] Implement the smallest build-script and spec changes.
- [ ] Re-run the contract tests and confirm GREEN.

### Task 2: Generate and inspect the canonical asset

**Files:**
- Create: `APP/NegativeCutter.icns`

- [ ] Run `python3 APP/generate_icns.py`.
- [ ] Render the ICNS with Quick Look into `/tmp` and inspect the preview.
- [ ] Verify the ICNS contains the approved dark plate, symmetric terracotta diamonds, central lens, and no diagonal slash or film perforations.

### Task 3: Rebuild and verify the bundle

**Files:**
- Modify: `.claude/handoffs/negativecutter-standalone-gui-v2.4.4-final-20260611.md`

- [ ] Run all GUI and package-contract tests.
- [ ] Run `APP/scripts/package_app.sh`.
- [ ] Confirm source and bundled ICNS hashes are identical.
- [ ] Confirm `CFBundleIconFile` is `NegativeCutter.icns`.
- [ ] Run strict deep code-sign verification.
- [ ] Update the handoff with exact evidence.

### Task 4: Targeted master commit

- [ ] Stage only the files listed by this plan.
- [ ] Verify no `.app`, test scan, scratch, or Lightroom plugin files are staged.
- [ ] Commit to `master` with the repository's concise imperative style.
