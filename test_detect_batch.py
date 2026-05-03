#!/usr/bin/env python3
"""
FilmCrop batch validation test — US-006
Runs detection on all .tif files in test_files/ and reports pass/fail metrics.
"""

import sys
import os
from pathlib import Path

# Ensure local filmcrop is importable
sys.path.insert(0, str(Path(__file__).parent / "FilmCrop_Clean.lrplugin"))
sys.dont_write_bytecode = True

import numpy as np
from filmcrop.detector import analyze_image


def test_image(path: Path) -> dict:
    """Run detection and return metrics."""
    result = analyze_image(str(path), expected_frames=6, cleanup_scale=0.5, original_path=str(path))
    debug = result["debug"]
    frames = result["frames"]

    # Gap width consistency
    gaps = debug["gapEdges"]
    gap_widths = [re - le for le, re in gaps]
    gap_diff = max(gap_widths) - min(gap_widths)

    # Frame height consistency (exclude last frame — film strip may be truncated)
    heights = [fr["bottom"] - fr["top"] for fr in frames]
    if len(heights) > 1:
        heights_excl_last = heights[:-1]
        median_h = float(np.median(heights_excl_last))
        mean_h = float(np.mean(heights_excl_last))
        std_h = float(np.std(heights_excl_last))
        cv = (std_h / mean_h * 100) if mean_h > 0 else 0.0
    else:
        median_h = 0.0
        cv = 0.0

    # Long edge proportional check
    long_edges = debug["longEdges"]
    orig_w = result["sourceWidth"]
    orig_h = result["sourceHeight"]
    is_h = debug["isHorizontal"]
    cross_size = orig_h if not is_h else orig_w
    long_span = long_edges[1] - long_edges[0]

    # Compute theoretical proportional span from median frame height
    median_frame_dim = median_h if not is_h else float(np.median([fr["right"] - fr["left"] for fr in frames]))
    target_span = int(round(median_frame_dim / 1.5))
    prop_deviation = abs(long_span - target_span) / target_span * 100 if target_span > 0 else 0.0

    # Strict aspect-ratio check for MIDDLE frames only (skip first/last)
    ratio_errors = []
    target_ratio = 2 / 3 if not is_h else 3 / 2
    middle_frames = frames[1:-1] if len(frames) > 2 else frames
    for fr in middle_frames:
        fw = fr["right"] - fr["left"]
        fh = fr["bottom"] - fr["top"]
        if fh > 0:
            actual_ratio = fw / fh
            err = abs(actual_ratio - target_ratio) / target_ratio * 100
            ratio_errors.append(err)
    max_ratio_err = max(ratio_errors) if ratio_errors else 100.0

    return {
        "name": path.name,
        "mode": debug["mode"],
        "gap_diff": gap_diff,
        "heights": heights,
        "cv": cv,
        "long_edges": long_edges,
        "long_span": long_span,
        "target_span": target_span,
        "prop_deviation": prop_deviation,
        "max_ratio_err": max_ratio_err,
        "frame_count": len(frames),
    }


def main() -> int:
    test_dir = Path(__file__).parent / "test_files"
    tif_files = sorted(test_dir.glob("*.tif"))

    if not tif_files:
        print("ERROR: No .tif files found in test_files/")
        return 1

    print(f"Running batch validation on {len(tif_files)} test images...\n")

    all_pass = True
    for path in tif_files:
        try:
            m = test_image(path)
        except Exception as e:
            print(f"FAIL {path.name}: {e}")
            all_pass = False
            continue

        gap_pass = m["gap_diff"] <= 500
        cv_pass = m["cv"] <= 5.0
        prop_pass = m["prop_deviation"] <= 5.0
        ratio_pass = m["max_ratio_err"] <= 5.0

        status = "PASS" if (gap_pass and cv_pass and prop_pass and ratio_pass) else "FAIL"
        if status == "FAIL":
            all_pass = False

        print(f"{status} {m['name']}")
        print(f"  mode={m['mode']}, frames={m['frame_count']}")
        print(f"  gap widths diff={m['gap_diff']}px  {'✓' if gap_pass else '✗ (>' + str(500) + ')'}")
        print(f"  frame heights (excl last) CV={m['cv']:.1f}%  {'✓' if cv_pass else '✗ (>5%)'}")
        print(f"  long span={m['long_span']}, target={m['target_span']}, deviation={m['prop_deviation']:.1f}%  {'✓' if prop_pass else '✗ (>5%)'}")
        print(f"  max ratio error={m['max_ratio_err']:.2f}%  {'✓' if ratio_pass else '✗ (>1%)'}")
        print(f"  heights={m['heights']}")
        print()

    if all_pass:
        print("=" * 50)
        print("ALL TESTS PASSED")
        return 0
    else:
        print("=" * 50)
        print("SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
