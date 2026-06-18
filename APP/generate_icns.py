"""Generate NegativeCutter.app icon set and compile to .icns (macOS)."""

import os
import struct
from io import BytesIO
from math import cos, sin, pi
from pathlib import Path
from PIL import Image, ImageDraw

APP_DIR = Path(__file__).parent
ICNS_PATH = APP_DIR / "NegativeCutter.icns"

# Brand colours (match filmcrop.gui.theme)
_BG = (40, 40, 38)          # #282826  CARD_BG dark
_BRAND = (201, 100, 66)     # #c96442  BRAND terracotta
_BRAND_DIM = (161, 90, 66)  # #a15a42  BRAND_DIM
_IVORY = (250, 249, 245)    # #faf9f5  TEXT_PRIMARY

# macOS .icns type codes for PNG data (macOS 10.8+)
ICNS_TYPES = [
    ("ic04", 16),      # 16x16
    ("ic11", 32),      # 16x16@2x
    ("ic05", 32),      # 32x32
    ("ic12", 64),      # 32x32@2x
    ("ic07", 128),     # 128x128
    ("ic13", 256),     # 128x128@2x
    ("ic08", 256),     # 256x256
    ("ic14", 512),     # 256x256@2x
    ("ic09", 512),     # 512x512
    ("ic10", 1024),    # 512x512@2x
]


def _diamond_points(cx: float, cy: float, radius: float) -> list[tuple[float, float]]:
    """Return diamond polygon points (top, right, bottom, left)."""
    return [
        (cx, cy - radius),
        (cx + radius, cy),
        (cx, cy + radius),
        (cx - radius, cy),
    ]


def _draw_logo(size: int) -> Image.Image:
    """Draw the NegativeCutter diamond mark into a square RGBA image."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    s = float(size)
    cx = cy = s / 2.0

    # Optional subtle rounded plate for larger sizes
    if size >= 32:
        pad = s * 0.07
        radius = s * 0.16
        d.rounded_rectangle(
            (pad, pad, s - pad, s - pad),
            radius=radius,
            fill=_BG,
        )

    outer_radius = s * 0.31
    line_w = max(1.5, s * 0.055)
    d.polygon(
        _diamond_points(cx, cy, outer_radius),
        outline=_BRAND,
        width=int(round(line_w)),
    )

    inner_radius = outer_radius * 0.58
    inner_line_w = max(1.0, s * 0.022)
    d.polygon(
        _diamond_points(cx, cy, inner_radius),
        outline=_BRAND_DIM,
        width=int(round(inner_line_w)),
    )

    lens_radius = s * 0.105
    d.ellipse(
        (
            cx - lens_radius,
            cy - lens_radius,
            cx + lens_radius,
            cy + lens_radius,
        ),
        outline=_BRAND,
        width=int(round(max(1.2, s * 0.035))),
        fill=_BG,
    )

    pupil_radius = max(1.0, s * 0.026)
    d.ellipse(
        (
            cx - pupil_radius,
            cy - pupil_radius,
            cx + pupil_radius,
            cy + pupil_radius,
        ),
        fill=_IVORY,
    )

    return img


def _build_icns() -> bytes:
    """Build an Apple .icns file directly from PNG blobs."""
    entries = []
    for type_code, px in ICNS_TYPES:
        img = _draw_logo(px)
        buf = BytesIO()
        img.save(buf, format="PNG")
        png_data = buf.getvalue()

        # Each entry: 4-byte type + 4-byte size + data
        entry_size = 8 + len(png_data)
        entries.append(struct.pack(">4sI", type_code.encode("ascii"), entry_size) + png_data)

    data = b"".join(entries)
    # File header: 'icns' + total file size
    file_size = 8 + len(data)
    return struct.pack(">4sI", b"icns", file_size) + data


def main():
    icns_data = _build_icns()
    ICNS_PATH.write_bytes(icns_data)
    print(f"→ {ICNS_PATH.name} 已生成 ({len(icns_data)} bytes)")


if __name__ == "__main__":
    main()
