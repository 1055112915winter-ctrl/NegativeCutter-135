# Plugin Release Synchronization Design

## Goal

Make the published Lightroom plugin self-consistent: every release must contain an engine rebuilt from the current source, prove that engine handles representative 135 and 120 scans, and install by replacing the complete previous plugin rather than overlaying files.

## Chosen approach

The release ZIP is the only authoritative installable artifact. `NegativeCutter-135.lrplugin/build.sh` will always remove old build output and the plugin's existing bundled runtime before rebuilding. It will stage the freshly built runtime, run packaged-engine smoke tests, verify release contents, and only then create the ZIP. The ZIP will contain both `NegativeCutter-135.lrplugin/` and a top-level `install.sh`.

Version-only comparison is insufficient because source can change without a version bump. Running Lightroom against Python source is also rejected because it makes the release depend on the user's Python environment.

## Build and verification flow

1. Remove `build/`, `dist/`, the previous output ZIP, and the plugin-root `NegativeCutter/` runtime.
2. Run PyInstaller from the current plugin source.
3. Copy the new onedir runtime into the plugin directory.
4. Run the packaged executable against one real 135 fixture and `Untitled (3).tif` as explicit 645/4-frame 120.
5. Require valid JSON, no `error`, `needsReview=false`, and the expected frame counts.
6. Stage only release files, include `install.sh`, reject development artifacts, and validate all Lightroom menu references.
7. Create the ZIP only after every gate succeeds.

Fixture paths may be supplied through environment variables. For local release builds they default to the repository's protected `test_files/` corpus. A release build fails clearly when required fixtures are absent; it must not silently skip packaged-engine verification.

## Installation flow

The top-level installer locates the adjacent plugin folder and installs it under Lightroom's Modules directory. It copies into a temporary sibling directory first, verifies the copied engine exists and matches the packaged engine fingerprint, removes the old installed plugin only after staging succeeds, then atomically renames the staged directory into place. This avoids mixed old/new files and reduces the chance of leaving Lightroom without a usable plugin after a failed copy.

The installer prints the installed plugin path and asks the user to restart Lightroom when it is running. It does not modify any other Lightroom plugin.

## Failure behavior

- PyInstaller failure: stop; do not create a ZIP.
- Missing fixtures or failed packaged-engine smoke: stop; do not create a ZIP.
- Forbidden release contents or missing menu targets: stop; do not create a ZIP.
- Installation staging or fingerprint mismatch: preserve the currently installed plugin and stop.
- Final replacement failure: report the staged/target paths and exit non-zero.

## Tests

Static contract tests will first cover the new build gates, installer inclusion, full-replacement behavior, staging, and fingerprint verification. Shell syntax checks will cover both scripts. The completed release build must then pass the packaged 135/120 smoke tests, ZIP inventory inspection, and signature verification of the packaged engine.

## Release boundary

Only the validated ZIP is a publishable attachment. `marketing/`, `.claude/`, tests, work files, logs, build directories, and other investigation artifacts remain excluded.
