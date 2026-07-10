# Detection Pipeline

## Shared flow

1. Decode the image and normalize EXIF orientation.
2. Preserve the explicit film-format family; ratio alone is insufficient.
3. Route to 135 or single-strip 120.
4. Detect the film region, internal gaps, and frame rectangles.
5. Enforce the selected aspect ratio and coordinate sanity.
6. Estimate optional rotation and reject unsafe measurements.
7. Return frames, `needsReview`, and structured diagnostics.
8. The product adapter maps coordinates and applies/exports crops.

## 135 invariants

- Explicit `35mm` always uses the 135 route.
- Middle frames remain strict 3:2.
- Gap-aligned placement and long-edge fallback are preserved.
- Rotation is zero unless resolution, sample count, gap agreement, signal
  prominence, and the 3-degree ceiling all pass.
- Lightroom independently rejects non-finite or >3-degree angles.

`debug.rotationEstimate` records the candidate angle, accepted angle, sample
count, offset range, prominence, resolution, and rejection reason.

## 120 invariants

- Supported codes: `645`, `6x6`, `6x7`, `6x8`, `6x9`.
- Explicit format family takes precedence over geometry.
- Explicit frame count constrains the 120 gap search.
- Auto geometry uses long-side/short-side ratio, independent of storage axis.
- Only one strip is supported. Grid/multi-row layouts are rejected scope.
- Ambiguous or low-confidence results must surface as `needsReview`.

## Orientation

Lightroom uses AB/BC/CD/DA rotation codes. BC and DA are different transforms;
a plain coordinate transpose is not valid for asymmetric rectangles. Python
and Lua property tests cover quarter-turn composition and angle sign.
