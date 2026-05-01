"""
FilmCrop - Film frame detection and cropping engine.

A standalone Python package for detecting frames in scanned film strips
and exporting crop boundaries for Lightroom or standalone use.
"""

from .detector import analyze_image, build_frames, detect_long_edges
from .export import to_json, to_xmp, crop_and_save

__version__ = "2.0.0"
__all__ = [
    "analyze_image",
    "build_frames",
    "detect_long_edges",
    "to_json",
    "to_xmp",
    "crop_and_save",
]
