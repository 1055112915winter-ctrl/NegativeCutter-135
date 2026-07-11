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
4. Run the packaged executable against `52191.tif` with `--frames 6 --format 35mm --original <same-path>` and `Untitled (3).tif` with `--frames 4 --format 645 --original <same-path>`. The paths default to `test_files/` and may be overridden by `NEGATIVECUTTER_RELEASE_135_FIXTURE` and `NEGATIVECUTTER_RELEASE_120_FIXTURE`.
5. Require exit code zero and valid JSON. Each result must omit `error`, contain integer `frameCount` equal to 6 or 4, and contain JSON boolean `needsReview` equal to `false`.
6. Stage the release from an explicit manifest rather than copying the development tree. The ZIP has exactly two top-level entries: `NegativeCutter-135.lrplugin/` and `install.sh`. The plugin allowlist contains its Lightroom Lua/menu resources, Python adapter package, notices/docs, icon assets, and the newly built complete `NegativeCutter/` runtime. Build/test/work/log files and every path component named `marketing` or `.claude` are hard failures. Any unclassified source entry fails staging.
7. Generate SHA-256 manifests for every regular file in the complete staged plugin, including all of `NegativeCutter/_internal`, and make the installer verify the manifest after copying.
8. Validate all Lightroom menu references and run `codesign --verify --deep --strict` on the staged engine.
9. Create the ZIP, reopen it in a fresh temporary directory, require the exact top-level inventory, revalidate the SHA-256 manifest, rerun `codesign --verify --deep --strict`, and rerun both packaged-engine smokes from the extracted plugin.
10. If any post-create check fails, delete the ZIP. Only a ZIP passing every extracted-artifact check is publishable.

Fixture paths may be supplied through environment variables. For local release builds they default to the repository's protected `test_files/` corpus. A release build fails clearly when required fixtures are absent; it must not silently skip packaged-engine verification.

## Installation flow

The top-level installer locates the adjacent plugin folder and installs it under Lightroom's Modules directory. It copies into a temporary sibling directory first, verifies every regular file against the packaged SHA-256 manifest, and verifies the staged engine signature. Replacement is rollback-safe: rename the current target to a sibling backup, rename staged to target, restore backup to target if the second rename fails, and remove the backup only after successful installation. Signal/exit traps remove incomplete staging and restore the backup whenever replacement has not committed. This avoids mixed old/new files and prevents a failed replacement from leaving Lightroom without its previous plugin.

The installer prints the installed plugin path and asks the user to restart Lightroom when it is running. It does not modify any other Lightroom plugin.

## Failure behavior

- PyInstaller failure: stop; do not create a ZIP.
- Missing fixtures or failed packaged-engine smoke: stop; do not create a ZIP.
- Forbidden release contents or missing menu targets: stop; do not create a ZIP.
- Installation staging, SHA-256 mismatch, or signature failure: preserve the currently installed plugin and stop.
- Final replacement failure: automatically restore the backup, report the staged/target paths, and exit non-zero.
- ZIP extraction, manifest, signature, inventory, or extracted smoke failure: delete the ZIP and exit non-zero.

## Tests

Static contract tests will first cover the new build gates, exact top-level inventory, explicit staging allowlist, installer inclusion, rollback behavior, traps, and complete SHA-256 verification. Shell syntax checks will cover both scripts. The completed release build must then pass staged and extracted packaged 135/120 smokes, exact ZIP inventory, full manifest verification, and staged/extracted engine signature verification.

## Release boundary

Only the validated ZIP is a publishable attachment. `marketing/`, `.claude/`, tests, work files, logs, build directories, and other investigation artifacts remain excluded.
