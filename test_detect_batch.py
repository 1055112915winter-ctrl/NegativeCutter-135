#!/usr/bin/env python3
"""
FilmCrop batch validation test — US-006
Runs detection on all .tif files in test_files/ and reports pass/fail metrics.

Examples:
    python test_detect_batch.py
    python test_detect_batch.py --aspect-ratio 1.0       # 6x6 medium format
    python test_detect_batch.py --format 6x7
    python test_detect_batch.py --json-out before.json   # write structured report
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure local filmcrop is importable
sys.path.insert(0, str(Path(__file__).parent / "FilmCrop_Clean.lrplugin"))
sys.dont_write_bytecode = True

import numpy as np
from filmcrop.detector import analyze_image


_FORMAT_RATIOS = {
    "35mm": 3 / 2,
    "6x6": 1.0,
    "6x7": 7 / 6,
    "6x9": 3 / 2,
    "4x5": 5 / 4,
}


def test_image(path: Path, aspect_ratio: float = 1.5) -> dict:
    """Run detection and return metrics. aspect_ratio is long/short."""
    result = analyze_image(
        str(path),
        expected_frames=6,
        cleanup_scale=0.5,
        original_path=str(path),
        aspect_ratio=aspect_ratio,
    )
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

    # Compute theoretical proportional span from median frame dimension
    median_frame_dim = (
        median_h
        if not is_h
        else float(np.median([fr["right"] - fr["left"] for fr in frames]))
    )
    target_span = int(round(median_frame_dim / aspect_ratio))
    prop_deviation = abs(long_span - target_span) / target_span * 100 if target_span > 0 else 0.0

    # Strict aspect-ratio check for MIDDLE frames only (skip first/last)
    ratio_errors = []
    target_ratio = (1 / aspect_ratio) if not is_h else aspect_ratio
    middle_frames = frames[1:-1] if len(frames) > 2 else frames
    for fr in middle_frames:
        fw = fr["right"] - fr["left"]
        fh = fr["bottom"] - fr["top"]
        if fh > 0:
            actual_ratio = fw / fh
            err = abs(actual_ratio - target_ratio) / target_ratio * 100
            ratio_errors.append(err)
    max_ratio_err = max(ratio_errors) if ratio_errors else 100.0

    # Per-frame confidence (item 5; tolerant when not yet implemented)
    confidences = [fr.get("confidence") for fr in frames]
    needs_review = result.get("needsReview")

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
        "confidences": confidences,
        "needs_review": needs_review,
        "auto_aspect_raw": debug.get("autoAspectRaw"),
        "long_edge_confidence": debug.get("longEdgeConfidence"),
    }


def _resolve_aspect_ratio(args: argparse.Namespace) -> float:
    if args.aspect_ratio is not None:
        return float(args.aspect_ratio)
    if args.format:
        if args.format not in _FORMAT_RATIOS:
            raise SystemExit(
                f"unknown --format {args.format!r}; valid: {sorted(_FORMAT_RATIOS)}"
            )
        return _FORMAT_RATIOS[args.format]
    return 1.5


def _evaluate(m: dict) -> dict:
    return {
        "gap_pass": m["gap_diff"] <= 500,
        "cv_pass": m["cv"] <= 5.0,
        "prop_pass": m["prop_deviation"] <= 5.0,
        "ratio_pass": m["max_ratio_err"] <= 1.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="FilmCrop batch validation")
    parser.add_argument("--aspect-ratio", type=float, default=None,
                        help="long/short aspect ratio (overrides --format)")
    parser.add_argument("--format", type=str, default=None,
                        choices=sorted(_FORMAT_RATIOS),
                        help="film format hint")
    parser.add_argument("--json-out", type=str, default=None,
                        help="write structured JSON report to PATH")
    parser.add_argument("--test-dir", type=str, default=None,
                        help="directory containing .tif files (default: test_files/)")
    args = parser.parse_args()

    aspect_ratio = _resolve_aspect_ratio(args)

    base = Path(__file__).parent
    test_dir = Path(args.test_dir) if args.test_dir else base / "test_files"
    tif_files = sorted(test_dir.glob("*.tif"))

    if not tif_files:
        print(f"ERROR: No .tif files found in {test_dir}")
        return 1

    print(f"Running batch validation on {len(tif_files)} test images "
          f"(aspect_ratio={aspect_ratio:.4f})...\n")

    all_pass = True
    needs_review_count = 0
    report = {
        "aspect_ratio": aspect_ratio,
        "format": args.format,
        "test_dir": str(test_dir),
        "thresholds": {"gap_diff": 500, "cv": 5.0, "prop_deviation": 5.0, "max_ratio_err": 1.0},
        "results": [],
    }

    for path in tif_files:
        try:
            m = test_image(path, aspect_ratio=aspect_ratio)
        except Exception as e:
            print(f"FAIL {path.name}: {e}")
            all_pass = False
            report["results"].append({"name": path.name, "error": str(e)})
            continue

        ev = _evaluate(m)
        passed = all(ev.values())
        if not passed:
            all_pass = False
        if m.get("needs_review"):
            needs_review_count += 1

        status = "PASS" if passed else "FAIL"
        print(f"{status} {m['name']}")
        print(f"  mode={m['mode']}, frames={m['frame_count']}")
        print(f"  gap widths diff={m['gap_diff']}px  {'✓' if ev['gap_pass'] else '✗ (>500)'}")
        print(f"  frame heights (excl last) CV={m['cv']:.1f}%  {'✓' if ev['cv_pass'] else '✗ (>5%)'}")
        print(f"  long span={m['long_span']}, target={m['target_span']}, "
              f"deviation={m['prop_deviation']:.1f}%  {'✓' if ev['prop_pass'] else '✗ (>5%)'}")
        print(f"  max ratio error={m['max_ratio_err']:.2f}%  {'✓' if ev['ratio_pass'] else '✗ (>1%)'}")
        print(f"  heights={m['heights']}")
        if any(c is not None for c in m["confidences"]):
            cfmt = ", ".join(f"{c:.2f}" if c is not None else "-" for c in m["confidences"])
            print(f"  confidence per frame=[{cfmt}]  needsReview={m['needs_review']}")
        if m.get("auto_aspect_raw") is not None:
            print(f"  autoAspectRaw={m['auto_aspect_raw']:.4f}")
        if m.get("long_edge_confidence"):
            lec = m["long_edge_confidence"]
            print(f"  longEdgeConf near={lec.get('near')} far={lec.get('far')}")
        print()

        report["results"].append({**m, **ev, "passed": passed})

    summary = {"all_pass": all_pass, "needs_review_count": needs_review_count,
               "total": len(tif_files)}
    report["summary"] = summary

    print("=" * 50)
    print(f"{'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}"
          f"   needsReview={needs_review_count}/{len(tif_files)}")

    if args.json_out:
        out = Path(args.json_out)
        out.write_text(json.dumps(report, indent=2, default=str))
        print(f"  → JSON report written to {out}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
