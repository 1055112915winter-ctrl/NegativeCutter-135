#!/usr/bin/env python3
"""
Compare 3 ratio-enforcement schemes across all test images.
Outputs a table of per-scheme metrics.
"""
import sys
import json
from pathlib import Path
import numpy as np

BASE = Path(__file__).parent
SCHEMES = {
    "A (MIN)": BASE / ".claude/worktrees/ratio-scheme-a-min-constraint",
    "B (Lua 2pass)": BASE / ".claude/worktrees/ratio-scheme-b-lua-twopass",
    "C (Pitch)": BASE / ".claude/worktrees/ratio-scheme-c-pitch-driven",
}
IMAGES = ["52191.tif", "52194.tif", "luckyc20013.tif"]
TEST_DIR = BASE / "test_files"


def run_scheme(scheme_name, worktree: Path, image: str) -> dict | None:
    plugin = worktree / "FilmCrop_Clean.lrplugin"
    # Clear cached filmcrop imports so each scheme loads its own code
    for mod in list(sys.modules.keys()):
        if mod.startswith("filmcrop"):
            del sys.modules[mod]
    sys.path.insert(0, str(plugin))
    try:
        from filmcrop.detector import analyze_image
    finally:
        if str(plugin) in sys.path:
            sys.path.remove(str(plugin))

    img_path = TEST_DIR / image
    result = analyze_image(str(img_path), expected_frames=6, cleanup_scale=0.5,
                           original_path=str(img_path))
    frames = result["frames"]
    target_ratio = 2 / 3  # vertical film strips (all 3 test images are vertical)

    # Per-frame ratio errors
    ratio_errors = []
    for fr in frames:
        w = fr["right"] - fr["left"]
        h = fr["bottom"] - fr["top"]
        if h > 0:
            err = abs(w / h - target_ratio) / target_ratio * 100
            ratio_errors.append(round(err, 2))

    # Gap between adjacent frames (should be positive = not overlapping)
    gaps = []
    for i in range(1, len(frames)):
        prev_bottom = frames[i - 1]["bottom"]
        curr_top = frames[i]["top"]
        gaps.append(curr_top - prev_bottom)

    # Frame dimensions (scan-direction)
    heights = [fr["bottom"] - fr["top"] for fr in frames]
    widths = [fr["right"] - fr["left"] for fr in frames]
    middle_heights = heights[1:-1] if len(heights) > 2 else heights

    return {
        "scheme": scheme_name,
        "image": image,
        "frames": len(frames),
        "ratio_errors": ratio_errors,
        "max_ratio_err": max(ratio_errors),
        "gaps": gaps,
        "min_gap": min(gaps) if gaps else 0,
        "overlapping": any(g <= 0 for g in gaps),
        "middle_heights": middle_heights,
        "height_range": max(middle_heights) - min(middle_heights) if middle_heights else 0,
        "middle_h_mean": round(np.mean(middle_heights), 1) if middle_heights else 0,
        "widths": widths,
        "width_range": max(widths) - min(widths),
        "pass": all(e <= 1.0 for e in ratio_errors[1:-1]) and not any(g <= 0 for g in gaps),
    }


def main():
    results = []
    for scheme_name, worktree in SCHEMES.items():
        for image in IMAGES:
            try:
                r = run_scheme(scheme_name, worktree, image)
                results.append(r)
            except Exception as e:
                results.append({
                    "scheme": scheme_name,
                    "image": image,
                    "error": str(e),
                    "pass": False,
                })

    # Print comparison table
    print(f"{'Scheme':<16} {'Image':<18} {'Frames':<7} {'MaxRatioErr':<12} {'MinGap':<8} {'Overlap':<8} {'HtRange':<9} {'WtRange':<8} {'PASS':<6}")
    print("-" * 110)
    for r in results:
        if "error" in r:
            print(f"{r['scheme']:<16} {r['image']:<18} {'ERROR: ' + r['error']}")
            continue
        print(f"{r['scheme']:<16} {r['image']:<18} {r['frames']:<7} {r['max_ratio_err']:<12.2f}% "
              f"{r['min_gap']:<8} {'YES' if r['overlapping'] else 'NO':<8} "
              f"{r['height_range']:<9} {r['width_range']:<8} "
              f"{'✓' if r['pass'] else '✗':<6}")

    # Summary
    print()
    print("=" * 60)
    print("Per-scheme summary (all images):")
    for scheme_name in SCHEMES:
        scheme_results = [r for r in results if r.get("scheme") == scheme_name and "error" not in r]
        if not scheme_results:
            print(f"  {scheme_name}: ERROR")
            continue
        all_pass = all(r["pass"] for r in scheme_results)
        avg_err = np.mean([r["max_ratio_err"] for r in scheme_results])
        any_overlap = any(r["overlapping"] for r in scheme_results)
        print(f"  {scheme_name}: {'PASS' if all_pass else 'FAIL'} "
              f"avg_max_ratio_err={avg_err:.2f}% "
              f"overlap={'YES' if any_overlap else 'NO'}")


if __name__ == "__main__":
    main()
