"""
FilmCrop - Film frame detection and cropping engine.

A standalone Python package for detecting frames in scanned film strips
and exporting crop boundaries for Lightroom or standalone use.
"""

__version__ = "2.4.6"
__all__ = [
    "analyze_image",
    "build_frames",
    "detect_long_edges",
    "to_json",
    "to_xmp",
    "crop_and_save",
]


def __getattr__(name):
    """Load the recognition/export stack only when its legacy API is used."""
    if name in {"analyze_image", "build_frames", "detect_long_edges"}:
        from . import detector
        return getattr(detector, name)
    if name in {"to_json", "to_xmp", "crop_and_save"}:
        from . import export
        return getattr(export, name)
    raise AttributeError(name)
