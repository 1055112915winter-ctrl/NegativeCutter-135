"""Canonical detection policies shared by the APP and Lightroom adapter."""

from .rotation import RotationEstimate, evaluate_rotation_offsets
from .formats import FILM_FORMATS, MEDIUM_FORMAT_CODES
from .orientation import transform_angle, transform_rect
from .medium_format import should_use_medium_format

__all__ = [
    "FILM_FORMATS",
    "MEDIUM_FORMAT_CODES",
    "RotationEstimate",
    "evaluate_rotation_offsets",
    "transform_angle",
    "transform_rect",
    "should_use_medium_format",
]
