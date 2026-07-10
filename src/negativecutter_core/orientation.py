"""Pure rectangle and angle transforms for Lightroom orientation codes."""

from __future__ import annotations

from typing import Iterable


ORIENTATION_CODES = frozenset({"AB", "BC", "CD", "DA"})


def normalize_orientation(value: str | None) -> str:
    code = str(value or "AB").strip().upper()
    if code not in ORIENTATION_CODES:
        raise ValueError(f"Unsupported orientation: {value!r}")
    return code


def transform_rect(
    rect: tuple[float, float, float, float] | Iterable[float],
    orientation: str,
) -> tuple[float, float, float, float]:
    """Transform ``(top, bottom, left, right)`` from AB to orientation."""

    top, bottom, left, right = (float(value) for value in rect)
    code = normalize_orientation(orientation)
    if code == "AB":
        return top, bottom, left, right
    if code == "BC":
        return 1.0 - right, 1.0 - left, top, bottom
    if code == "CD":
        return 1.0 - bottom, 1.0 - top, 1.0 - right, 1.0 - left
    return left, right, 1.0 - bottom, 1.0 - top


def transform_angle(angle: float, orientation: str) -> float:
    """Map Lightroom crop-angle sign through the same orientation transform."""

    code = normalize_orientation(orientation)
    return -float(angle) if code in {"BC", "DA"} else float(angle)
