# Unified Application Icon Design

## Goal

Use the current symmetric diamond-and-lens NegativeCutter mark everywhere: the Qt window, Finder, Get Info, Dock, and the packaged macOS application.

## Root cause

The Qt GUI renders the new mark from `APP/filmcrop/gui/logo.py`, and `APP/generate_icns.py` already implements the same geometry for macOS icon sizes. However, `APP/NegativeCutter.icns` is absent. `APP/NegativeCutter.spec` silently searches `.claude/worktrees/` and picks an older icon, so the packaged app receives the obsolete film-strip/slash artwork.

## Design

- `APP/scripts/build_app.sh` generates `APP/NegativeCutter.icns` before invoking PyInstaller.
- `APP/NegativeCutter.spec` accepts only that local icon and raises a clear error if it is missing. It never searches other worktrees.
- The generated `APP/NegativeCutter.icns` is committed so Finder can show the correct icon before a rebuild and clean checkouts have the canonical asset.
- `APP/generate_icns.py` remains the single source for macOS raster sizes; `APP/filmcrop/gui/logo.py` remains the Qt renderer for the same approved geometry and colors.

## Verification

- Package-contract tests fail before implementation if the build script does not generate the icon or if the spec contains a worktree fallback.
- After implementation, generate the icon and render a 1024px Quick Look preview for visual inspection.
- Rebuild the app, verify the source and bundled ICNS SHA-256 values match, inspect `CFBundleIconFile`, run GUI/package tests, and verify the code signature.

## Git scope

Commit only the generator/build/spec/test changes, generated ICNS, design/plan documents, and handoff update. Preserve all unrelated Lightroom plugin and working-tree changes.
