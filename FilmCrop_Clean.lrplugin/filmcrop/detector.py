"""
FilmCrop core detection engine.

Extracted and cleaned from detect_thumb.py v1.5.1.
All image analysis, frame detection, and boundary computation lives here.
"""

import math
import time
from pathlib import Path
from typing import Optional

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


def _find_local_peaks(signal, mode="peak"):
    """Find all local maxima (or minima for valley mode) in a 1D signal.

    Returns a list of indices where the signal has a local extremum.
    These are points that are strictly higher (peak) or lower (valley)
    than both of their immediate neighbours.
    """
    n = len(signal)
    peaks = []
    for i in range(1, n - 1):
        if mode == "peak":
            if signal[i] > signal[i - 1] and signal[i] > signal[i + 1]:
                peaks.append(i)
        else:
            if signal[i] < signal[i - 1] and signal[i] < signal[i + 1]:
                peaks.append(i)
    return peaks


def _local_contrast(signal, idx, mode="peak", radius=120):
    """Score a local peak/valley by blending absolute brightness with prominence.

    Absolute brightness (signal value) is the primary cue for gap detection:
    film gaps are the brightest (peak) or darkest (valley) features in the
    projection.  Prominence (peak − local baseline) breaks ties when two
    peaks have similar brightness.  The 0.25 blending factor gives prominence
    enough weight to suppress frame-content artefacts without letting it
    override genuinely brighter gap candidates.

    Returns a dimensionless score where higher = more gap-like.
    """
    val = float(signal[idx])
    left_baseline = float(np.min(signal[max(0, idx - radius):idx + 1]))
    right_baseline = float(np.min(signal[idx:min(len(signal), idx + radius + 1)]))
    baseline = max(left_baseline, right_baseline)
    if mode == "peak":
        prominence = val - baseline
        return val * (1.0 + prominence * 0.25)
    else:
        prominence = baseline - val
        return (1.0 - val) * (1.0 + prominence * 0.25)


def find_boundaries(arr, expected_frames, size, mode="valley"):
    """Locate frame-gap centres by matching local extrema to expected positions.

    Unlike the previous global-argmax-in-a-huge-window approach, this first
    enumerates *all* local maxima / minima in the smoothed projection, then
    picks the strongest one within a moderate window around each theoretical
    boundary position.  Fallback to a narrow argmax window when no local
    peak is found nearby.
    """
    pstep = size / expected_frames
    # Search half-window: ±25% of a frame distance (was ±45%)
    search_half = max(10, int(pstep * 0.25))
    # Fallback window (used when no local peak is found nearby)
    fallback_half = max(10, int(pstep * 0.15))

    all_peaks = _find_local_peaks(arr, mode)

    boundaries = [0]
    for f in range(1, expected_frames):
        center = int(f * pstep)
        s0 = max(0, center - search_half)
        s1 = min(size, center + search_half + 1)

        if s1 <= s0:
            boundaries.append(center)
            continue

        # 1) Local-peak matching: pick the strongest peak near the expected position
        candidates = [p for p in all_peaks if s0 <= p <= s1]
        if candidates:
            # Combined score: _local_contrast × distance weight.
            # Distance weight is a Gaussian centred on the expected position
            # so peaks closer to the theoretical boundary are preferred.
            sigma = pstep * 0.20
            best_peak = max(
                candidates,
                key=lambda p: _local_contrast(arr, p, mode)
                * math.exp(-0.5 * ((p - center) / sigma) ** 2),
            )
            boundary_pos = min(best_peak, size - 1)
            if boundary_pos <= boundaries[-1]:
                boundary_pos = boundaries[-1] + 1
            boundaries.append(boundary_pos)
            continue

        # 2) Narrow-window argmax fallback (was ±45%, now ±15% of pstep)
        fs0 = max(0, center - fallback_half)
        fs1 = min(size, center + fallback_half + 1)
        if fs1 <= fs0:
            boundaries.append(center)
            continue
        sub = arr[fs0:fs1]
        pos = int(np.argmax(sub)) if mode == "peak" else int(np.argmin(sub))
        boundary_pos = fs0 + pos
        if boundary_pos <= boundaries[-1]:
            boundary_pos = boundaries[-1] + 1
        boundaries.append(min(boundary_pos, size - 1))

    boundaries.append(size)
    return boundaries


def _enforce_boundary_consistency(boundaries, all_peaks, size, expected_frames):
    """Nudge boundaries toward even spacing while staying on local peaks.

    Each boundary is independently detected by ``find_boundaries``, which
    can produce uneven pitches when a bright frame-content feature is
    mistaken for a gap.  This pass adjusts each boundary toward the position
    implied by ``median_pitch × frame_index``, but only if a local peak
    exists within ``±12 %`` of the current pitch.
    """
    if len(boundaries) < 4:
        return boundaries
    pitches = [boundaries[i + 1] - boundaries[i] for i in range(len(boundaries) - 1)]
    median_pitch = float(np.median(pitches))
    peak_set = sorted(all_peaks)  # sorted for deterministic iteration
    search_range = max(20, int(median_pitch * 0.12))
    for i in range(1, len(boundaries) - 1):
        prev = boundaries[i - 1]
        ideal = prev + median_pitch
        current = boundaries[i]
        best = current
        best_dist = abs(current - ideal)
        # Scan local peaks within search_range of the ideal position
        lo = max(prev + 1, ideal - search_range)
        hi = min(size - 1, ideal + search_range)
        for p in peak_set:
            if lo <= p <= hi:
                d = abs(p - ideal)
                if d < best_dist:
                    best_dist = d
                    best = p
        boundaries[i] = best
    # Restore monotonicity
    for i in range(1, len(boundaries)):
        if boundaries[i] <= boundaries[i - 1]:
            boundaries[i] = boundaries[i - 1] + 1
    return boundaries


def refine_boundaries(boundaries, arr, expected_frames, size):
    """Drop weakest boundaries if we have too many.

    NOTE: with the current pipeline (find_boundaries → _enforce_boundary_consistency)
    the boundary count always equals expected_frames + 1, so this function is
    effectively a no-op.  Kept as a safety net in case a future change introduces
    extra boundaries.
    """
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
    """Convert boundary centres into (left_edge, right_edge) gap pairs.

    Uses gradient-based edge detection: from each boundary centre, walk left
    and right tracking the maximum gradient.  The gap edges are placed at the
    steepest transition points — no arbitrary percentile threshold needed.
    """
    pstep = size / expected_frames
    search_r = max(50, int(pstep * 0.06))
    max_gap = int(pstep * 0.12)
    min_hw = max(2, int(pstep * 0.002))

    gap_edges = []
    prev = 0
    for b in boundaries[1:-1]:
        s0 = max(0, b - search_r)
        s1 = min(size, b + search_r)
        sub = arr[s0:s1]

        b_rel = b - s0
        grad = np.abs(np.diff(sub.astype(np.float64)))

        # Dynamic gradient floor: 30 % of the 85th-percentile gradient in the
        # search window.  Lower bound of 1e-4 avoids stalling on ultra-low-
        # contrast scans (e.g. thin-base film where frame content and gap have
        # very similar brightness).
        noise_floor = float(np.percentile(grad, 85))
        grad_threshold = max(noise_floor * 0.30, 0.0001)

        # ---- gradient-based edge detection ----------------------------------
        def _find_edge(from_idx, step):
            """Walk *step* (-1 left, +1 right) from *from_idx*, tracking the
            maximum gradient.  Stop when the gradient falls below 30 % of the
            maximum seen (we've left the transition zone).  Return the position
            of the steepest gradient + 1 (gap-edge pixel index in *sub*)."""
            max_g = 0.0
            best = from_idx
            i = from_idx + step
            min_steps = 3  # walk at least a few pixels before stopping
            steps_taken = 0
            seen_transition = False  # at least one gradient ≥ threshold
            while 0 <= i < len(grad):
                g = grad[i]
                steps_taken += 1
                if g > max_g:
                    max_g = g
                    best = i
                if g >= grad_threshold:
                    seen_transition = True
                # Stop when gradient has decayed well below the peak
                if steps_taken >= min_steps and max_g > 0 and g < max_g * 0.30:
                    break
                # Absolute stop: only allowed after we've crossed a genuine
                # transition (gradient ≥ threshold).  Prevents premature
                # stopping on ultra-low-contrast scans.
                if seen_transition and g < grad_threshold and steps_taken >= min_steps:
                    break
                i += step
            return best + 1  # grad[k] is between sub[k] and sub[k+1]

        left = _find_edge(b_rel, -1)
        right = _find_edge(b_rel, +1)

        # Sanity: clamp so edges don't cross the centre or each other
        left = min(left, b_rel)
        right = max(right, b_rel + 1)

        gap_width = right - left

        # ---- edge-case handling (mirrors original) --------------------------
        if left == 0 or right >= len(sub):
            # Gradient search hit the search-window boundary.
            if gap_width > max_gap:
                gap_edges.append((b, b))
                prev = b
                continue
            # Conservative fallback with the same soft floor as the normal path
            hw = max(min_hw * 2, int(pstep * 0.006))
            le = max(prev + 1, b - hw)
            re = max(le + 1, b + hw)
            gap_edges.append((le, re))
            prev = re
            continue

        # ---- local gradient polish (narrow ±8 px search) --------------------
        local_r = 8

        def _refine_edge(idx, direction):
            if direction == -1:
                start = max(0, idx - local_r)
                end = min(len(grad), idx)
            else:
                start = max(0, idx)
                end = min(len(grad), idx + local_r)
            if end <= start:
                return idx
            sub_grad = grad[start:end]
            offset = int(np.argmax(sub_grad))
            return start + offset + 1

        refined_left = _refine_edge(left, -1)
        refined_right = _refine_edge(right, +1)
        refined_left = min(refined_left, b_rel)
        refined_right = max(refined_right, b_rel)

        # ---- compute final gap edges ----------------------------------------
        min_dist = min(b_rel - refined_left, refined_right - b_rel)
        hw = int(min_dist * cleanup_scale)
        # Soft floor – ensure ~3 px visibility in a typical Lightroom
        # thumbnail (long edge ≈ 1 500 px).  pstep * 0.006 ≈ 0.6 % of a
        # frame height, which maps to ≈ 3 thumbnail pixels.
        soft_floor = max(min_hw * 2, int(pstep * 0.006))
        hw = max(soft_floor, hw)
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

    def _pick_best(threshold_val, content_val, full_size):
        """当 threshold 法与 content_ref 法差异很大时，优先使用 threshold 法（更可靠）。"""
        if threshold_val is not None and content_val is not None:
            if abs(content_val - threshold_val) < full_size * 0.10:
                return max(threshold_val, content_val)
            return threshold_val
        if threshold_val is not None:
            return threshold_val
        if content_val is not None:
            return content_val
        return None

    near_candidates = []
    far_candidates = []
    for m in ("valley", "peak"):
        near_t = _find_margin_threshold(smoothed[:search_len], size, m)
        near_c = _find_margin_content_ref(smoothed[:search_len], content_ref)
        near_best = _pick_best(near_t, near_c, size)
        if near_best is not None and near_best > 0:
            near_candidates.append(near_best)

        right_slice = smoothed[-search_len:][::-1]
        far_t = _find_margin_threshold(right_slice, size, m)
        far_c = _find_margin_content_ref(right_slice, content_ref)
        far_best = _pick_best(far_t, far_c, size)
        if far_best is not None and far_best > 0:
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

    height, width = arr.shape
    scan_size = width if is_horizontal else height
    cross_size = height if is_horizontal else width

    if is_horizontal:
        projection = np.mean(arr, axis=1) / 255.0
    else:
        projection = np.mean(arr, axis=0) / 255.0

    size = len(projection)  # cross_size

    # Compute median frame dimension along scan direction
    frame_dims = []
    prev = 0
    for le, re in chosen_edges:
        frame_dims.append(le - prev)
        prev = re
    frame_dims.append(scan_size - prev)

    median_dim = float(np.median(frame_dims))
    if median_dim <= 0:
        return None

    target = int(round(median_dim / aspect_ratio))
    if target < 3:
        return None
    if target > size:
        # Theoretical span wider than image — use full image width
        return int(0), int(size - 1)

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


def _refine_long_edges(
    arr,
    is_horizontal,
    chosen_edges,
    prev_long_edges,
    aspect_ratio=3 / 2,
    search_margin=50,
):
    """Refine long-edge boundaries using gap-driven aspect-ratio constraint.

    The idea: gap detection (top/bottom) is more reliable than long-edge
    detection (left/right) because frame gaps have strong brightness contrast.
    We use the median frame height from gap analysis to compute a theoretical
    frame width, then search for the steepest gradient near the previously
    detected edge positions within a small ±search_margin window.

    If the refined result deviates from the theoretical span by >50%,
    we fall back to prev_long_edges.
    """
    if not chosen_edges or prev_long_edges == (0, 0):
        return prev_long_edges

    height, width = arr.shape
    scan_size = width if is_horizontal else height
    cross_size = height if is_horizontal else width

    # 1. Median frame dimension along scan direction
    frame_dims = []
    prev = 0
    for le, re in chosen_edges:
        frame_dims.append(le - prev)
        prev = re
    frame_dims.append(scan_size - prev)
    median_dim = float(np.median(frame_dims))
    if median_dim <= 0:
        return prev_long_edges

    # 2. Theoretical span along cross direction
    target_span = int(round(median_dim / aspect_ratio))

    # 3. Cross-axis projection
    if is_horizontal:
        proj = np.mean(arr, axis=1) / 255.0
    else:
        proj = np.mean(arr, axis=0) / 255.0

    # Light smoothing
    ksize = max(3, cross_size // 400)
    if ksize % 2 == 0:
        ksize += 1
    kernel = np.ones(ksize) / ksize
    padded = np.pad(proj, (ksize // 2, ksize // 2), mode="edge")
    smoothed = np.convolve(padded, kernel, mode="valid")

    # 4. Local gradient search
    def _search_local(prev_pos):
        s0 = max(0, prev_pos - search_margin)
        s1 = min(len(smoothed), prev_pos + search_margin + 1)
        if s1 <= s0 + 1:
            return prev_pos
        sub = smoothed[s0:s1]

        # Compute gradient
        grad = np.diff(sub)
        if len(grad) < 1:
            return prev_pos

        # Smooth gradient to reduce noise
        g_ksize = min(5, max(3, len(grad) // 10))
        if g_ksize % 2 == 0:
            g_ksize += 1
        if len(grad) >= g_ksize:
            g_kernel = np.ones(g_ksize) / g_ksize
            g_padded = np.pad(grad, (g_ksize // 2, g_ksize // 2), mode="edge")
            smooth_grad = np.convolve(g_padded, g_kernel, mode="valid")[: len(grad)]
        else:
            smooth_grad = grad

        # Find steepest transition (largest absolute gradient)
        pos = int(np.argmax(np.abs(smooth_grad)))
        return s0 + pos

    prev_near, prev_far = prev_long_edges
    near = _search_local(prev_near)
    far = _search_local(prev_far)

    # 5. Don't make the aspect ratio worse than the input
    old_span = prev_far - prev_near
    old_dev = abs(old_span - target_span)
    new_span = far - near
    new_dev = abs(new_span - target_span)
    if new_dev > old_dev:
        return prev_long_edges

    if far <= near:
        return prev_long_edges
    actual_span = far - near
    if actual_span < target_span * 0.5 or actual_span > target_span * 1.5:
        return prev_long_edges

    # 防止 refine 大幅偏离 preliminary 结果（±20px 或 5% 理论帧宽）
    max_shift = max(20, int(target_span * 0.05))
    if abs(near - prev_near) > max_shift or abs(far - prev_far) > max_shift:
        return prev_long_edges

    # 防止 refine 把边界推到图像边缘（可能包含扫描黑边/白边）
    edge_margin = max(3, int(cross_size * 0.005))
    if (prev_near >= edge_margin and near < edge_margin) or \
       (prev_far <= cross_size - edge_margin and far > cross_size - edge_margin):
        return prev_long_edges

    return int(near), int(far)


def _detect_scan_edge(proj, mode="peak", expected_frames=6, from_end=False):
    """Detect scan-edge / sprocket-area before first or after last frame.

    Uses gradient-based detection for sharp flat borders, with a brightness-
    percentile fallback for gradual vignetting at the film edge.
    """
    scan_size = len(proj)
    pstep = scan_size / expected_frames
    search_end = max(30, int(scan_size * 0.05), int(pstep * 0.2))

    if from_end:
        sub = proj[-search_end:]
    else:
        sub = proj[:search_end]

    if len(sub) < 5:
        return None

    # Compute brightness gradient
    grad = np.abs(np.diff(sub))

    # Dynamic threshold: 1.5x median gradient, floor at 0.002
    noise_floor = float(np.percentile(grad, 50))
    threshold = max(noise_floor * 1.5, 0.002)

    # Maximum reasonable border width (5% of scan size)
    max_border = max(5, int(scan_size * 0.05))

    def _has_significant_gradient(idx):
        """Require at least 2 neighbouring points above threshold (denoising)."""
        if grad[idx] <= threshold:
            return False
        neighbours = 1
        for j in (idx - 1, idx + 1):
            if 0 <= j < len(grad) and grad[j] > threshold:
                neighbours += 1
        return neighbours >= 2

    pos = None
    if from_end:
        for i in range(len(grad) - 1, -1, -1):
            if _has_significant_gradient(i):
                pos = scan_size - search_end + i + 1
                border_width = scan_size - pos
                if border_width > max_border:
                    pos = None
                break
    else:
        for i in range(len(grad)):
            if _has_significant_gradient(i):
                if i + 1 > max_border:
                    pos = None
                else:
                    pos = i + 1
                break

    # Verify border flatness (gradient method succeeds only on truly flat borders)
    if pos is not None:
        if from_end:
            border = proj[pos:]
        else:
            border = proj[:pos]
        mid_start = min(search_end, int(scan_size * 0.2))
        mid_end = max(scan_size - search_end, int(scan_size * 0.8))
        if mid_end > mid_start:
            mid_std = float(np.std(proj[mid_start:mid_end]))
            mid_mean = float(np.median(proj[mid_start:mid_end]))
        else:
            mid_std = 0.01
            mid_mean = 0.3
        border_std = float(np.std(border)) if len(border) > 1 else 0.0
        border_len = len(border)
        border_mean = float(np.mean(border)) if border_len > 0 else mid_mean
        # Standard flatness for long borders
        if border_len >= 10 and border_std < mid_std * 0.5:
            return pos
        # Short borders at image edge are common; accept if reasonably flat and dark
        if 3 <= border_len < 10 and border_std < mid_std * 0.8 and border_mean < mid_mean * 0.5:
            return pos
        if border_len < 3 and border_mean < mid_mean * 0.5:
            return pos
        # Bright-edge scan (overexposed scanner edge) — common on film strips scanned flush
        if border_mean > mid_mean * 1.15 and border_std < mid_std * 0.5:
            # Extend cut to where brightness normalises (drops below 1.1x mid_mean)
            search_limit = min(100, search_end)
            if from_end:
                # Search inward from pos toward scan_size - search_limit
                for i in range(pos, max(scan_size - search_limit, pos - search_limit), -1):
                    if proj[i] < mid_mean * 1.1:
                        return i
                return scan_size - search_limit
            else:
                for i in range(pos, search_limit):
                    if proj[i] < mid_mean * 1.1:
                        return i
                return search_limit
        pos = None  # gradient result rejected, will fallback

    # Fallback: brightness percentile (handles gradual vignetting)
    mid_start = min(search_end, int(scan_size * 0.2))
    mid_end = max(scan_size - search_end, int(scan_size * 0.8))
    if mid_end > mid_start:
        content_p5 = float(np.percentile(proj[mid_start:mid_end], 5))
    else:
        content_p5 = 0.05

    if from_end:
        for i in range(scan_size - 1, -1, -1):
            if proj[i] > content_p5:
                return i + 1
    else:
        for i in range(scan_size):
            if proj[i] > content_p5:
                return i
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
            if long_edges is not None and long_edges != (0, 0):
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
            if long_edges is not None and long_edges != (0, 0):
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


def _validate_gap_shape(proj, boundaries, mode="peak", check_radius=40):
    """Score how well the boundary positions match the expected gap shape.

    In *peak* mode a real film gap is a bright stripe flanked by darker
    frame content, so the projection at the boundary centre should be
    higher than its local neighbourhood.  In *valley* mode the opposite
    holds.  Returns a positive score (higher = better match); negative
    values indicate anti-correlation (the opposite mode is a better fit).
    """
    if len(boundaries) < 3:
        return 0.0
    scores = []
    for b in boundaries[1:-1]:
        s0 = max(0, b - check_radius)
        s1 = min(len(proj), b + check_radius)
        local = proj[s0:s1]
        if len(local) < 5:
            continue
        mid = len(local) // 2
        left_mean = float(np.mean(local[:mid]))
        right_mean = float(np.mean(local[mid:]))
        centre_mean = float(np.mean(local[mid - 3:mid + 3]))
        if mode == "peak":
            # Centre should be brighter than both sides
            scores.append(centre_mean - max(left_mean, right_mean))
        else:
            # Centre should be darker than both sides
            scores.append(min(left_mean, right_mean) - centre_mean)
    return float(np.mean(scores)) if scores else 0.0


def _analyze_single_config(smoothed, scan_size, expected_frames, cleanup_scale):
    """Quick evaluation of one frame-count configuration."""
    # Valley path
    valley_peaks = _find_local_peaks(smoothed, "valley")
    valley_bounds_raw = find_boundaries(smoothed, expected_frames, scan_size, "valley")
    valley_bounds = refine_boundaries(
        _enforce_boundary_consistency(valley_bounds_raw, valley_peaks, scan_size, expected_frames),
        smoothed, expected_frames, scan_size,
    )
    valley_edges = gap_edges_from_boundaries(smoothed, valley_bounds, expected_frames, scan_size, "valley", cleanup_scale)
    valley_variance = evaluate_uniformity([0] + [e for pair in valley_edges for e in pair] + [scan_size])

    # Peak path
    peak_peaks = _find_local_peaks(smoothed, "peak")
    peak_bounds_raw = find_boundaries(smoothed, expected_frames, scan_size, "peak")
    peak_bounds = refine_boundaries(
        _enforce_boundary_consistency(peak_bounds_raw, peak_peaks, scan_size, expected_frames),
        smoothed, expected_frames, scan_size,
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
        # Prefer the mode whose gap shape better matches the data
        peak_shape = _validate_gap_shape(smoothed, [0] + [(le + re) // 2 for le, re in pe] + [scan_size], "peak")
        valley_shape = _validate_gap_shape(smoothed, [0] + [(le + re) // 2 for le, re in ve] + [scan_size], "valley")
        if peak_shape > 0 and valley_shape <= 0:
            chosen_edges, chosen_var = pe, pv
        elif valley_shape > 0 and peak_shape <= 0:
            chosen_edges, chosen_var = ve, vv
        elif pv < vv:
            chosen_edges, chosen_var = pe, pv
        else:
            chosen_edges, chosen_var = ve, vv
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


def analyze_image(image_path: str, expected_frames: int = 6, cleanup_scale: float = 0.5, original_path: Optional[str] = None, aspect_ratio: float = 3 / 2) -> dict:
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
        Path to the original full-resolution image.  When provided,
        the detector will always load ``original_path`` and run all
        detection (projection, gap, long-edge, scan-edge) on the
        original pixels for maximum accuracy.  Coordinates are then
        scaled back to thumbnail space before being returned.

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
    thumb_h, thumb_w = arr.shape
    is_horizontal = thumb_w >= thumb_h

    # ------------------------------------------------------------------
    # Always run detection on the original image when available
    # ------------------------------------------------------------------
    cross_size = thumb_h if is_horizontal else thumb_w
    orig_arr = arr
    orig_h, orig_w = thumb_h, thumb_w

    if original_path:
        try:
            orig_arr = _load_image_array(original_path)
            orig_h, orig_w = orig_arr.shape
        except Exception:
            pass

    # Scale factors for converting original coordinates back to thumbnail
    scale_h = thumb_h / orig_h
    scale_w = thumb_w / orig_w
    scan_scale = scale_w if is_horizontal else scale_h
    cross_scale = scale_h if is_horizontal else scale_w

    # ------------------------------------------------------------------
    # All detection runs on orig_arr (higher resolution when available)
    # ------------------------------------------------------------------
    if is_horizontal:
        orig_projection = np.mean(orig_arr, axis=0) / 255.0
    else:
        orig_projection = np.mean(orig_arr, axis=1) / 255.0
    orig_scan_size = len(orig_projection)

    base_pstep = orig_scan_size / max(expected_frames if expected_frames > 0 else 6, 1)
    window_size = max(5, min(21, int(base_pstep * 0.08)))
    if window_size % 2 == 0:
        window_size += 1
    kernel = np.ones(window_size) / window_size
    padded = np.pad(orig_projection, (window_size // 2, window_size // 2), mode="edge")
    orig_smoothed = np.convolve(padded, kernel, mode="valid")

    auto_detected = False
    if expected_frames <= 0:
        auto_detected = True
        expected_frames, auto_result = _auto_detect_frames(orig_smoothed, orig_scan_size, cleanup_scale)
        valley_edges, valley_variance, peak_edges, peak_variance = auto_result
    else:
        valley_edges, valley_variance, peak_edges, peak_variance = _analyze_single_config(
            orig_smoothed, orig_scan_size, expected_frames, cleanup_scale
        )

    # ---- mode selection: prefer the mode whose gap shape matches the data ----
    peak_shape = _validate_gap_shape(orig_smoothed, [0] + [(le + re) // 2 for le, re in peak_edges] + [orig_scan_size], "peak")
    valley_shape = _validate_gap_shape(orig_smoothed, [0] + [(le + re) // 2 for le, re in valley_edges] + [orig_scan_size], "valley")

    # Strong shape preference: if one mode has positive shape score and the
    # other is negative, shape wins over variance.
    if peak_shape > 0 and valley_shape <= 0:
        orig_chosen_edges = peak_edges
        chosen_mode = "peak"
    elif valley_shape > 0 and peak_shape <= 0:
        orig_chosen_edges = valley_edges
        chosen_mode = "valley"
    elif peak_variance < valley_variance:
        orig_chosen_edges = peak_edges
        chosen_mode = "peak"
    else:
        orig_chosen_edges = valley_edges
        chosen_mode = "valley"

    # Long-edge detection on original image
    orig_long_edges = detect_long_edges(orig_arr, is_horizontal, chosen_mode)
    orig_cross_size = orig_w if not is_horizontal else orig_h
    if orig_long_edges == (0, orig_cross_size):
        opposite_mode = "peak" if chosen_mode == "valley" else "valley"
        orig_long_edges = detect_long_edges(orig_arr, is_horizontal, opposite_mode)

    # Aspect-ratio constrained refinement on original image
    orig_proportional = _detect_long_edges_proportional(
        orig_arr, is_horizontal, orig_chosen_edges, aspect_ratio=3 / 2
    )
    if orig_proportional:
        prop_near, prop_far = orig_proportional
        prop_span = prop_far - prop_near
        orig_span = orig_long_edges[1] - orig_long_edges[0]
        min_reasonable = max(20, int(orig_cross_size * 0.05))

        # Prefer the proportional result (gap-driven, more reliable) whenever
        # it produces a reasonable span — unless it would aggressively crop
        # valid content that the direct detector saw.
        if prop_span >= min_reasonable:
            if orig_long_edges == (0, orig_cross_size):
                # Direct detection failed entirely — use proportional
                orig_long_edges = orig_proportional
            elif prop_span >= orig_span * 0.92:
                # Proportional agrees with direct (within 8 %) — use the
                # gap-driven result for precision
                orig_long_edges = orig_proportional
        elif orig_long_edges == (0, orig_cross_size) and prop_span > 0:
            # Last resort: even a short proportional result beats nothing
            orig_long_edges = orig_proportional

    # Final sanity on original coordinates
    if (orig_long_edges[1] - orig_long_edges[0]) < max(10, int(orig_cross_size * 0.03)):
        orig_long_edges = (0, orig_cross_size)

    # Refine on original image
    orig_prev_long_edges = orig_long_edges
    refined = _refine_long_edges(
        orig_arr, is_horizontal, orig_chosen_edges, orig_prev_long_edges,
        aspect_ratio=3 / 2, search_margin=50,
    )
    orig_long_edges = refined if refined else orig_prev_long_edges

    # Scan-edge detection on original image projection (use unsmoothed for sharper edges)
    first_offset_raw = _detect_scan_edge(orig_projection, chosen_mode, expected_frames, from_end=False)
    last_offset_raw = _detect_scan_edge(orig_projection, chosen_mode, expected_frames, from_end=True)

    # ------------------------------------------------------------------
    # Scale all original coordinates back to thumbnail space
    # ------------------------------------------------------------------
    def _scale_edges(edges, s):
        return [(int(le * s), int(re * s)) for le, re in edges]

    chosen_edges = _scale_edges(orig_chosen_edges, scan_scale)
    long_edges = (int(orig_long_edges[0] * cross_scale), int(orig_long_edges[1] * cross_scale))
    prev_long_edges = (int(orig_prev_long_edges[0] * cross_scale), int(orig_prev_long_edges[1] * cross_scale))
    first_offset = int(first_offset_raw * scan_scale) if first_offset_raw is not None else 0
    last_offset = int(last_offset_raw * scan_scale) if last_offset_raw is not None else None

    # Build frames using thumbnail dimensions so relative coords match Lightroom
    frames = build_frames(chosen_edges, thumb_w, thumb_h, is_horizontal, long_edges, first_offset, last_offset)

    # Override relative coordinates with original-image precision.
    # Absolute coords stay in thumbnail space for debug/visualization compatibility.
    n = len(frames) - 1
    for i, frame in enumerate(frames):
        if is_horizontal:
            orig_left = first_offset_raw if (i == 0 and first_offset_raw is not None) else (
                orig_chosen_edges[i - 1][1] if i > 0 else 0
            )
            orig_right = last_offset_raw if (i == n and last_offset_raw is not None) else (
                orig_chosen_edges[i][0] if i < n else orig_w
            )
            orig_top, orig_bottom = orig_long_edges
        else:
            orig_top = first_offset_raw if (i == 0 and first_offset_raw is not None) else (
                orig_chosen_edges[i - 1][1] if i > 0 else 0
            )
            orig_bottom = last_offset_raw if (i == n and last_offset_raw is not None) else (
                orig_chosen_edges[i][0] if i < n else orig_h
            )
            orig_left, orig_right = orig_long_edges
        frame["relativeTop"] = round(orig_top / orig_h, 6) if orig_h > 0 else 0.0
        frame["relativeBottom"] = round(orig_bottom / orig_h, 6) if orig_h > 0 else 1.0
        frame["relativeLeft"] = round(orig_left / orig_w, 6) if orig_w > 0 else 0.0
        frame["relativeRight"] = round(orig_right / orig_w, 6) if orig_w > 0 else 1.0

    # --- Enforce strict 3:2 / 2:3 aspect ratio on MIDDLE frames only ---
    # First and last frames may be truncated by scan edges; we only force
    # exact ratio on the complete middle frames.
    if aspect_ratio and len(frames) > 0:
        n = len(frames) - 1

        # Collect scan-direction dimensions for MIDDLE frames only (index 1..n-1)
        middle_scan_dims = []
        for i in range(1, n):
            if is_horizontal:
                left_b = first_offset_raw if (i == 0 and first_offset_raw is not None) else (
                    orig_chosen_edges[i - 1][1] if i > 0 else 0
                )
                right_b = last_offset_raw if (i == n and last_offset_raw is not None) else (
                    orig_chosen_edges[i][0] if i < n else orig_w
                )
                middle_scan_dims.append(right_b - left_b)
            else:
                top_b = first_offset_raw if (i == 0 and first_offset_raw is not None) else (
                    orig_chosen_edges[i - 1][1] if i > 0 else 0
                )
                bottom_b = last_offset_raw if (i == n and last_offset_raw is not None) else (
                    orig_chosen_edges[i][0] if i < n else orig_h
                )
                middle_scan_dims.append(bottom_b - top_b)

        if middle_scan_dims:
            unified_scan_dim = int(np.median(middle_scan_dims))
        else:
            # Fallback: only 2 frames, compute from available frames
            all_scan_dims = []
            for i in range(len(frames)):
                if is_horizontal:
                    left_b = first_offset_raw if (i == 0 and first_offset_raw is not None) else (
                        orig_chosen_edges[i - 1][1] if i > 0 else 0
                    )
                    right_b = last_offset_raw if (i == n and last_offset_raw is not None) else (
                        orig_chosen_edges[i][0] if i < n else orig_w
                    )
                    all_scan_dims.append(right_b - left_b)
                else:
                    top_b = first_offset_raw if (i == 0 and first_offset_raw is not None) else (
                        orig_chosen_edges[i - 1][1] if i > 0 else 0
                    )
                    bottom_b = last_offset_raw if (i == n and last_offset_raw is not None) else (
                        orig_chosen_edges[i][0] if i < n else orig_h
                    )
                    all_scan_dims.append(bottom_b - top_b)
            unified_scan_dim = int(np.median(all_scan_dims)) if all_scan_dims else 0

        unified_cross_dim = int(round(unified_scan_dim / aspect_ratio))

        # If image doesn't have enough cross-space, shrink scan-dim to fit
        if unified_cross_dim > orig_cross_size:
            unified_cross_dim = orig_cross_size
            unified_scan_dim = int(round(unified_cross_dim * aspect_ratio))

        # Recenter long edges to exact unified cross-dimension
        curr_near, curr_far = orig_long_edges
        center = (curr_near + curr_far) // 2
        new_near = max(0, center - unified_cross_dim // 2)
        new_far = min(orig_cross_size, new_near + unified_cross_dim)
        if new_far > orig_cross_size:
            new_far = orig_cross_size
            new_near = max(0, new_far - unified_cross_dim)
        orig_long_edges = (new_near, new_far)

        # Rebuild MIDDLE frames with unified dimensions
        for i, fr in enumerate(frames):
            is_middle = (0 < i < n)
            if not is_middle:
                # First / last frame: keep original scan dim, but use unified width
                # (do NOT shrink width when height is truncated)
                if is_horizontal:
                    left_b = first_offset_raw if (i == 0 and first_offset_raw is not None) else (
                        orig_chosen_edges[i - 1][1] if i > 0 else 0
                    )
                    right_b = last_offset_raw if (i == n and last_offset_raw is not None) else (
                        orig_chosen_edges[i][0] if i < n else orig_w
                    )
                    new_left = max(0, left_b)
                    new_right = min(orig_w, right_b)
                    fr["left"] = int(new_left * scan_scale)
                    fr["right"] = int(new_right * scan_scale)
                    fr["top"] = int(orig_long_edges[0] * cross_scale)
                    fr["bottom"] = int(orig_long_edges[1] * cross_scale)
                    fr["relativeLeft"] = round(new_left / orig_w, 6) if orig_w > 0 else 0.0
                    fr["relativeRight"] = round(new_right / orig_w, 6) if orig_w > 0 else 1.0
                    fr["relativeTop"] = round(orig_long_edges[0] / orig_h, 6) if orig_h > 0 else 0.0
                    fr["relativeBottom"] = round(orig_long_edges[1] / orig_h, 6) if orig_h > 0 else 1.0
                    fr["frameWidth"] = new_right - new_left
                else:
                    top_b = first_offset_raw if (i == 0 and first_offset_raw is not None) else (
                        orig_chosen_edges[i - 1][1] if i > 0 else 0
                    )
                    bottom_b = last_offset_raw if (i == n and last_offset_raw is not None) else (
                        orig_chosen_edges[i][0] if i < n else orig_h
                    )
                    new_top = max(0, top_b)
                    new_bottom = min(orig_h, bottom_b)
                    fr["top"] = int(new_top * scan_scale)
                    fr["bottom"] = int(new_bottom * scan_scale)
                    fr["left"] = int(orig_long_edges[0] * cross_scale)
                    fr["right"] = int(orig_long_edges[1] * cross_scale)
                    fr["relativeTop"] = round(new_top / orig_h, 6) if orig_h > 0 else 0.0
                    fr["relativeBottom"] = round(new_bottom / orig_h, 6) if orig_h > 0 else 1.0
                    fr["relativeLeft"] = round(orig_long_edges[0] / orig_w, 6) if orig_w > 0 else 0.0
                    fr["relativeRight"] = round(orig_long_edges[1] / orig_w, 6) if orig_w > 0 else 1.0
                    fr["frameWidth"] = new_bottom - new_top
                continue

            if is_horizontal:
                left_b = first_offset_raw if (i == 0 and first_offset_raw is not None) else (
                    orig_chosen_edges[i - 1][1] if i > 0 else 0
                )
                right_b = last_offset_raw if (i == n and last_offset_raw is not None) else (
                    orig_chosen_edges[i][0] if i < n else orig_w
                )
                center_scan = (left_b + right_b) // 2
                new_left = max(0, center_scan - unified_scan_dim // 2)
                new_right = min(orig_w, new_left + unified_scan_dim)
                if new_right > orig_w:
                    new_right = orig_w
                    new_left = max(0, new_right - unified_scan_dim)

                fr["left"] = int(new_left * scan_scale)
                fr["right"] = int(new_right * scan_scale)
                fr["top"] = int(orig_long_edges[0] * cross_scale)
                fr["bottom"] = int(orig_long_edges[1] * cross_scale)
                fr["relativeLeft"] = round(new_left / orig_w, 6) if orig_w > 0 else 0.0
                fr["relativeRight"] = round(new_right / orig_w, 6) if orig_w > 0 else 1.0
                fr["relativeTop"] = round(orig_long_edges[0] / orig_h, 6) if orig_h > 0 else 0.0
                fr["relativeBottom"] = round(orig_long_edges[1] / orig_h, 6) if orig_h > 0 else 1.0
                fr["frameWidth"] = new_right - new_left
            else:
                top_b = first_offset_raw if (i == 0 and first_offset_raw is not None) else (
                    orig_chosen_edges[i - 1][1] if i > 0 else 0
                )
                bottom_b = last_offset_raw if (i == n and last_offset_raw is not None) else (
                    orig_chosen_edges[i][0] if i < n else orig_h
                )
                center_scan = (top_b + bottom_b) // 2
                new_top = max(0, center_scan - unified_scan_dim // 2)
                new_bottom = min(orig_h, new_top + unified_scan_dim)
                if new_bottom > orig_h:
                    new_bottom = orig_h
                    new_top = max(0, new_bottom - unified_scan_dim)

                fr["top"] = int(new_top * scan_scale)
                fr["bottom"] = int(new_bottom * scan_scale)
                fr["left"] = int(orig_long_edges[0] * cross_scale)
                fr["right"] = int(orig_long_edges[1] * cross_scale)
                fr["relativeTop"] = round(new_top / orig_h, 6) if orig_h > 0 else 0.0
                fr["relativeBottom"] = round(new_bottom / orig_h, 6) if orig_h > 0 else 1.0
                fr["relativeLeft"] = round(orig_long_edges[0] / orig_w, 6) if orig_w > 0 else 0.0
                fr["relativeRight"] = round(orig_long_edges[1] / orig_w, 6) if orig_w > 0 else 1.0
                fr["frameWidth"] = new_bottom - new_top

        # Update thumbnail-space long edges for debug output
        long_edges = (int(orig_long_edges[0] * cross_scale), int(orig_long_edges[1] * cross_scale))

    crop_angle = estimate_rotation(orig_arr, expected_frames, orig_w, orig_h, is_horizontal, chosen_mode)

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
        "imageHeight": thumb_h,
        "imageWidth": thumb_w,
        "isHorizontal": is_horizontal,
        "usedOriginalForLongEdge": original_path is not None,
        "gapEdges": chosen_edges,
        "longEdges": long_edges,
        "prevLongEdges": prev_long_edges,
        "mode": chosen_mode,
        "valleyVariance": round(valley_variance, 2),
        "peakVariance": round(peak_variance, 2),
    }
    if auto_detected:
        debug_info["autoDetectedFrames"] = expected_frames

    return {
        "frameCount": len(frames),
        "sourceWidth": thumb_w,
        "sourceHeight": thumb_h,
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
