#!/usr/bin/env python3
"""
FilmCrop debug visualization — compatible with filmcrop.detector v2.x

Usage:
    python3 debug_visualize.py <image_path> [--frames N] [--cleanup-scale X.X] [--original <path>]

Output:
    <image_path>.debug.jpg  — annotated preview with gap edges, frame boxes, and stats
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def _load_image(path: str) -> Image.Image:
    """Load image, handling 16-bit TIFF."""
    img = Image.open(path)
    if img.mode in ("I;16", "I;16B", "I;16N", "I"):
        arr_16 = np.array(img)
        arr = ((arr_16.astype(np.float32) / 65535.0) * 255).astype(np.uint8)
        img = Image.fromarray(arr, mode="L")
    elif img.mode != "L":
        img = img.convert("L")
    return img


def _get_font(size: int = 14):
    """Try to load a monospace font, fallback to default."""
    for font_name in ("Courier New", "Menlo", "DejaVu Sans Mono", "monospace"):
        try:
            return ImageFont.truetype(font_name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_text_panel(draw, text_lines, x, y, font, bg_alpha=180):
    """Draw a semi-transparent text panel."""
    if not text_lines:
        return
    max_w = 0
    line_h = font.size + 4
    for line in text_lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        max_w = max(max_w, bbox[2] - bbox[0])
    panel_w = max_w + 16
    panel_h = len(text_lines) * line_h + 10
    overlay = Image.new("RGBA", (panel_w, panel_h), (0, 0, 0, bg_alpha))
    draw_overlay = ImageDraw.Draw(overlay)
    draw_overlay.rectangle([(0, 0), (panel_w - 1, panel_h - 1)], outline=(255, 255, 255, 120), width=1)
    return overlay, panel_w, panel_h


def main():
    img_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not img_path or not Path(img_path).exists():
        print(f"用法: python3 {sys.argv[0]} <image_path> [--frames N] [--cleanup-scale X.X] [--original <path>]")
        sys.exit(1)

    expected_frames = 6
    cleanup_scale = 0.50
    original_path = None

    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--frames" and i + 1 < len(sys.argv):
            expected_frames = int(sys.argv[i + 1])
            i += 2
        elif arg == "--cleanup-scale" and i + 1 < len(sys.argv):
            cleanup_scale = float(sys.argv[i + 1])
            i += 2
        elif arg == "--original" and i + 1 < len(sys.argv):
            original_path = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    # ------------------------------------------------------------------
    # 1. Run detection
    # ------------------------------------------------------------------
    sys.path.insert(0, str(Path(__file__).parent))
    from filmcrop.detector import analyze_image

    result = analyze_image(img_path, expected_frames, cleanup_scale, original_path)
    frames = result["frames"]
    debug = result.get("debug", {})
    is_horizontal = debug.get("isHorizontal", result["sourceWidth"] >= result["sourceHeight"])
    gap_edges = debug.get("gapEdges", [])
    long_edges = debug.get("longEdges", [0, 0])
    crop_angle = result.get("cropAngle", 0)
    mode = debug.get("mode", "unknown")

    # ------------------------------------------------------------------
    # 2. Load and resize image for visualization
    # ------------------------------------------------------------------
    img = _load_image(img_path)
    width, height = img.size
    scale = 1200 / max(width, height) if max(width, height) > 1200 else 1.0
    viz_w = int(width * scale)
    viz_h = int(height * scale)
    viz_img = img.resize((viz_w, viz_h), Image.LANCZOS).convert("RGB")
    draw = ImageDraw.Draw(viz_img)
    font = _get_font(13)
    font_small = _get_font(11)

    # ------------------------------------------------------------------
    # 3. Draw gap edges (red/blue lines)
    # ------------------------------------------------------------------
    for le, re in gap_edges:
        if is_horizontal:
            x1 = int(le * scale)
            x2 = int(re * scale)
            draw.line([(x1, 0), (x1, viz_h)], fill=(255, 0, 0), width=2)
            draw.line([(x2, 0), (x2, viz_h)], fill=(0, 0, 255), width=2)
        else:
            y1 = int(le * scale)
            y2 = int(re * scale)
            draw.line([(0, y1), (viz_w, y1)], fill=(255, 0, 0), width=2)
            draw.line([(0, y2), (viz_w, y2)], fill=(0, 0, 255), width=2)

    # ------------------------------------------------------------------
    # 4. Draw long edges (yellow lines)
    # ------------------------------------------------------------------
    if long_edges and len(long_edges) == 2 and long_edges != [0, 0]:
        near, far = long_edges
        if is_horizontal:
            y1 = int(near * scale)
            y2 = int(far * scale)
            draw.line([(0, y1), (viz_w, y1)], fill=(255, 255, 0), width=2)
            draw.line([(0, y2), (viz_w, y2)], fill=(255, 255, 0), width=2)
        else:
            x1 = int(near * scale)
            x2 = int(far * scale)
            draw.line([(x1, 0), (x1, viz_h)], fill=(255, 255, 0), width=2)
            draw.line([(x2, 0), (x2, viz_h)], fill=(255, 255, 0), width=2)

    # ------------------------------------------------------------------
    # 5. Draw frame boxes with semi-transparent overlay
    # ------------------------------------------------------------------
    colors = [
        (255, 50, 50),   # red
        (50, 255, 50),   # green
        (50, 50, 255),   # blue
        (255, 255, 50),  # yellow
        (255, 50, 255),  # magenta
        (50, 255, 255),  # cyan
        (255, 150, 50),  # orange
        (150, 50, 255),  # purple
    ]

    overlay = Image.new("RGBA", (viz_w, viz_h), (0, 0, 0, 0))
    draw_o = ImageDraw.Draw(overlay)

    for idx, frame in enumerate(frames):
        color = colors[idx % len(colors)]
        if is_horizontal:
            x1 = int((frame.get("left", 0)) * scale)
            x2 = int((frame.get("right", width)) * scale)
            y1 = int((frame.get("top", 0)) * scale)
            y2 = int((frame.get("bottom", height)) * scale)
        else:
            x1 = int((frame.get("left", 0)) * scale)
            x2 = int((frame.get("right", width)) * scale)
            y1 = int((frame.get("top", 0)) * scale)
            y2 = int((frame.get("bottom", height)) * scale)

        draw_o.rectangle([(x1, y1), (x2, y2)], outline=(*color, 200), width=2)
        # Semi-transparent fill
        draw_o.rectangle([(x1, y1), (x2, y2)], fill=(*color, 25))

        # Frame number label
        label = f"{idx + 1}"
        bbox = draw_o.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        lx = x1 + 4
        ly = y1 + 4
        draw_o.rectangle([(lx, ly), (lx + tw + 6, ly + th + 4)], fill=(0, 0, 0, 160))
        draw_o.text((lx + 3, ly), label, fill=(*color, 255), font=font)

    viz_img = Image.alpha_composite(viz_img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(viz_img)

    # ------------------------------------------------------------------
    # 6. Stats text panel
    # ------------------------------------------------------------------
    lines = [
        f"FilmCrop Debug  |  {result['frameCount']} frames  |  mode={mode}",
        f"Orient: {'H' if is_horizontal else 'V'}  |  Angle: {crop_angle:.2f}deg",
        f"Long edges: {long_edges[0]}, {long_edges[1]}  (span={long_edges[1] - long_edges[0]}px)",
        "",
        "Gap widths (px):",
    ]
    for i, (le, re) in enumerate(gap_edges):
        lines.append(f"  Gap {i + 1}: {re - le}px")

    lines.append("")
    lines.append("Frame heights (px):")
    for f in frames:
        h = f.get("bottom", 0) - f.get("top", 0)
        lines.append(f"  Frame {f['index']}: {h}px")

    panel_w = 0
    line_h = font.size + 4
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        panel_w = max(panel_w, bbox[2] - bbox[0])
    panel_w += 16
    panel_h = len(lines) * line_h + 10

    margin = 10
    px = viz_w - panel_w - margin
    py = margin
    draw.rectangle([(px, py), (px + panel_w, py + panel_h)], fill=(0, 0, 0, 180))
    draw.rectangle([(px, py), (px + panel_w, py + panel_h)], outline=(255, 255, 255, 120), width=1)

    for i, line in enumerate(lines):
        draw.text((px + 8, py + 5 + i * line_h), line, fill=(255, 255, 255), font=font)

    # ------------------------------------------------------------------
    # 7. Save
    # ------------------------------------------------------------------
    out_path = str(Path(img_path).with_suffix(".debug.jpg"))
    viz_img.save(out_path, quality=95)
    print(f"Debug image saved: {out_path}")
    print(f"  Frames: {result['frameCount']}  |  Mode: {mode}  |  Angle: {crop_angle:.2f}deg")
    print(f"  Long edges: {long_edges}")
    print(f"  Source: {result['sourceWidth']}x{result['sourceHeight']}")


if __name__ == "__main__":
    main()
