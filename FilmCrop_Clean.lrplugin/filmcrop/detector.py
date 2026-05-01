"""
FilmCrop core detection engine.

Extracted and cleaned from detect_thumb.py v1.5.1.
All image analysis, frame detection, and boundary computation lives here.
"""

import math
import time
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def _load_image_array(path: str) -> np.ndarray:
    """Load image as grayscale uint8 ndarray, handling 16-bit TIFF."""
    img: Image.Image = Image.open(path)
    if img.mode in ("I;16", "I;16B", "I;16N", "I"):
        arr_16 = np.array(img)
        arr = ((arr_16.astype(np.float32) / 65535.0) * 255).astype(np.uint8)
    elif img.mode != "L":
        img = img.convert("L")
        arr = np.array(img)
    else:
        arr = np.array(img)
    return arr


def find_boundaries(arr, expected_frames, size, mode="valley"):
    """Locate frame-gap centres near theoretical positions."""
    pstep = size / expected_frames
    diffstep = max(10, int(pstep * 0.45))
    boundaries = [0]
    tol = 0.005
    for f in range(1, expected_frames):
        pc_min = max(0, int(f * pstep - diffstep))
        pc_max = min(size, int(f * pstep + diffstep))
        if pc_max <= pc_min:
            boundaries.append(int(f * pstep))
            continue
        sub = arr[pc_min:pc_max]
        pos = int(np.argmax(sub)) if mode == "peak" else int(np.argmin(sub))

        if mode == "peak":
            ls = pos
            while ls > 0 and sub[ls] >= sub[pos] - tol:
                ls -= 1
            rs = pos
            while rs < len(sub) - 1 and sub[rs] >= sub[pos] - tol:
                rs += 1
        else:
            ls = pos
            while ls > 0 and sub[ls] <= sub[pos] + tol:
                ls -= 1
            rs = pos
            while rs < len(sub) - 1 and sub[rs] <= sub[pos] + tol:
                rs += 1
        tol_pos = (ls + rs) // 2
        max_shift = 15
        shift = max(-max_shift, min(max_shift, tol_pos - pos))
        pos = pos + shift

        boundary_pos = pc_min + pos
        if boundary_pos <= boundaries[-1]:
            boundary_pos = boundaries[-1] + 1
        boundaries.append(boundary_pos)
    boundaries.append(size)
    return boundaries


def refine_boundaries(boundaries, arr, expected_frames, size):
    """Drop weakest boundaries if we have too many."""
    if len(boundaries) <= expected_frames + 1:
        return boundaries
    depths = []
    for i in range(1, len(boundaries) - 1):
        b = boundaries[i]
        left_avg = np.mean(arr[max(0, b - 5):b])
        right_avg = np.mean(arr[b:min(size, b + 5)])
        depths.append((b, abs(left_avg - right_avg)))
    depths.sort(key=lambda x: x[1], reverse=True)
    kept = sorted([d[0] for d in depths[: expected_frames - 1]])
    return [0] + kept + [size]


def evaluate_uniformity(boundaries):
    """Score how evenly spaced boundaries are."""
    widths = [boundaries[i + 1] - boundaries[i] for i in range(len(boundaries) - 1)]
    if not widths:
        return float("inf")
    mean_w = np.mean(widths)
    return float(np.mean([(w - mean_w) ** 2 for w in widths]))


def estimate_rotation(arr, expected_frames, width, height, is_horizontal=True, mode="valley"):
    """Estimate global skew angle by comparing top/bottom (or left/right) gap positions."""
    if is_horizontal:
        if height is None or height < 10:
            return 0.0
        scan_size = width
        cross_size = height
        pstep = scan_size / expected_frames
        diffstep = max(5, int(pstep * 0.30))
        mid_y = cross_size // 2
        q1 = int(cross_size * 0.25)
        q3 = int(cross_size * 0.75)
        top_proj = arr[q1:mid_y, :].mean(axis=0) / 255.0
        bot_proj = arr[mid_y:q3, :].mean(axis=0) / 255.0
        projs = [top_proj, bot_proj]
    else:
        if width is None or width < 10:
            return 0.0
        scan_size = height
        cross_size = width
        pstep = scan_size / expected_frames
        diffstep = max(5, int(pstep * 0.30))
        mid_x = cross_size // 2
        q1 = int(cross_size * 0.25)
        q3 = int(cross_size * 0.75)
        left_proj = arr[:, q1:mid_x].mean(axis=1) / 255.0
        right_proj = arr[:, mid_x:q3].mean(axis=1) / 255.0
        projs = [left_proj, right_proj]

    ksize = max(5, scan_size // 200)
    if ksize % 2 == 0:
        ksize += 1
    kernel = np.ones(ksize) / ksize
    smooth_projs = [np.convolve(p, kernel, mode="same") for p in projs]

    offsets = []
    for f in range(1, expected_frames):
        pc_min = max(0, int(f * pstep - diffstep))
        pc_max = min(scan_size, int(f * pstep + diffstep))
        if pc_max <= pc_min:
            continue
        subs = [sp[pc_min:pc_max] for sp in smooth_projs]
        centers = []
        for sub in subs:
            centers.append(pc_min + (int(np.argmax(sub)) if mode == "peak" else int(np.argmin(sub))))
        if len(centers) == 2:
            offsets.append(centers[1] - centers[0])

    if not offsets:
        return 0.0
    med_offset = float(np.median(offsets))
    dy = (q3 - q1) / 2.0
    return math.degrees(math.atan2(med_offset, dy))


def gap_edges_from_boundaries(arr, boundaries, expected_frames, size, mode="valley", cleanup_scale=0.5):
    """Convert boundary centres into (left_edge, right_edge) gap pairs."""
    pstep = size / expected_frames
    search_r = max(20, int(pstep * 0.35))
    max_gap = int(pstep * 0.45)
    min_hw = max(2, int(pstep * 0.002))
    max_hw = int(pstep * 0.06)

    gap_edges = []
    prev = 0
    for b in boundaries[1:-1]:
        s0 = max(0, b - search_r)
        s1 = min(size, b + search_r)
        sub = arr[s0:s1]

        lo = float(np.percentile(sub, 10))
        hi = float(np.percentile(sub, 90))
        contrast = hi - lo
        if contrast < 0.03:
            gap_edges.append((b, b))
            prev = b
            continue

        th = (lo + hi) / 2.0
        if mode == "peak":
            is_gap = sub > th
        else:
            is_gap = sub < th

        b_rel = b - s0
        left = b_rel
        while left > 0 and is_gap[left - 1]:
            left -= 1
        right = b_rel
        while right < len(sub) - 1 and is_gap[right + 1]:
            right += 1

        if (left == 0 or right == len(sub) - 1) and (right - left + 1) > max_gap:
            gap_edges.append((b, b))
            prev = b
            continue

        hw = min(b_rel - left, right - b_rel)
        hw = int(hw * cleanup_scale)
        hw = max(min_hw, min(max_hw, hw))
        le = max(prev + 1, b - hw)
        re = max(le + 1, b + hw)
        gap_edges.append((le, re))
        prev = re

    if gap_edges and gap_edges[-1][1] >= size:
        le, re = gap_edges[-1]
        gap_edges[-1] = (min(le, size - 2), size - 1)
    return gap_edges


def _find_margin_threshold(proj_slice, size, mode):
    """Steep-edge threshold-crossing method."""
    if len(proj_slice) < 2:
        return None
    vmin = float(np.min(proj_slice))
    vmax = float(np.max(proj_slice))
    contrast = vmax - vmin
    if contrast < 0.010:
        return None

    def try_ratio(r):
        if mode == "peak":
            th = vmax - contrast * r
            is_margin = proj_slice > th
        else:
            th = vmin + contrast * r
            is_margin = proj_slice < th
        for i in range(len(is_margin)):
            if not is_margin[i]:
                return max(0, i - 1)
        return len(is_margin) - 1

    e_steep = try_ratio(0.10)
    e_gentle = try_ratio(0.45)
    diff = abs(e_steep - e_gentle)
    if diff < size * 0.02:
        return e_steep
    elif diff < size * 0.12:
        return int(e_steep * 0.85 + e_gentle * 0.15)
    return None


def _find_margin_content_ref(proj_slice, content_ref):
    """Content-reference method for wide, gentle transitions."""
    if len(proj_slice) < 50:
        return None
    edge_ref = float(np.mean(proj_slice[:5]))
    contrast = abs(edge_ref - content_ref)
    if contrast < 0.03:
        return None
    tol = contrast * 0.10
    for i in range(len(proj_slice)):
        if abs(float(proj_slice[i]) - content_ref) < tol:
            return i
    return None


def detect_long_edges(arr, is_horizontal, mode="valley", margin_search_ratio=0.95):
    """Detect long-edge crop boundaries (film edge vs frame content)."""
    if is_horizontal:
        projection = np.mean(arr, axis=1) / 255.0
    else:
        projection = np.mean(arr, axis=0) / 255.0

    size = len(projection)
    search_len = max(5, int(size * margin_search_ratio))

    ksize = max(3, size // 400)
    if ksize % 2 == 0:
        ksize += 1
    kernel = np.ones(ksize) / ksize
    padded = np.pad(projection, (ksize // 2, ksize // 2), mode="edge")
    smoothed = np.convolve(padded, kernel, mode="valid")

    content_ref = float(np.median(smoothed[size // 4 : size * 3 // 4]))

    near_candidates = []
    far_candidates = []
    for m in ("valley", "peak"):
        near_t = _find_margin_threshold(smoothed[:search_len], size, m)
        near_c = _find_margin_content_ref(smoothed[:search_len], content_ref)
        near_best = max(near_t or 0, near_c or 0)
        if near_best > 0:
            near_candidates.append(near_best)

        right_slice = smoothed[-search_len:][::-1]
        far_t = _find_margin_threshold(right_slice, size, m)
        far_c = _find_margin_content_ref(right_slice, content_ref)
        far_best = max(far_t or 0, far_c or 0)
        if far_best > 0:
            far_candidates.append(size - far_best)

    if not near_candidates and not far_candidates:
        return 0, size

    near = max(near_candidates) if near_candidates else 0
    far = min(far_candidates) if far_candidates else size
    if (far - near) < size * 0.1:
        return 0, size
    return int(near), int(far)


def _detect_long_edges_proportional(arr, is_horizontal, chosen_edges, aspect_ratio=3 / 2):
    """
    Find long-edge boundaries using an aspect-ratio constraint.

    Instead of assuming left/right (or top/bottom) edges are symmetric,
    we derive the target long-edge size from the median frame dimension
    (detected by gap analysis) and the known film aspect ratio, then
    search for the best-fitting window on the projection profile.

    The "best" window is the one with maximum brightness variance:
    film-frame content has more texture than black border / sprocket
    holes, so higher variance = more picture.
    """
    if not chosen_edges or aspect_ratio is None or aspect_ratio <= 0:
        return None

    if is_horizontal:
        projection = np.mean(arr, axis=1) / 255.0
    else:
        projection = np.mean(arr, axis=0) / 255.0

    size = len(projection)

    # Compute median frame dimension along scan direction
    frame_dims = []
    prev = 0
    for le, re in chosen_edges:
        frame_dims.append(le - prev)
        prev = re
    frame_dims.append(size - prev)

    median_dim = float(np.median(frame_dims))
    if median_dim <= 0:
        return None

    target = int(round(median_dim / aspect_ratio))
    if target >= size or target < 3:
        return None

    margin = max(5, int(size * 0.03))
    end_limit = size - target - margin + 1
    if end_limit <= margin:
        margin = 0
        end_limit = size - target + 1

    best_start = margin
    best_score = -float("inf")

    for start in range(margin, end_limit):
        window = projection[start:start + target]
        score = float(np.var(window))
        if score > best_score:
            best_score = score
            best_start = start

    return int(best_start), int(best_start + target)


def _detect_scan_edge(proj, mode="peak", expected_frames=6, from_end=False):
    """Detect scan-edge / sprocket-area before first or after last frame."""
    scan_size = len(proj)
    pstep = scan_size / expected_frames
    search_end = max(100, int(scan_size * 0.05), int(pstep * 0.3))

    if from_end:
        sub = proj[-search_end:]
    else:
        sub = proj[:search_end]

    vmin, vmax = float(np.min(sub)), float(np.max(sub))
    contrast = vmax - vmin
    if contrast < 0.03:
        return None

    midpoint = (vmin + vmax) / 2.0

    if from_end:
        for i in range(len(sub) - 1, -1, -1):
            crossed = (mode == "peak" and sub[i] < midpoint) or (mode == "valley" and sub[i] > midpoint)
            if crossed:
                actual_pos = scan_size - search_end + i
                if actual_pos < scan_size - 50 and actual_pos > scan_size - search_end * 0.7:
                    left_avg = float(np.mean(proj[max(0, actual_pos - 50):actual_pos]))
                    right_avg = float(np.mean(proj[actual_pos:min(scan_size, actual_pos + 50)]))
                    if abs(left_avg - right_avg) > 0.01:
                        return actual_pos
                return None
    else:
        for i in range(len(sub)):
            crossed = (mode == "peak" and sub[i] < midpoint) or (mode == "valley" and sub[i] > midpoint)
            if crossed:
                if i > 50 and i < search_end * 0.7:
                    left_avg = float(np.mean(sub[max(0, i - 50):i]))
                    right_avg = float(np.mean(sub[i:min(len(sub), i + 50)]))
                    if abs(left_avg - right_avg) > 0.01:
                        return i
                return None
    return None


def build_frames(
    gap_edges,
    width,
    height,
    is_horizontal=True,
    long_edges=None,
    first_offset=0,
    last_offset=None,
):
    """Build per-frame coordinate dicts from gap edges."""
    frames = []
    n = len(gap_edges)
    if last_offset is None:
        last_offset = width if is_horizontal else height

    for i in range(n + 1):
        if is_horizontal:
            left = first_offset if i == 0 else gap_edges[i - 1][1]
            right = last_offset if i == n else gap_edges[i][0]
            left = max(0, min(left, width - 1))
            right = max(left + 1, min(right, width))
            if long_edges:
                top, bottom = long_edges
            else:
                top, bottom = 0, height
            top = max(0, min(top, height - 1))
            bottom = max(top + 1, min(bottom, height))
            frame_width = right - left
        else:
            top = first_offset if i == 0 else gap_edges[i - 1][1]
            bottom = last_offset if i == n else gap_edges[i][0]
            top = max(0, min(top, height - 1))
            bottom = max(top + 1, min(bottom, height))
            if long_edges:
                left, right = long_edges
            else:
                left, right = 0, width
            left = max(0, min(left, width - 1))
            right = max(left + 1, min(right, width))
            frame_width = bottom - top

        frames.append(
            {
                "index": i + 1,
                "top": top,
                "bottom": bottom,
                "left": left,
                "right": right,
                "relativeTop": round(top / height, 6) if height > 0 else 0.0,
                "relativeBottom": round(bottom / height, 6) if height > 0 else 1.0,
                "relativeLeft": round(left / width, 6) if width > 0 else 0.0,
                "relativeRight": round(right / width, 6) if width > 0 else 1.0,
                "frameWidth": frame_width,
            }
        )
    return frames


def _analyze_single_config(smoothed, scan_size, expected_frames, cleanup_scale):
    """Quick evaluation of one frame-count configuration."""
    valley_bounds = refine_boundaries(
        find_boundaries(smoothed, expected_frames, scan_size, "valley"),
        smoothed,
        expected_frames,
        scan_size,
    )
    valley_edges = gap_edges_from_boundaries(smoothed, valley_bounds, expected_frames, scan_size, "valley", cleanup_scale)
    valley_variance = evaluate_uniformity([0] + [e for pair in valley_edges for e in pair] + [scan_size])

    peak_bounds = refine_boundaries(
        find_boundaries(smoothed, expected_frames, scan_size, "peak"),
        smoothed,
        expected_frames,
        scan_size,
    )
    peak_edges = gap_edges_from_boundaries(smoothed, peak_bounds, expected_frames, scan_size, "peak", cleanup_scale)
    peak_variance = evaluate_uniformity([0] + [e for pair in peak_edges for e in pair] + [scan_size])

    return valley_edges, valley_variance, peak_edges, peak_variance


def _compute_frame_width_cv(edges, scan_size):
    """Coefficient of variation for frame widths; penalises over-segmentation."""
    boundaries = [0]
    for le, re in edges:
        boundaries.append(le)
        boundaries.append(re)
    boundaries.append(scan_size)
    frame_widths = [boundaries[i + 1] - boundaries[i] for i in range(0, len(boundaries) - 1, 2)]
    if not frame_widths or any(w <= 0 for w in frame_widths):
        return float("inf")
    mean_w = np.mean(frame_widths)
    std_w = np.std(frame_widths)
    return std_w / mean_w if mean_w > 0 else float("inf")


def _auto_detect_frames(smoothed, scan_size, cleanup_scale, max_frames=8):
    """Auto-detect best frame count (2..max_frames)."""
    best_frames = 6
    best_score = float("inf")
    best_result = None
    for ef in range(2, max_frames + 1):
        ve, vv, pe, pv = _analyze_single_config(smoothed, scan_size, ef, cleanup_scale)
        chosen_edges, chosen_var = (pe, pv) if pv < vv else (ve, vv)
        fallback_count = sum(1 for le, re in chosen_edges if le == re)
        cv = _compute_frame_width_cv(chosen_edges, scan_size)
        cv_penalty = max(0.0, cv - 0.10) * 2.0
        fallback_penalty = fallback_count * 1.5
        score = chosen_var * (1.0 + cv_penalty + fallback_penalty)
        if score < best_score:
            best_score = score
            best_frames = ef
            best_result = (ve, vv, pe, pv)
    if best_score > 1e8:
        best_frames = 6
    return best_frames, best_result


def analyze_image(image_path: str, expected_frames: int = 6, cleanup_scale: float = 0.5, original_path: str | None = None) -> dict:
    """
    Analyse a scanned film strip and detect frame boundaries.

    Parameters
    ----------
    image_path : str
        Path to the image to analyse (thumbnail or full-res).
    expected_frames : int
        Expected number of frames; 0 triggers auto-detection.
    cleanup_scale : float
        Factor controlling how aggressively gap edges are cleaned.
    original_path : str, optional
        Path to the original full-resolution image.  If the *cross*
        dimension of ``image_path`` is < 2000 px the detector will
        load ``original_path`` for long-edge detection to maintain
        accuracy.

    Returns
    -------
    dict
        Compatible with the legacy ``detect_thumb.py`` JSON output:
        ``frameCount``, ``sourceWidth``, ``sourceHeight``,
        ``frames[]``, ``cropAngle``, ``debug``.
    """
    t0 = time.time()
    mem_before = psutil.Process().memory_info().rss / 1024 / 1024 if HAS_PSUTIL else 0

    arr = _load_image_array(image_path)
    height, width = arr.shape
    is_horizontal = width >= height

    if is_horizontal:
        projection = np.mean(arr, axis=0) / 255.0
    else:
        projection = np.mean(arr, axis=1) / 255.0
    scan_size = width if is_horizontal else height

    base_pstep = scan_size / 6
    window_size = max(5, min(21, int(base_pstep * 0.08)))
    if window_size % 2 == 0:
        window_size += 1
    kernel = np.ones(window_size) / window_size
    padded = np.pad(projection, (window_size // 2, window_size // 2), mode="edge")
    smoothed = np.convolve(padded, kernel, mode="valid")

    auto_detected = False
    if expected_frames <= 0:
        auto_detected = True
        expected_frames, auto_result = _auto_detect_frames(smoothed, scan_size, cleanup_scale)
        valley_edges, valley_variance, peak_edges, peak_variance = auto_result
    else:
        valley_edges, valley_variance, peak_edges, peak_variance = _analyze_single_config(smoothed, scan_size, expected_frames, cleanup_scale)

    if peak_variance < valley_variance:
        chosen_edges = peak_edges
        chosen_mode = "peak"
    else:
        chosen_edges = valley_edges
        chosen_mode = "valley"

    # Long-edge detection — use original if thumbnail resolution is too low
    cross_size = height if is_horizontal else width
    long_edge_arr = arr
    used_original_for_long_edge = False
    if original_path and cross_size < 2000:
        try:
            long_edge_arr = _load_image_array(original_path)
            used_original_for_long_edge = True
        except Exception:
            pass

    long_edges = detect_long_edges(long_edge_arr, is_horizontal, chosen_mode)
    size_for_fallback = height if is_horizontal else width
    if long_edges == (0, size_for_fallback):
        opposite_mode = "peak" if chosen_mode == "valley" else "valley"
        long_edges = detect_long_edges(long_edge_arr, is_horizontal, opposite_mode)

    # Aspect-ratio constrained refinement (replaces symmetric assumption)
    proportional = _detect_long_edges_proportional(
        long_edge_arr, is_horizontal, chosen_edges, aspect_ratio=3 / 2
    )
    if proportional:
        prop_near, prop_far = proportional
        prop_span = prop_far - prop_near
        if long_edges == (0, size_for_fallback):
            long_edges = proportional
        else:
            orig_span = long_edges[1] - long_edges[0]
            min_reasonable = max(20, int(size_for_fallback * 0.05))
            if orig_span < min_reasonable:
                if prop_span >= min_reasonable:
                    long_edges = proportional
            elif abs(orig_span - prop_span) > size_for_fallback * 0.15:
                long_edges = proportional

    # Final sanity: never accept a ridiculously narrow span
    if (long_edges[1] - long_edges[0]) < max(10, int(size_for_fallback * 0.03)):
        long_edges = (0, size_for_fallback)

    if used_original_for_long_edge and long_edge_arr is not arr:
        orig_h, orig_w = long_edge_arr.shape
        scale = height / orig_h if is_horizontal else width / orig_w
        long_edges = (int(long_edges[0] * scale), int(long_edges[1] * scale))

    first_offset = _detect_scan_edge(smoothed, chosen_mode, expected_frames, from_end=False)
    last_offset = _detect_scan_edge(smoothed, chosen_mode, expected_frames, from_end=True)

    frames = build_frames(chosen_edges, width, height, is_horizontal, long_edges, first_offset or 0, last_offset)
    crop_angle = estimate_rotation(arr, expected_frames, width, height, is_horizontal, chosen_mode)

    elapsed = time.time() - t0
    if HAS_PSUTIL:
        mem_after = psutil.Process().memory_info().rss / 1024 / 1024
        print(
            f"[Perf] analyze_image: {elapsed:.2f}s, RAM +{mem_after - mem_before:.1f}MB (total {mem_after:.1f}MB)",
            file=__import__("sys").stderr,
        )
    else:
        print(f"[Perf] analyze_image: {elapsed:.2f}s", file=__import__("sys").stderr)

    debug_info = {
        "imageHeight": height,
        "imageWidth": width,
        "isHorizontal": is_horizontal,
        "gapEdges": chosen_edges,
        "longEdges": long_edges,
        "mode": chosen_mode,
        "valleyVariance": round(valley_variance, 2),
        "peakVariance": round(peak_variance, 2),
    }
    if auto_detected:
        debug_info["autoDetectedFrames"] = expected_frames

    return {
        "frameCount": len(frames),
        "sourceWidth": width,
        "sourceHeight": height,
        "frames": frames,
        "cropAngle": round(crop_angle, 2),
        "debug": debug_info,
    }


if __name__ == "__main__":
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="FilmCrop frame detector")
    parser.add_argument("image_path", help="Path to the image to analyse")
    parser.add_argument("--frames", type=int, default=6, help="Expected number of frames (0=auto)")
    parser.add_argument("--cleanup-scale", type=float, default=0.5, help="Gap cleanup scale factor")
    parser.add_argument("--original", type=str, default=None, help="Path to original full-res image")
    args = parser.parse_args()

    if not Path(args.image_path).exists():
        print(json.dumps({"error": f"file not found: {args.image_path}"}), file=sys.stderr)
        sys.exit(1)

    result = analyze_image(args.image_path, args.frames, args.cleanup_scale, args.original)
    print(json.dumps(result, indent=2, ensure_ascii=False))
