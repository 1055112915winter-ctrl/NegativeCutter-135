# FilmCrop Long-Term Detection Core Design

## Goal

Turn the v2.4.5 FilmCrop/NegativeCutter codebase into one testable detection
product: protect 135 users from unsafe rotation, preserve the verified 135
geometry, and support single-strip 120 formats (645, 6x6, 6x7, 6x8, 6x9)
without maintaining two drifting detector implementations.

## Evidence and constraints

- Four real 135 TIFF fixtures currently detect six frames with angles between
  -0.39 and -0.05 degrees.
- A real Lightroom feedback bundle contains unsafe historical outputs of
  -8.13 and 33.69 degrees. The estimator has no confidence contract and the
  Lua applier accepts every angle above 0.5 degrees.
- The APP and Lightroom plugin carry different copies of detector.py. They
  already drift in DNG loading and review-frame behavior.
- The existing 120 worktree has green routing tests and two green real-fixture
  tests, but its implementation is not committed and does not establish a
  canonical shared source.
- Orientation 5/7 overlay evidence shows that width/height-only mapping is not
  a sufficient coordinate contract.
- A forced 6x2 overlay visibly splits four real photographs into twelve cells;
  6x2 is rejected, not a supported film format.

## Approaches considered

### A. Patch both detector copies

Add angle clamps and copy the 120 changes into APP and plugin. This is the
smallest diff, but preserves the cause of current drift and makes every future
algorithm change a two-file merge exercise. Rejected for long-term operation.

### B. Rewrite the detector around a new computer-vision pipeline

Replace the current projection model with a new OpenCV/ML detector. This could
eventually improve difficult scans, but it discards a verified 135 baseline,
expands packaging dependencies, and cannot be justified by the available six
real fixtures. Rejected as unnecessary and high-risk.

### C. Canonical shared core with compatibility adapters (selected)

Move the superset detector behavior into a root `src/negativecutter_core`
package. Keep the existing `APP.filmcrop` and plugin `filmcrop` public imports
as thin adapters, so GUI, CLI, PyInstaller, and Lightroom call sites remain
stable. Extract the highest-risk policies (formats/routing, rotation, and
orientation transforms) into focused modules first; leave the proven 135
projection internals intact behind the compatibility facade.

This approach removes behavioral drift without coupling the GUI to Lightroom,
and supports gradual extraction of the remaining detector internals later.

## Architecture

### Canonical core

- `src/negativecutter_core/formats.py`
  - owns supported film codes and aspect ratios;
  - distinguishes the 135 and 120 families even when ratios match (35mm and
    6x9 are both 3:2);
  - validates explicit format and frame-count hints.
- `src/negativecutter_core/rotation.py`
  - estimates candidate offsets at each internal gap;
  - returns a structured estimate containing angle, confidence, sample count,
    spread, and rejection reason;
  - rejects under-resolved, inconsistent, implausible, or weak estimates;
  - preserves small, consistent real skew.
- `src/negativecutter_core/orientation.py`
  - owns EXIF 1-8 and Lightroom AB/BC/CD/DA coordinate transforms;
  - transforms rectangles and angle signs through an explicit source-to-target
    orientation delta;
  - is tested by group/round-trip properties and fixture overlays.
- `src/negativecutter_core/medium_format.py`
  - owns the existing isolated 120 film-region, gap, and frame construction
    pipeline;
  - accepts explicit format and frame-count hints;
  - supports single-strip 645, 6x6, 6x7, 6x8, and 6x9 in either storage axis.
- `src/negativecutter_core/detector.py`
  - remains the compatibility facade and owns the proven 135 projection
    pipeline during this refactor;
  - routes by explicit film family first, then conservative auto geometry;
  - emits stable JSON plus diagnostics.

### Product adapters

- `APP/filmcrop/detector.py` and
  `NegativeCutter-135.lrplugin/filmcrop/detector.py` re-export the canonical
  API; neither contains detector policy.
- APP-only display/export code remains in `APP/filmcrop`.
- Lightroom Lua remains an adapter: collect metadata, call the engine, map
  orientation, validate the returned crop, and apply it.
- PyInstaller specs and build scripts add the root `src` path explicitly.

## 135 rotation safety contract

Rotation is optional enhancement, never required for a valid crop. The core
returns zero unless all gates pass:

1. cross-axis resolution is high enough to measure the requested angle;
2. at least two internal gaps provide usable paired offsets;
3. offsets agree within a robust median-absolute-deviation limit;
4. the estimated absolute angle is within the product safety ceiling;
5. local gap prominence supports the selected extrema.

The initial product ceiling is 3 degrees. Existing good fixtures are below
0.4 degrees, while the known failures are 8.13 and 33.69 degrees. Diagnostics
retain the rejected candidate and reason, but `cropAngle` becomes zero. The Lua
applier independently rejects non-finite angles and angles above 3 degrees, so
an old or malformed engine cannot rotate a user photo catastrophically.

## 120 contract

- Explicit 645/6x6/6x7/6x8/6x9 always selects the 120 route.
- Explicit 35mm always selects 135, even though 6x9 has the same 3:2 ratio.
- Auto mode uses orientation-independent long/short geometry and conservative
  evidence; ambiguous scans return `needsReview` rather than silently choosing
  a family.
- Explicit frame count constrains candidate evaluation but does not bypass
  coordinate, confidence, or format validation.
- Single-strip only. Multi-row/grid scans are outside this release.

## Testing and quality gates

1. Rotation unit tests reproduce low-resolution and inconsistent-offset
   failures and verify red-green behavior.
2. Lua tests prove the independent >3-degree and non-finite angle fuse.
3. Compatibility tests prove APP and plugin imports resolve to the same core
   implementation.
4. Existing 29 APP tests and focused plugin unit tests remain green.
5. `raw0014.dng` remains six 135 frames.
6. Four real 135 TIFFs remain six frames, strict 3:2, no review, no unsafe
   angle.
7. Two real 120 TIFFs remain four frames in auto and explicit format modes.
8. Synthetic format matrix covers all five 120 formats and both axes.
9. Test discovery excludes Lightroom UI automation; E2E remains a separate,
   explicit command.

## Repository hygiene

Keep:

- source, tests, small fixtures, build metadata, current release notes;
- the six large local recognition fixtures, ignored by Git;
- the feedback archive until its regression facts are encoded in tests.

Consolidate:

- canonical detector policy under `src/negativecutter_core`;
- maintenance, testing, architecture, format-extension, and release guidance
  under `docs/`;
- deterministic test commands under `scripts/`.

Remove only after verification:

- obsolete worktrees with clean status and branches already represented by
  reachable commits;
- generated previews/caches that can be reproduced;
- interrupted `tmp_pack_*` Git files after confirming no active Git process.

Never delete large recognition fixtures merely because of size, and never
upload `marketing/` or `.claude/` artifacts.

## Rollout

1. Land tests and the rotation fuse without changing 135 crop geometry.
2. Establish the canonical package and compatibility adapters.
3. Integrate the already-green 120 route into the canonical core.
4. Fix orientation transforms and test separation.
5. Run real-fixture regression, package smoke checks, and documentation review.
6. Perform only evidence-backed repository cleanup.
