#!/usr/bin/env python3
"""
Debug visualization for FilmCrop detection v1.4-fix5.
Supports both horizontal and vertical film strips.
Shows BOTH valley (dark-gap) and peak (bright-gap) predictions side-by-side.
Red line = gap left edge, Blue line = gap right edge.
Run: python3 debug_detect.py <path_to_scan_image> [--frames N] [--cleanup-scale X.X]
"""

import sys
import numpy as np
from PIL import Image, ImageDraw
from pathlib import Path

import detect_thumb as dt


def draw_preview(img_gray, gap_edges, title, scale, is_horizontal=True, long_edges=None):
    viz_w = int(img_gray.size[0] * scale)
    viz_h = int(img_gray.size[1] * scale)
    img_viz = img_gray.resize((viz_w, viz_h), Image.LANCZOS).convert('RGB')
    draw = ImageDraw.Draw(img_viz)
    for le, re in gap_edges:
        if is_horizontal:
            x1 = int(le * scale)
            x2 = int(re * scale)
            draw.line([(x1, 0), (x1, viz_h)], fill=(255, 0, 0), width=2)   # 左边界 红
            draw.line([(x2, 0), (x2, viz_h)], fill=(0, 0, 255), width=2)   # 右边界 蓝
        else:
            y1 = int(le * scale)
            y2 = int(re * scale)
            draw.line([(0, y1), (viz_w, y1)], fill=(255, 0, 0), width=2)   # 上边界 红
            draw.line([(0, y2), (viz_w, y2)], fill=(0, 0, 255), width=2)   # 下边界 蓝
    if long_edges:
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
    draw.text((5, 5), title, fill=(255, 255, 0))
    return img_viz


def draw_graph(smoothed, valley_edges, peak_edges, scan_size, viz_w, is_horizontal=True):
    graph_h = 200
    canvas = Image.new('RGB', (viz_w, graph_h), (30, 30, 30))
    draw = ImageDraw.Draw(canvas)
    min_sm = float(np.min(smoothed))
    max_sm = float(np.max(smoothed))
    rng = max_sm - min_sm if max_sm > min_sm else 1.0

    points = []
    scale_x = viz_w / scan_size
    for x in range(viz_w):
        src_x = min(int(x / scale_x), len(smoothed) - 1)
        y = 10 + int((1 - (smoothed[src_x] - min_sm) / rng) * (graph_h - 40))
        points.append((x, y))
    for i in range(len(points) - 1):
        draw.line([points[i], points[i+1]], fill=(200, 200, 200), width=1)

    # valley 左边界红线，右边界品红线
    for le, re in valley_edges:
        x1 = int(le * scale_x)
        x2 = int(re * scale_x)
        draw.line([(x1, 10), (x1, graph_h - 10)], fill=(255, 0, 0), width=2)
        draw.line([(x2, 10), (x2, graph_h - 10)], fill=(255, 0, 255), width=2)

    # peak 左边界绿线，右边界青线
    for le, re in peak_edges:
        x1 = int(le * scale_x)
        x2 = int(re * scale_x)
        draw.line([(x1, 10), (x1, graph_h - 10)], fill=(0, 255, 0), width=2)
        draw.line([(x2, 10), (x2, graph_h - 10)], fill=(0, 255, 255), width=2)

    orient_label = "H" if is_horizontal else "V"
    draw.text((5, graph_h - 20), f"Valley:R/M | Peak:G/C | Gray:projection | {orient_label}", fill=(255, 255, 255))
    return canvas


def draw_cross_graph(smoothed_cross, long_edges, cross_size, viz_size, is_horizontal=True):
    """绘制垂直于主排列方向的投影图（长边边缘检测）"""
    graph_h = 120
    canvas = Image.new('RGB', (viz_size, graph_h), (30, 30, 30))
    draw = ImageDraw.Draw(canvas)
    min_sm = float(np.min(smoothed_cross))
    max_sm = float(np.max(smoothed_cross))
    rng = max_sm - min_sm if max_sm > min_sm else 1.0

    points = []
    scale_x = viz_size / cross_size
    for x in range(viz_size):
        src_x = min(int(x / scale_x), len(smoothed_cross) - 1)
        y = 10 + int((1 - (smoothed_cross[src_x] - min_sm) / rng) * (graph_h - 40))
        points.append((x, y))
    for i in range(len(points) - 1):
        draw.line([points[i], points[i + 1]], fill=(200, 200, 200), width=1)

    if long_edges:
        near, far = long_edges
        x1 = int(near * scale_x)
        x2 = int(far * scale_x)
        draw.line([(x1, 10), (x1, graph_h - 10)], fill=(255, 255, 0), width=2)
        draw.line([(x2, 10), (x2, graph_h - 10)], fill=(255, 255, 0), width=2)

    label = "Cross-axis (long edges) | Yellow=margin"
    draw.text((5, graph_h - 20), label, fill=(255, 255, 255))
    return canvas


def main():
    img_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not img_path or not Path(img_path).exists():
        print(f"用法: python3 {sys.argv[0]} <scan_image> [--frames N] [--cleanup-scale X.X]")
        sys.exit(1)

    expected_frames = 6
    cleanup_scale = 0.5
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

    img = Image.open(img_path)
    if img.mode in ('I;16', 'I;16B', 'I;16N', 'I'):
        arr_16 = np.array(img)
        arr = ((arr_16.astype(np.float32) / 65535.0) * 255).astype(np.uint8)
        img_gray = Image.fromarray(arr, mode='L')
    else:
        img_gray = img.convert('L')
        arr = np.array(img_gray)
    height, width = arr.shape
    is_horizontal = width >= height

    scan_size = width if is_horizontal else height

    # 自动帧数检测
    if expected_frames <= 0:
        auto_result = dt.analyze_thumb(img_path, expected_frames, cleanup_scale)
        expected_frames = auto_result.get('debug', {}).get('autoDetectedFrames', auto_result.get('frameCount', 6))
        print(f"Auto-detected frames: {expected_frames}")

    pstep = scan_size / expected_frames

    if is_horizontal:
        projection = np.mean(arr, axis=0) / 255.0
    else:
        projection = np.mean(arr, axis=1) / 255.0

    window_size = max(5, min(21, int(pstep * 0.08)))
    if window_size % 2 == 0:
        window_size += 1
    kernel = np.ones(window_size) / window_size
    padded = np.pad(projection, (window_size // 2, window_size // 2), mode='edge')
    smoothed = np.convolve(padded, kernel, mode='valid')

    # valley
    valley_bounds = dt.refine_boundaries(dt.find_boundaries(smoothed, expected_frames, scan_size, 'valley'), smoothed, expected_frames, scan_size)
    valley_edges = dt.gap_edges_from_boundaries(smoothed, valley_bounds, expected_frames, scan_size, 'valley', cleanup_scale)
    vv = dt.evaluate_uniformity([0] + [e for pair in valley_edges for e in pair] + [scan_size])
    valley_angle = dt.estimate_rotation(arr, expected_frames, width, height, is_horizontal, 'valley')

    # peak
    peak_bounds = dt.refine_boundaries(dt.find_boundaries(smoothed, expected_frames, scan_size, 'peak'), smoothed, expected_frames, scan_size)
    peak_edges = dt.gap_edges_from_boundaries(smoothed, peak_bounds, expected_frames, scan_size, 'peak', cleanup_scale)
    pv = dt.evaluate_uniformity([0] + [e for pair in peak_edges for e in pair] + [scan_size])
    peak_angle = dt.estimate_rotation(arr, expected_frames, width, height, is_horizontal, 'peak')

    scale = 800 / max(width, height) if max(width, height) > 800 else 1.0
    viz_w = int(width * scale)
    viz_h = int(height * scale)

    # 长边边缘检测（使用与 auto-selected 相同的模式）
    # 缩略图分辨率不足时（长边检测轴向 < 2000），用原图补长边检测
    selected_mode = 'peak' if pv < vv else 'valley'
    long_edge_arr = arr
    cross_size = height if is_horizontal else width
    if original_path and cross_size < 2000:
        try:
            long_edge_arr = dt._load_image_array(original_path)
            print(f"[Debug] Using original image for long-edge detection")
        except Exception as e:
            print(f"[Debug] Failed to load original for long-edge: {e}")
    long_edges = dt.detect_long_edges(long_edge_arr, is_horizontal, selected_mode)
    if long_edges == (0, (height if is_horizontal else width)):
        opposite_mode = 'valley' if selected_mode == 'peak' else 'peak'
        long_edges = dt.detect_long_edges(long_edge_arr, is_horizontal, opposite_mode)

    # 计算 cross-axis 投影用于绘图
    if is_horizontal:
        cross_proj = np.mean(arr, axis=1) / 255.0
    else:
        cross_proj = np.mean(arr, axis=0) / 255.0
    cross_size = len(cross_proj)
    ksize = max(3, cross_size // 200)
    if ksize % 2 == 0:
        ksize += 1
    kernel = np.ones(ksize) / ksize
    smoothed_cross = np.convolve(cross_proj, kernel, mode='same')

    valley_img = draw_preview(img_gray, valley_edges, f"Valley (var={vv:.0f})", scale, is_horizontal, long_edges)
    peak_img = draw_preview(img_gray, peak_edges, f"Peak (var={pv:.0f})", scale, is_horizontal, long_edges)
    graph_img = draw_graph(smoothed, valley_edges, peak_edges, scan_size, viz_w, is_horizontal)
    cross_graph_img = draw_cross_graph(smoothed_cross, long_edges, cross_size, viz_w, is_horizontal)

    total_h = viz_h * 2 + graph_img.size[1] + cross_graph_img.size[1] + 80
    canvas = Image.new('RGB', (viz_w, total_h), (20, 20, 20))
    canvas.paste(valley_img, (0, 0))
    canvas.paste(peak_img, (0, viz_h + 10))
    canvas.paste(graph_img, (0, viz_h * 2 + 20))
    canvas.paste(cross_graph_img, (0, viz_h * 2 + graph_img.size[1] + 30))

    out_path = str(Path(img_path).with_suffix('.debug.jpg'))
    canvas.save(out_path, quality=95)
    print(f"Debug image saved: {out_path}")
    print(f"Valley gap edges: {valley_edges}  variance={vv:.1f}  angle={valley_angle:.2f}")
    print(f"Peak gap edges:   {peak_edges}  variance={pv:.1f}  angle={peak_angle:.2f}")
    selected = 'peak' if pv < vv else 'valley'
    sel_angle = peak_angle if pv < vv else valley_angle
    print(f"Auto-selected: {selected}  angle={sel_angle:.2f}  orient={'H' if is_horizontal else 'V'}  long_edges={long_edges}")


if __name__ == '__main__':
    main()
