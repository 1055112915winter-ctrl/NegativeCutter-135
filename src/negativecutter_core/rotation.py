"""Robust rotation policy for film-strip detection.

Rotation is an optional refinement.  An untrusted estimate must never make an
otherwise valid crop unsafe, so rejected candidates are retained in diagnostics
while the applied angle is zero.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Iterable, Sequence

import numpy as np


MAX_SAFE_ROTATION_DEGREES = 3.0
MIN_CROSS_RESOLUTION = 128
MIN_OFFSET_SAMPLES = 2
MIN_MEDIAN_PROMINENCE = 0.05


@dataclass(frozen=True)
class RotationEstimate:
    angle: float
    candidate_angle: float
    accepted: bool
    rejection_reason: str | None
    sample_count: int
    median_offset: float
    offset_range: float
    median_prominence: float
    cross_baseline: float
    cross_resolution: int

    def as_dict(self) -> dict:
        return asdict(self)


def evaluate_rotation_offsets(
    offsets: Sequence[float] | Iterable[float],
    *,
    cross_baseline: float,
    cross_resolution: int,
    prominences: Sequence[float] | Iterable[float] | None = None,
    max_safe_angle: float = MAX_SAFE_ROTATION_DEGREES,
) -> RotationEstimate:
    """Validate paired gap offsets and return a safe structured estimate."""

    finite_offsets = [float(value) for value in offsets if math.isfinite(float(value))]
    finite_prominences = (
        [float(value) for value in prominences if math.isfinite(float(value))]
        if prominences is not None
        else []
    )
    sample_count = len(finite_offsets)
    median_offset = float(np.median(finite_offsets)) if finite_offsets else 0.0
    offset_range = (
        float(max(finite_offsets) - min(finite_offsets)) if finite_offsets else 0.0
    )
    median_prominence = (
        float(np.median(finite_prominences)) if finite_prominences else 1.0
    )
    candidate_angle = (
        math.degrees(math.atan2(median_offset, cross_baseline))
        if cross_baseline > 0 and math.isfinite(cross_baseline)
        else 0.0
    )

    rejection_reason: str | None = None
    if cross_resolution < MIN_CROSS_RESOLUTION:
        rejection_reason = "under_resolved"
    elif sample_count < MIN_OFFSET_SAMPLES:
        rejection_reason = "insufficient_samples"
    else:
        allowed_range = max(3.0, abs(median_offset) * 0.75)
        if offset_range > allowed_range:
            rejection_reason = "inconsistent_offsets"
        elif median_prominence < MIN_MEDIAN_PROMINENCE:
            rejection_reason = "weak_gap_signal"
        elif abs(candidate_angle) > max_safe_angle:
            rejection_reason = "angle_limit"

    accepted = rejection_reason is None
    return RotationEstimate(
        angle=candidate_angle if accepted else 0.0,
        candidate_angle=candidate_angle,
        accepted=accepted,
        rejection_reason=rejection_reason,
        sample_count=sample_count,
        median_offset=median_offset,
        offset_range=offset_range,
        median_prominence=median_prominence,
        cross_baseline=float(cross_baseline),
        cross_resolution=int(cross_resolution),
    )
