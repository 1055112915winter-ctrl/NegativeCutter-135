"""Medium-format routing policy.

The image-analysis implementation remains callable through detector.py; this
module owns the product decision about when that isolated pipeline is entered.
"""

from __future__ import annotations

from .formats import format_family, normalize_format_code


AUTO_STRIP_RATIO_MIN = 2.0
AUTO_STRIP_RATIO_MAX = 5.0


def should_use_medium_format(
    width: int,
    height: int,
    expected_frames: int,
    film_format: str | None,
) -> tuple[bool, str]:
    normalized = normalize_format_code(film_format)
    family = format_family(normalized)
    if family == "120":
        return True, "explicit_format"
    if family == "135":
        return False, "explicit_35mm"
    if normalized:
        return False, "explicit_other"
    if expected_frames != 0:
        return False, "explicit_frame_count"

    short_side = min(width, height)
    long_side = max(width, height)
    image_ratio = long_side / short_side if short_side > 0 else 1.0
    if AUTO_STRIP_RATIO_MIN < image_ratio < AUTO_STRIP_RATIO_MAX:
        return True, "auto_geometry"
    return False, "auto_135_geometry"
