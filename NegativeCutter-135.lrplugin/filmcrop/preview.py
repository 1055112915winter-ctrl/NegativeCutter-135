"""Render lightweight annotated previews for live Lightroom crop adjustments."""

from __future__ import annotations

import copy
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _finite_number(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _axis_bounds(start, end, size):
    size = int(size)
    minimum = min(20, size)
    start = max(0, min(int(round(start)), size))
    end = max(0, min(int(round(end)), size))
    if end < start:
        start, end = end, start
    if end - start < minimum:
        end = min(size, start + minimum)
        start = max(0, end - minimum)
    return start, end


def _frame_pixel(frame, name, relative_name, size, default):
    if name in frame:
        return _finite_number(frame[name], default)
    return _finite_number(frame.get(relative_name, default / size), default / size) * size


def adjust_frames(frames, source_width, source_height, offsets, orientation=1):
    """Apply live crop offsets to canonical, orientation-aligned frame bounds.

    ``orientation`` is accepted so callers can pass their source metadata, but
    frames are already canonical after direction alignment/CropCleaner and
    therefore use the supplied oriented dimensions without further rotation.
    """
    width = int(_finite_number(source_width))
    height = int(_finite_number(source_height))
    if width <= 0 or height <= 0:
        raise ValueError("source dimensions must be positive")
    if not isinstance(frames, list):
        raise ValueError("frames must be a list")
    if not isinstance(offsets, dict):
        raise ValueError("offsets must be an object")

    top_offset = _finite_number(offsets.get("top"))
    bottom_offset = _finite_number(offsets.get("bottom"))
    left_offset = _finite_number(offsets.get("left"))
    right_offset = _finite_number(offsets.get("right"))
    adjusted = copy.deepcopy(frames)

    for frame in adjusted:
        top = _frame_pixel(frame, "top", "relativeTop", height, 0) - top_offset
        bottom = _frame_pixel(frame, "bottom", "relativeBottom", height, height) + bottom_offset
        left = _frame_pixel(frame, "left", "relativeLeft", width, 0) - left_offset
        right = _frame_pixel(frame, "right", "relativeRight", width, width) + right_offset
        top, bottom = _axis_bounds(top, bottom, height)
        left, right = _axis_bounds(left, right, width)
        frame.update({
            "top": top, "bottom": bottom, "left": left, "right": right,
            "relativeTop": round(top / height, 6), "relativeBottom": round(bottom / height, 6),
            "relativeLeft": round(left / width, 6), "relativeRight": round(right / width, 6),
        })
    return adjusted


def render_preview(image_path, frames, output_path):
    """Write an annotated JPEG preview, bounded to a 1200-pixel long edge."""
    image_path = Path(image_path)
    output_path = Path(output_path)
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    long_edge = max(image.size)
    scale = min(1.0, 1200 / long_edge) if long_edge else 1.0
    if scale < 1.0:
        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)

    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    for position, frame in enumerate(frames, start=1):
        left = round(_finite_number(frame.get("left")) * scale)
        top = round(_finite_number(frame.get("top")) * scale)
        right = round(_finite_number(frame.get("right")) * scale)
        bottom = round(_finite_number(frame.get("bottom")) * scale)
        draw.rectangle((left, top, right, bottom), outline=(255, 64, 32), width=max(1, round(2 * scale)))
        label = str(frame.get("index", position))
        draw.text((left + 3, top + 3), label, fill=(255, 64, 32), font=font, stroke_width=1, stroke_fill=(255, 255, 255))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="JPEG", quality=90)
    return output_path
