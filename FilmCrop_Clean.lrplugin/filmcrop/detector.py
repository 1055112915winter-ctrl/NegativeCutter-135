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



def _load_image_array(path: str, contrast_enhance: bool = True) -> np.ndarray:
    """Load image as grayscale uint8 ndarray, handling 16-bit TIFF.

    With ``contrast_enhance=True`` (default), apply a percentile-based
    contrast stretch (1 % / 99 %) to the grayscale array. Hot pixels and
    dust spots otherwise compress the dynamic range; stretching the 1–99
    band to [0, 255] keeps gap peaks / valleys separable from frame
    content, which is the dominant cue for boundary detection. Percentiles
    are estimated on a stride-8 subsample for speed (~50 ms vs ~2 s on a
    200 MP scan); the stretch itself is applied to the full array.
    """
    img: Image.Image = Image.open(path)
    if img.mode in ("I;16", "I;16B", "I;16N", "I"):
        arr_16 = np.array(img)
        arr = ((arr_16.astype(np.float32) / 65535.0) * 255).astype(np.uint8)
    elif img.mode != "L":
        img = img.convert("L")
        arr = np.array(img)
    else:
        arr = np.array(img)

    if contrast_enhance and arr.size > 0 and arr.ndim == 2:
        sub = arr[::8, ::8]
        if sub.size > 0:
            p_lo, p_hi = np.percentile(sub, [1, 99])
            p_lo, p_hi = float(p_lo), float(p_hi)
            # Require non-trivial dynamic range (>1/255) before stretching, so
            # a near-uniform image is left untouched rather than amplifying
            # numerical noise.
            if p_hi - p_lo > 1.0:
                arr = np.clip(
                    (arr.astype(np.float32) - p_lo) * (255.0 / (p_hi - p_lo)),
                    0.0,
                    255.0,
                ).astype(np.uint8)

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

    Plateau-walk: from each boundary centre, walk outward while the signal
    stays inside the gap "plateau" (very bright = film base, or very dark =
    developed mask). The gap edge is placed at the FIRST sample whose value
    has moved a fraction ``drop_frac`` of the way from plateau toward content
    — i.e. once we are firmly past the plateau-to-content transition.

    Robustness notes:
    * Plateau direction is inferred from the data (local-vs-percentile), not
      from the ``mode`` argument, because mode selection is variance-based and
      sometimes mismatches the actual gap polarity (e.g. mostly-bright gaps
      with a couple of darker outliers).
    * ``search_r`` is generous (≈30 % of the per-frame step) so the search
      window almost always encloses both gap and adjacent frame content,
      keeping content_ref away from the plateau and avoiding stuck walks.
    * When one walk hits the window edge, the half it found is mirrored to
      the other side (symmetric fallback) — better than a fixed ``soft_floor``
      because it preserves the actual gap width on the side we trust.
    """
    pstep = size / expected_frames
    search_r = max(200, int(pstep * 0.30))
    max_gap = int(pstep * 0.10)  # implausibly wide — gap > 10 % of frame step
    min_hw = max(2, int(pstep * 0.002))
    soft_floor = max(min_hw * 2, int(pstep * 0.004))
    drop_frac = 0.15
    min_range = 0.10  # plateau-vs-content contrast floor; below this we can't
                       # tell plateau from noise → fall back to soft_floor

    gap_edges = []
    prev = 0
    for b in boundaries[1:-1]:
        s0 = max(0, b - search_r)
        s1 = min(size, b + search_r)
        sub = arr[s0:s1]
        n_sub = len(sub)
        if n_sub < 8:
            le = max(prev + 1, b - soft_floor)
            re = max(le + 1, b + soft_floor)
            gap_edges.append((le, re))
            prev = re
            continue

        b_rel = max(0, min(n_sub - 1, b - s0))

        # ---- local plateau anchor + content references ------------------
        local_r = min(20, n_sub // 4)
        ls = max(0, b_rel - local_r)
        le_idx = min(n_sub, b_rel + local_r + 1)
        local_region = sub[ls:le_idx]
        local_mean = float(np.mean(local_region))
        sub_low = float(np.percentile(sub, 10))
        sub_high = float(np.percentile(sub, 90))

        # Infer plateau direction from data; fall back to ``mode`` when the
        # difference is too small to tell.
        if abs(local_mean - sub_high) < abs(local_mean - sub_low) - 0.01:
            polarity = "peak"
        elif abs(local_mean - sub_low) < abs(local_mean - sub_high) - 0.01:
            polarity = "valley"
        else:
            polarity = mode

        if polarity == "peak":
            plateau_val = float(np.max(local_region))
            content_ref = sub_low
            range_ = max(plateau_val - content_ref, 1e-3)
            out_threshold = plateau_val - range_ * drop_frac

            def in_plateau(v):  # type: ignore
                return v >= out_threshold
        else:
            plateau_val = float(np.min(local_region))
            content_ref = sub_high
            range_ = max(content_ref - plateau_val, 1e-3)
            out_threshold = plateau_val + range_ * drop_frac

            def in_plateau(v):  # type: ignore
                return v <= out_threshold

        # ---- low-contrast fallback: no real plateau ---------------------
        # If plateau-vs-content contrast is below ``min_range``, the local
        # region is not actually a plateau — the boundary is likely a flat
        # frame interior or low-contrast scan. Use soft_floor symmetric gap.
        if range_ < min_range:
            le = max(prev + 1, b - soft_floor)
            re = max(le + 1, b + soft_floor)
            gap_edges.append((le, re))
            prev = re
            continue

        # ---- walk outward until first "out of plateau" sample -----------
        def _walk(start_idx, step):
            i = start_idx + step
            while 0 <= i < n_sub:
                if not in_plateau(float(sub[i])):
                    return i
                i += step
            return -1 if step < 0 else n_sub  # hit window boundary

        left_first_out = _walk(b_rel, -1)
        right_first_out = _walk(b_rel, +1)
        hit_left_bound = left_first_out < 0
        hit_right_bound = right_first_out >= n_sub

        # ---- mirror-fallback: if one side hit window edge, mirror the
        # other side's measured half-gap (preserves trusted half).
        if hit_left_bound and not hit_right_bound:
            right_half = right_first_out - b_rel
            le_rel = max(0, b_rel - right_half)
            le = s0 + le_rel
            re = s0 + right_first_out
        elif hit_right_bound and not hit_left_bound:
            left_half = b_rel - (left_first_out + 1)
            re_rel = min(n_sub, b_rel + left_half)
            le = s0 + left_first_out + 1
            re = s0 + re_rel
        elif hit_left_bound and hit_right_bound:
            # Both hit window — abandon, fall through to soft_floor.
            le = max(0, b - soft_floor)
            re = min(size, b + soft_floor)
        else:
            le = s0 + left_first_out + 1
            re = s0 + right_first_out

        gap_width = re - le

        # ---- implausibly wide → reject ----------------------------------
        if gap_width > max_gap:
            gap_edges.append((b, b))
            prev = b
            continue

        # Soft-floor: never narrower than 2*soft_floor total
        if gap_width < soft_floor * 2:
            le = b - soft_floor
            re = b + soft_floor

        # Monotonicity guard against previous gap
        le = max(prev + 1, le)
        re = max(le + 1, re)
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


_LONG_EDGE_CONF_LOW = 0.25
_LONG_EDGE_CONF_HIGH = 0.55


def _long_edge_confidence(arr, is_horizontal, long_edges, cross_size, sample_count=12):
    """Score how cleanly each long edge separates film from film-base.

    Returns (near_conf, far_conf, near_diag, far_diag) where each conf is in
    [0, 1]. Combines two cues:
      - Gradient strength: max |diff| around the edge in the global cross-axis
        projection, normalised against 20% of the projection's P5..P95 range.
      - Along-axis consistency: at `sample_count` evenly spaced positions along
        the scan axis, locate the strongest local gradient near the edge; a
        small std of those positions means the edge is straight and stable.
    Score = 0.6 * gradient_strength + 0.4 * consistency.
    """
    near, far = long_edges
    radius = max(8, int(cross_size * 0.005))

    if is_horizontal:
        proj = arr.mean(axis=1).astype(np.float32)
        scan_size = arr.shape[1]
    else:
        proj = arr.mean(axis=0).astype(np.float32)
        scan_size = arr.shape[1] if not is_horizontal else arr.shape[0]
        # arr.shape == (h, w); when is_horizontal=False the cross axis is x,
        # so projection is per-column (axis=0) and scan size is height.
        scan_size = arr.shape[0]

    proj_range = float(np.percentile(proj, 95) - np.percentile(proj, 5))
    grad_norm = max(proj_range * 0.2, 1e-6)

    def _grad_strength(center: int) -> float:
        lo = max(0, center - radius)
        hi = min(len(proj), center + radius + 1)
        if hi - lo < 3:
            return 0.0
        local = proj[lo:hi]
        return float(np.clip(np.max(np.abs(np.diff(local))) / grad_norm, 0.0, 1.0))

    def _consistency(center: int) -> tuple:
        if center <= 0 or center >= cross_size - 1 or scan_size < sample_count * 4:
            return 0.0, []
        big_lo = max(0, center - 4 * radius)
        big_hi = min(cross_size, center + 4 * radius + 1)
        if big_hi - big_lo < 5:
            return 0.0, []
        sample_positions = np.linspace(
            scan_size * 0.1, scan_size * 0.9, sample_count
        ).astype(int)
        sample_positions = np.clip(sample_positions, 0, scan_size - 1)
        positions: list = []
        for s in sample_positions:
            if is_horizontal:
                strip = arr[big_lo:big_hi, max(0, s - 4):min(arr.shape[1], s + 5)]
                if strip.size == 0:
                    continue
                col = strip.mean(axis=1).astype(np.float32)
            else:
                strip = arr[max(0, s - 4):min(arr.shape[0], s + 5), big_lo:big_hi]
                if strip.size == 0:
                    continue
                col = strip.mean(axis=0).astype(np.float32)
            if len(col) < 3:
                continue
            grad = np.abs(np.diff(col))
            local_peak = big_lo + int(np.argmax(grad))
            positions.append(local_peak)
        if len(positions) < sample_count // 2:
            return 0.0, positions
        std = float(np.std(positions))
        return float(np.clip(1.0 - std / (4 * radius), 0.0, 1.0)), positions

    near_grad = _grad_strength(near)
    far_grad = _grad_strength(far)
    near_cons, near_pos = _consistency(near)
    far_cons, far_pos = _consistency(far)

    near_conf = 0.6 * near_grad + 0.4 * near_cons
    far_conf = 0.6 * far_grad + 0.4 * far_cons
    near_diag = {"grad": round(near_grad, 3), "cons": round(near_cons, 3)}
    far_diag = {"grad": round(far_grad, 3), "cons": round(far_cons, 3)}
    return float(near_conf), float(far_conf), near_diag, far_diag


_ZERO_MARGIN_THRESHOLD = 5
_ZERO_MARGIN_WALK_FRAC = 0.04
_ZERO_MARGIN_HYSTERESIS = 3
_ZERO_MARGIN_BASE_SAMPLE = 4
_ZERO_MARGIN_SIGMA = 3.0

# Gap-edge plateau refinement: walk each gap edge outward until the
# transition gradient drops to a small fraction of its local peak.
# The initial plateau-walk (drop_frac=0.15) places edges early in the
# transition, leaving most of the gradient zone inside frames.
_GAP_REFINE_HYSTERESIS = 3
_GAP_REFINE_WALK_MAX = 60          # px — search window around each edge
_GAP_REFINE_GRAD_FRAC = 0.15       # threshold = peak_grad * 0.15
_GAP_REFINE_MIN_PEAK = 0.002       # absolute gradient floor — skip flat edges
_GAP_REFINE_MAX_SHIFT = 50         # hard cap on how far an edge may move


def _tighten_zero_margin(arr, is_horizontal, long_edges, cross_size):
    """Walk inward from a near-zero film-base margin until image content begins.

    Triple safety: 3σ deviation gate, 3-line hysteresis, and a hard 4% walk
    cap. Only acts on sides where the current margin is ≤5px. Returns the
    (possibly tightened) (near, far) tuple.
    """
    near, far = long_edges
    walk_max = max(8, int(cross_size * _ZERO_MARGIN_WALK_FRAC))
    sample = _ZERO_MARGIN_BASE_SAMPLE

    def _line_mean(idx: int) -> float:
        if is_horizontal:
            if idx < 0 or idx >= arr.shape[0]:
                return 0.0
            return float(arr[idx, :].mean())
        else:
            if idx < 0 or idx >= arr.shape[1]:
                return 0.0
            return float(arr[:, idx].mean())

    def _walk(start: int, direction: int) -> int:
        # Sample film-base from the outermost rows/columns on this side.
        if direction == 1:
            base_indices = [max(0, start + i) for i in range(sample)]
        else:
            base_indices = [max(0, start - i) for i in range(sample)]
        base_means = np.array([_line_mean(i) for i in base_indices], dtype=np.float32)
        base_mean = float(base_means.mean())
        base_std = float(base_means.std())
        threshold = max(_ZERO_MARGIN_SIGMA * base_std, 1.5)
        out_streak = 0
        last_in = start
        for step in range(sample, walk_max):
            idx = start + step * direction
            if idx < 0 or idx >= cross_size:
                break
            m = _line_mean(idx)
            if abs(m - base_mean) > threshold:
                out_streak += 1
                if out_streak >= _ZERO_MARGIN_HYSTERESIS:
                    # Step back to the first out-of-distribution line.
                    return idx - (out_streak - 1) * direction
            else:
                out_streak = 0
                last_in = idx
        return last_in

    new_near, new_far = near, far
    if near <= _ZERO_MARGIN_THRESHOLD:
        new_near = max(near, _walk(near, 1))
    if (cross_size - far) <= _ZERO_MARGIN_THRESHOLD:
        new_far = min(far, _walk(far, -1))

    if new_near >= new_far:
        return long_edges
    return int(new_near), int(new_far)


def _refine_gap_edges_to_plateau(arr, is_horizontal, gap_edges, long_edges,
                                  cross_size, mode):
    """Refine gap edges by absorbing the transition zone into the gap.

    The initial plateau-walk (``drop_frac = 0.15``) places edges early in
    the gap-to-frame transition.  This leaves most of the gradient zone
    inside adjacent frames, causing visible bleed.  Here we look at the
    *gradient* of the scan projection: the transition zone has a sharp
    gradient peak, while frame content is comparatively flat.  We walk
    each edge outward past the local gradient peak until the gradient
    drops to a small fraction (``_GAP_REFINE_GRAD_FRAC``) of that peak
    for ``_GAP_REFINE_HYSTERESIS`` consecutive rows.

    Parameters
    ----------
    arr : ndarray
        Original-resolution grayscale image (uint8).
    is_horizontal : bool
        Film strips run horizontally (scan axis = x).
    gap_edges : list[(le, re)]
        Current gap edges in scan-axis coordinates.
    long_edges : (near, far)
        Cross-axis bounds.
    cross_size : int
        Size of the cross axis (height if horizontal, width if not).
    mode : {"peak", "valley"}
        Gap polarity (ignored — gradient is sign-agnostic).

    Returns
    -------
    list[(le, re)]
        Refined gap edges (may be identical to input if no walk was needed).
    """
    if not gap_edges or cross_size <= 0:
        return gap_edges

    near, far = long_edges
    if near >= far:
        near, far = 0, cross_size

    # Compute scan projection limited to the long-edge band.
    if is_horizontal:
        scan_projection = np.mean(arr[near:far, :], axis=0) / 255.0
    else:
        scan_projection = np.mean(arr[:, near:far], axis=1) / 255.0

    n = len(scan_projection)

    # First derivative (central differences) + light smoothing.
    grad = np.zeros_like(scan_projection)
    grad[1:-1] = np.abs(scan_projection[2:] - scan_projection[:-2]) / 2.0
    grad[0] = abs(scan_projection[1] - scan_projection[0])
    grad[-1] = abs(scan_projection[-1] - scan_projection[-2])
    smooth_k = np.ones(5) / 5.0
    grad = np.convolve(grad, smooth_k, mode="same")

    walk_max = _GAP_REFINE_WALK_MAX
    shift_cap = _GAP_REFINE_MAX_SHIFT
    hysteresis = _GAP_REFINE_HYSTERESIS
    grad_frac = _GAP_REFINE_GRAD_FRAC
    min_peak = _GAP_REFINE_MIN_PEAK

    refined = []
    for i, (le, re) in enumerate(gap_edges):
        if re <= le:
            refined.append((le, re))
            continue

        new_le, new_re = le, re

        # ---- left edge: search [le - walk_max, le] ---------------------
        left_win_start = max(0, le - walk_max)
        left_grad_win = grad[left_win_start:le]
        if len(left_grad_win) > 0:
            peak_rel = int(np.argmax(left_grad_win))
            peak_idx = left_win_start + peak_rel
            peak_val = float(left_grad_win[peak_rel])
            if peak_val >= min_peak:
                threshold = peak_val * grad_frac
                streak = 0
                for idx in range(peak_idx - 1, max(-1, peak_idx - 1 - walk_max), -1):
                    if grad[idx] <= threshold:
                        streak += 1
                        if streak >= hysteresis:
                            candidate = idx + streak - 1
                            if le - candidate <= shift_cap:
                                new_le = candidate
                            break
                    else:
                        streak = 0

        # ---- right edge: search [re, re + walk_max] --------------------
        right_win_end = min(n, re + walk_max)
        right_grad_win = grad[re:right_win_end]
        if len(right_grad_win) > 0:
            peak_rel = int(np.argmax(right_grad_win))
            peak_idx = re + peak_rel
            peak_val = float(right_grad_win[peak_rel])
            if peak_val >= min_peak:
                threshold = peak_val * grad_frac
                streak = 0
                for idx in range(peak_idx + 1, min(n, peak_idx + 1 + walk_max)):
                    if grad[idx] <= threshold:
                        streak += 1
                        if streak >= hysteresis:
                            candidate = idx - streak + 1
                            if candidate - re <= shift_cap:
                                new_re = candidate
                            break
                    else:
                        streak = 0

        # Prevent edges from crossing adjacent frames.
        if i > 0:
            prev_re = refined[-1][1]
            new_le = max(new_le, prev_re + 1)
        new_re = max(new_re, new_le + 1)

        refined.append((int(new_le), int(new_re)))

    return refined


_FRAME_CONFIDENCE_REVIEW_THRESHOLD = 0.55


def _frame_confidence(frame, aspect_ratio, is_horizontal, gap_shape_score, near_conf, far_conf):
    """Combine three independent quality signals into a single 0-1 score.

    Components (weighted sum):
      aspect_residual (0.5) — frame ratio vs. requested aspect_ratio
      gap_shape       (0.25) — chosen-mode gap-shape validation score
      edge_strength   (0.25) — average long-edge gradient confidence
    """
    fw = frame["right"] - frame["left"]
    fh = frame["bottom"] - frame["top"]
    if fw <= 0 or fh <= 0:
        return 0.0
    actual = (fw / fh) if is_horizontal else (fh / fw)
    rel_err = abs(actual - aspect_ratio) / aspect_ratio if aspect_ratio > 0 else 1.0
    aspect_score = max(0.0, 1.0 - rel_err / 0.5)  # 0 at 50% off, 1 at perfect
    gap_norm = max(0.0, min(1.0, (gap_shape_score + 0.05) / 0.30))
    edge_score = max(0.0, min(1.0, (near_conf + far_conf) / 2.0))
    return 0.5 * aspect_score + 0.25 * gap_norm + 0.25 * edge_score


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


_KNOWN_FORMAT_RATIOS = (1.0, 7 / 6, 5 / 4, 3 / 2)
_AUTO_ASPECT_SNAP_TOLERANCE = 0.08


def _auto_aspect_ratio(chosen_edges, long_edges, scan_size, cross_size):
    """Estimate the long/short aspect ratio from detected frames.

    Returns (resolved_ratio, raw_ratio). resolved_ratio snaps to the nearest
    known format (1.0, 7/6, 5/4, 3/2) when within 8% relative deviation;
    otherwise equals raw_ratio. Falls back to (3/2, None) when geometry is
    degenerate.
    """
    if not chosen_edges or long_edges is None:
        return 3 / 2, None
    cross_span = long_edges[1] - long_edges[0]
    if cross_span <= 0 or cross_size <= 0:
        return 3 / 2, None

    boundaries = [0]
    for le, re in chosen_edges:
        boundaries.append(le)
        boundaries.append(re)
    boundaries.append(scan_size)
    frame_widths = [
        boundaries[i + 1] - boundaries[i]
        for i in range(0, len(boundaries) - 1, 2)
    ]
    frame_widths = [w for w in frame_widths if w > 0]
    if len(frame_widths) < 2:
        return 3 / 2, None
    if len(frame_widths) >= 4:
        frame_widths = frame_widths[1:-1]
    median_scan = float(np.median(frame_widths))
    if median_scan <= 0:
        return 3 / 2, None

    raw_ratio = median_scan / cross_span
    best = min(_KNOWN_FORMAT_RATIOS, key=lambda r: abs(raw_ratio - r) / r)
    if abs(raw_ratio - best) / best <= _AUTO_ASPECT_SNAP_TOLERANCE:
        return best, raw_ratio
    return raw_ratio, raw_ratio


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


def analyze_image(image_path: str, expected_frames: int = 6, cleanup_scale: float = 0.5, original_path: Optional[str] = None, aspect_ratio: Optional[float] = 3 / 2) -> dict:
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

    # Auto-detect aspect ratio when caller did not specify one
    auto_aspect_raw: Optional[float] = None
    if aspect_ratio is None:
        aspect_ratio, auto_aspect_raw = _auto_aspect_ratio(
            orig_chosen_edges, orig_long_edges, orig_scan_size, orig_cross_size
        )

    # Aspect-ratio constrained refinement on original image
    orig_proportional = _detect_long_edges_proportional(
        orig_arr, is_horizontal, orig_chosen_edges, aspect_ratio=aspect_ratio
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
        aspect_ratio=aspect_ratio, search_margin=50,
    )
    orig_long_edges = refined if refined else orig_prev_long_edges

    # Confidence-gated symmetry mirror: trust the high-confidence side and
    # mirror its margin only when the opposite side is clearly missed.
    # Both-high or both-low (or both-medium) leaves the asymmetric crop intact,
    # which preserves legal off-centre framings instead of clobbering them.
    near_long_conf, far_long_conf, near_long_diag, far_long_diag = (
        _long_edge_confidence(orig_arr, is_horizontal, orig_long_edges, orig_cross_size)
    )
    if orig_long_edges != (0, orig_cross_size):
        left_margin = orig_long_edges[0]
        right_margin = orig_cross_size - orig_long_edges[1]
        margin_diff = abs(left_margin - right_margin)
        asymmetric = (
            margin_diff > max(10, int(orig_cross_size * 0.02))
            and max(left_margin, right_margin) > 5
        )
        if asymmetric:
            if near_long_conf >= _LONG_EDGE_CONF_HIGH and far_long_conf < _LONG_EDGE_CONF_LOW:
                orig_long_edges = (left_margin, orig_cross_size - left_margin)
            elif far_long_conf >= _LONG_EDGE_CONF_HIGH and near_long_conf < _LONG_EDGE_CONF_LOW:
                orig_long_edges = (right_margin, orig_cross_size - right_margin)
            # Both-high / both-low / mixed: keep the asymmetric edges as-is.

    # Zero-margin tightening: when the film runs flush to one side of the
    # scan, the long-edge detector returns the bare image edge, leaving 1-2px
    # of black film border in the crop. Walk inward content-aware until we
    # cross a 3σ deviation streak.
    if (orig_long_edges[0] <= _ZERO_MARGIN_THRESHOLD or
            orig_cross_size - orig_long_edges[1] <= _ZERO_MARGIN_THRESHOLD):
        orig_long_edges = _tighten_zero_margin(
            orig_arr, is_horizontal, orig_long_edges, orig_cross_size
        )

    # Plateau-refinement: the initial plateau-walk places gap edges at 15 %
    # of the transition from plateau toward content.  This leaves most of the
    # gradient zone inside adjacent frames, causing visible bleed.  Walk each
    # edge outward until the signal stabilises at frame-content level.
    orig_chosen_edges = _refine_gap_edges_to_plateau(
        orig_arr, is_horizontal, orig_chosen_edges,
        orig_long_edges, orig_cross_size, chosen_mode
    )

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

                # --- Hard-clamp protection: never cross the gap centre into a
                # neighbouring middle frame.  When the median-forced span is
                # wider than the natural extent the recentre step can push
                # ``new_left`` / ``new_right`` past the adjacent gap, producing
                # frame overlap.  Clamping to the gap centre splits each gap
                # symmetrically between the two frames it separates and
                # guarantees mutual exclusivity.  3:2 still holds for frames
                # that fit; clamped frames trade a small slice of scan-dim
                # (and therefore aspect ratio) for non-overlap.
                prev_gap_center = (orig_chosen_edges[i - 1][0] + orig_chosen_edges[i - 1][1]) // 2
                next_gap_center = (orig_chosen_edges[i][0] + orig_chosen_edges[i][1]) // 2
                if new_left < prev_gap_center:
                    new_left = prev_gap_center
                if new_right > next_gap_center:
                    new_right = next_gap_center

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

                # Hard-clamp protection (see horizontal branch above).
                prev_gap_center = (orig_chosen_edges[i - 1][0] + orig_chosen_edges[i - 1][1]) // 2
                next_gap_center = (orig_chosen_edges[i][0] + orig_chosen_edges[i][1]) // 2
                if new_top < prev_gap_center:
                    new_top = prev_gap_center
                if new_bottom > next_gap_center:
                    new_bottom = next_gap_center

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

    # Per-frame confidence + global needsReview flag
    chosen_gap_shape = peak_shape if chosen_mode == "peak" else valley_shape
    for fr in frames:
        fr["confidence"] = round(
            _frame_confidence(
                fr, float(aspect_ratio), is_horizontal,
                chosen_gap_shape, near_long_conf, far_long_conf,
            ),
            3,
        )
    needs_review = any(
        fr.get("confidence", 0.0) < _FRAME_CONFIDENCE_REVIEW_THRESHOLD
        for fr in frames
    )

    elapsed = time.time() - t0

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
    debug_info["aspectRatio"] = round(float(aspect_ratio), 4)
    if auto_aspect_raw is not None:
        debug_info["autoAspectRaw"] = round(float(auto_aspect_raw), 4)
    debug_info["longEdgeConfidence"] = {
        "near": round(near_long_conf, 3),
        "far": round(far_long_conf, 3),
        "near_diag": near_long_diag,
        "far_diag": far_long_diag,
    }

    return {
        "frameCount": len(frames),
        "sourceWidth": thumb_w,
        "sourceHeight": thumb_h,
        "frames": frames,
        "cropAngle": round(crop_angle, 2),
        "needsReview": needs_review,
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
