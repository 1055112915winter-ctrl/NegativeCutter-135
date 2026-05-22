"""
FilmCrop export utilities: JSON sidecar, XMP sidecar, and cropped image export.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from PIL import Image


def to_json(frames: list, source_width: int, source_height: int, crop_angle: float = 0.0, debug: dict | None = None) -> str:
    """Serialize frame data to the legacy detect_thumb.py JSON format."""
    data: dict = {
        "frameCount": len(frames),
        "sourceWidth": source_width,
        "sourceHeight": source_height,
        "cropAngle": round(crop_angle, 2),
        "frames": frames,
    }
    if debug is not None:
        data["debug"] = debug
    return json.dumps(data, indent=2, ensure_ascii=False)


def to_xmp(
    frames: list,
    source_width: int,
    source_height: int,
    image_name: str = "image",
    crop_angle: float = 0.0,
) -> str:
    """
    Generate an XMP sidecar string with per-frame crop metadata.

    The output is a single XMP file that contains:

    * Standard Adobe Camera Raw (``crs:``) crop fields for the first
      frame so Lightroom can read a native crop rectangle directly.
    * A custom ``filmcrop:Frames`` RDF sequence preserving all detected
      frame boundaries with both pixel and relative coordinates.
    * Required Dublin Core (``dc:title``) and XMP Media Management
      (``xmpMM:DocumentID``) fields.

    Parameters
    ----------
    frames :
        List of frame dicts (must contain ``index``, ``top``, ``bottom``,
        ``left``, ``right``, ``relativeTop``, ``relativeBottom``,
        ``relativeLeft``, ``relativeRight``).
    source_width, source_height :
        Dimensions of the source image in pixels.
    image_name :
        Value for ``dc:title`` (XML-escaped automatically).
    crop_angle :
        Rotation angle in degrees for the first-frame ``crs:CropAngle``.

    Returns
    -------
    str
        Well-formed XMP XML.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    safe_title = escape(image_name, {"\"": "&quot;"})
    doc_id = "xmp.did:filmcrop"

    # First-frame standard Camera Raw crop (relative 0-1)
    if frames:
        first = frames[0]
        crs_top = first.get("relativeTop", 0.0)
        crs_left = first.get("relativeLeft", 0.0)
        crs_bottom = first.get("relativeBottom", 1.0)
        crs_right = first.get("relativeRight", 1.0)
    else:
        crs_top = crs_left = 0.0
        crs_bottom = crs_right = 1.0

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">',
        '  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"',
        '           xmlns:xmp="http://ns.adobe.com/xap/1.0/"',
        '           xmlns:dc="http://purl.org/dc/elements/1.1/"',
        '           xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/"',
        '           xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"',
        '           xmlns:filmcrop="http://filmcrop.io/ns/1.0/">',
        '    <rdf:Description rdf:about=""',
        f'                     dc:title="{safe_title}"',
        f'                     xmp:CreateDate="{now}"',
        f'                     xmpMM:DocumentID="{doc_id}"',
        '                     crs:HasCrop="True"',
        f'                     crs:CropTop="{crs_top:.6f}"',
        f'                     crs:CropLeft="{crs_left:.6f}"',
        f'                     crs:CropBottom="{crs_bottom:.6f}"',
        f'                     crs:CropRight="{crs_right:.6f}"',
        f'                     crs:CropAngle="{crop_angle:.2f}">',
        '      <filmcrop:Frames>',
        '        <rdf:Seq>',
    ]

    for frame in frames:
        lines.append("          <rdf:li>")
        lines.append("            <rdf:Description")
        for key in (
            "index",
            "relativeTop",
            "relativeBottom",
            "relativeLeft",
            "relativeRight",
            "top",
            "bottom",
            "left",
            "right",
        ):
            val = frame.get(key)
            if val is None:
                default = 0 if key != "index" else 0
                if key in ("bottom", "right"):
                    default = source_height if key == "bottom" else source_width
                val = default
            lines.append(f'              filmcrop:{key}="{val}"')
        lines.append("            />")
        lines.append("          </rdf:li>")

    lines.extend([
        "        </rdf:Seq>",
        "      </filmcrop:Frames>",
        "    </rdf:Description>",
        "  </rdf:RDF>",
        "</x:xmpmeta>",
        "",
    ])

    return "\n".join(lines)


def validate_xmp(xmp_string: str) -> tuple[bool, str]:
    """
    Perform a basic structural validation of an XMP string.

    Checks:
    * Well-formed XML
    * Presence of ``xmpMM:DocumentID``
    * Presence of ``dc:title``
    * Presence of ``filmcrop:Frames/rdf:Seq``
    * At least one ``rdf:li`` with ``filmcrop:index``

    Returns
    -------
    tuple[bool, str]
        ``(is_valid, message)``
    """
    try:
        root = ET.fromstring(xmp_string)
    except ET.ParseError as exc:
        return False, f"XML parse error: {exc}"

    # XMP uses many namespaces; search broadly
    text = xmp_string
    required = {
        "xmpMM:DocumentID": "xmpMM:DocumentID" in text,
        "dc:title": 'dc:title=' in text or 'dc:title="' in text,
        "filmcrop:Frames": "filmcrop:Frames" in text,
        "rdf:Seq": "<rdf:Seq>" in text,
    }

    missing = [k for k, v in required.items() if not v]
    if missing:
        return False, f"Missing required elements: {', '.join(missing)}"

    if "filmcrop:index" not in text:
        return False, "No filmcrop:index attributes found in frame list"

    return True, "XMP structure looks valid"


def crop_and_save(
    image_path: str,
    frames: list,
    output_dir: str,
    fmt: str = "tiff",
    quality: int = 95,
    color_space: str = "sRGB",
) -> List[str]:
    """
    Crop each frame from *image_path* and save to *output_dir*.

    Uses *PIL* ``Image.crop()`` directly; if any down-sampling is
    required it uses ``Image.Resampling.LANCZOS``.

    Parameters
    ----------
    fmt : str
        Output format: ``tiff``, ``jpeg``, or ``png``.
    quality : int
        JPEG quality (1-100); ignored for TIFF/PNG.
    color_space : str
        ICC profile hint (``sRGB`` or ``Adobe RGB``).  The original
        image's ICC profile is preserved when possible; for JPEG
        exports the profile is embedded if the source contained one.

    Returns
    -------
    List[str]
        Paths to the written files.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    img: Image.Image = Image.open(image_path)
    base_name = Path(image_path).stem
    written: List[str] = []

    # Preserve original ICC profile and bit depth info
    icc_profile = img.info.get("icc_profile")
    src_mode = img.mode
    is_16bit = src_mode in ("I;16", "I;16B", "I;16N", "I")

    for frame in frames:
        left = frame.get("left", 0)
        top = frame.get("top", 0)
        right = frame.get("right", img.width)
        bottom = frame.get("bottom", img.height)
        crop = img.crop((left, top, right, bottom))

        idx = frame.get("index", 1)
        suffix = f"_frame_{idx:02d}"

        save_kwargs: dict = {}
        if icc_profile is not None:
            save_kwargs["icc_profile"] = icc_profile

        fmt_lower = fmt.lower()
        if fmt_lower in ("tiff", "tif"):
            dest = out / f"{base_name}{suffix}.tif"
            # Preserve 16-bit depth for TIFF when input is 16-bit
            if is_16bit and crop.mode not in ("I;16", "I;16B", "I;16N", "I"):
                # If crop somehow changed mode, try to restore it
                pass  # PIL crop should preserve mode
            crop.save(dest, format="TIFF", **save_kwargs)
        elif fmt_lower in ("jpeg", "jpg"):
            dest = out / f"{base_name}{suffix}.jpg"
            if crop.mode in ("I", "I;16", "I;16B", "I;16N"):
                crop = crop.convert("RGB")
            elif crop.mode == "RGBA":
                crop = crop.convert("RGB")
            save_kwargs["quality"] = quality
            crop.save(dest, format="JPEG", **save_kwargs)
        else:
            dest = out / f"{base_name}{suffix}.png"
            crop.save(dest, format="PNG", **save_kwargs)

        written.append(str(dest))

    return written
