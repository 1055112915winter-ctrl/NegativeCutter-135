# 120 Single-Strip Detection Design

## Scope

Implement reliable single-strip 120 detection on the v2.4.5 baseline. Support
automatic and explicitly selected 645, 6x6, 6x7, 6x8, and 6x9 formats in both
horizontal and vertical storage orientations. Do not implement multi-row scans
in this iteration.

## Current Problem

The v2.4.5 detector contains a separate 120 pipeline, but it is entered only
when all of these are true:

- frame count is automatic (expected_frames == 0);
- the decoded image is vertical;
- the long-to-short image ratio is between 2 and 5.

Consequently, selecting a 120 format or entering an explicit frame count can
still run the 135 pipeline. A horizontal 120 strip also bypasses the 120
pipeline. The CLI converts the format code to an aspect ratio and discards the
format family, so 35mm and 6x9 are indistinguishable downstream.

## Design

1. Preserve the selected format code from detect_thumb.py to analyze_image().
2. Treat 645, 6x6, 6x7, 6x8, and 6x9 as explicit medium-format signals. Keep
   35mm on the existing 135 path.
3. Make the automatic 120 heuristic orientation-independent by using
   max(width, height) / min(width, height).
4. Let the 120 gap detector accept an explicit frame-count hint. When supplied,
   evaluate exactly that count; otherwise retain the existing conservative 2-6
   auto search.
5. Return debug fields identifying the selected format, route reason, and
   explicit frame-count hint.
6. Apply the same detector behavior to the Lightroom plugin and standalone APP
   copies without changing the established 135 algorithm.

## Verification

- RED/GREEN routing tests for explicit 120 formats, explicit 35mm, horizontal
  automatic 120, and explicit frame-count forwarding.
- Real-fixture checks against Untitled (3).tif and 未标题(1).tif: four frames,
  full-width boundaries, needsReview=false.
- Existing raw0014 auto regression remains six frames.
- Plugin and standalone Python suites remain green.

## Deferred

- 6x2 or other multi-row layouts.
- Replacing Lightroom's partial BC/CD/DA coordinate mapping.
- Automatic 120 counts above six without an explicit frame-count hint.
