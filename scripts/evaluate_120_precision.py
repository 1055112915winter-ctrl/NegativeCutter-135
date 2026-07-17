#!/usr/bin/env python3
"""Evaluate real 120 detections against reviewed pixel-edge bands."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from negativecutter_core.detector import analyze_image  # noqa: E402


TRUTH_PATH = ROOT / "tests" / "fixtures" / "120_edge_truth.json"


def distance_to_band(value: int, band: list[int]) -> int:
    low, high = band
    if value < low:
        return low - value
    if value > high:
        return value - high
    return 0


def resolve_fixture(entry: dict, fixture_root: Path | None) -> Path:
    configured = os.environ.get(entry["environmentVariable"])
    if configured:
        return Path(configured)
    if fixture_root is not None:
        return fixture_root / entry["fileName"]
    raise FileNotFoundError(
        f"set {entry['environmentVariable']} or pass --fixture-root"
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def evaluate_entry(entry: dict, path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    actual_hash = sha256(path)
    if actual_hash != entry["sha256"]:
        raise ValueError(f"fixture hash mismatch for {path}")

    result = analyze_image(
        str(path),
        expected_frames=0,
        original_path=str(path),
        aspect_ratio=None,
    )
    gap_rows = []
    actual_gaps = result.get("debug", {}).get("gapEdges", [])
    for index, expected in enumerate(entry["gapEdgeBands"]):
        if index >= len(actual_gaps):
            gap_rows.append({"index": index + 1, "missing": True})
            continue
        left, right = actual_gaps[index]
        gap_rows.append(
            {
                "index": index + 1,
                "actual": [left, right],
                "expected": expected,
                "leftError": distance_to_band(left, expected["left"]),
                "rightError": distance_to_band(right, expected["right"]),
            }
        )

    near, far = result.get("debug", {}).get("longEdges", [0, 0])
    cross = entry["crossAxisEdgeBands"]
    cross_errors = {
        "actual": [near, far],
        "nearError": distance_to_band(near, cross["near"]),
        "farError": distance_to_band(far, cross["far"]),
    }
    errors = [
        value
        for row in gap_rows
        for value in (row.get("leftError"), row.get("rightError"))
        if value is not None
    ] + [cross_errors["nearError"], cross_errors["farError"]]
    return {
        "fileName": entry["fileName"],
        "frameCount": result.get("frameCount"),
        "expectedFrameCount": entry["frameCount"],
        "needsReview": result.get("needsReview"),
        "gapEdges": gap_rows,
        "crossAxis": cross_errors,
        "maxEdgeError": max(errors, default=0),
        "passed": (
            result.get("frameCount") == entry["frameCount"]
            and len(actual_gaps) == len(entry["gapEdgeBands"])
            and all(error == 0 for error in errors)
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    truth = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))
    reports = []
    for entry in truth["fixtures"]:
        path = resolve_fixture(entry, args.fixture_root)
        reports.append(evaluate_entry(entry, path))

    if args.json:
        print(json.dumps({"fixtures": reports}, ensure_ascii=False, indent=2))
    else:
        for report in reports:
            status = "PASS" if report["passed"] else "FAIL"
            print(
                f"{status} {report['fileName']}: "
                f"frames={report['frameCount']}/{report['expectedFrameCount']} "
                f"max_edge_error={report['maxEdgeError']}px "
                f"needsReview={report['needsReview']}"
            )
            for gap in report["gapEdges"]:
                print(
                    f"  gap{gap['index']}: actual={gap.get('actual')} "
                    f"left_error={gap.get('leftError')} "
                    f"right_error={gap.get('rightError')}"
                )
    return 0 if all(report["passed"] for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
