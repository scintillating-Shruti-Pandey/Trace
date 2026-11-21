"""Classical IVP pipeline — all techniques integrated with TRACE's industrial corpus.

Each function accepts a numpy array (BGR image, uint8) and returns a result dict
with the processed image(s) and any derived metrics. All operations are pure
OpenCV + NumPy — zero paid APIs, zero network calls.
"""

from __future__ import annotations

import base64
import math
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _encode_png(img: np.ndarray) -> str:
    """Encode a numpy image (any dtype) to base64 PNG string for JSON/HTML."""
    if img.dtype != np.uint8:
        # Normalize to 0-255 for display
        mn, mx = img.min(), img.max()
        if mx > mn:
            img = ((img - mn) / (mx - mn) * 255).astype(np.uint8)
        else:
            img = np.zeros_like(img, dtype=np.uint8)
    _, buf = cv2.imencode(".png", img)
    return base64.b64encode(buf).decode("utf-8")


def _to_gray(bgr: np.ndarray) -> np.ndarray:
    if len(bgr.shape) == 2:
        return bgr
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)


# ---------------------------------------------------------------------------
# 1. Color Space Conversion
# ---------------------------------------------------------------------------

def analyze_color_spaces(bgr: np.ndarray) -> dict[str, Any]:
    """Convert BGR image to Grayscale, HSV, and LAB color spaces.

    Returns all three conversions with channel-level statistics.
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    hsv  = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    lab  = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    rgb  = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    h, s, v = cv2.split(hsv)
    l_ch, a_ch, b_ch = cv2.split(lab)

    return {
        "technique": "Color Space Conversion",
        "description": (
            "Converts the original BGR frame into Grayscale (luminance only), "
            "HSV (Hue–Saturation–Value, separates colour from brightness), and "
            "LAB (perceptually uniform colour space). Used in TRACE to normalise "
            "industrial frames before feature extraction."
        ),
        "images": {
            "original_rgb":  _encode_png(rgb),
            "grayscale":     _encode_png(gray),
            "hsv":           _encode_png(hsv),
            "lab":           _encode_png(lab),
        },
        "metrics": {
            "mean_brightness_gray": float(gray.mean()),
            "mean_hue":  float(h.mean()),
            "mean_sat":  float(s.mean()),
            "mean_val":  float(v.mean()),
            "mean_L":    float(l_ch.mean()),
            "std_gray":  float(gray.std()),
        },
    }


# ---------------------------------------------------------------------------
# 2. Histogram Analysis & Equalization
# ---------------------------------------------------------------------------

def analyze_histograms(bgr: np.ndarray) -> dict[str, Any]:
    """Compute BGR channel histograms and apply CLAHE equalization.

    CLAHE (Contrast Limited Adaptive Histogram Equalization) enhances local
    contrast — critical for detecting faint features in industrial images.
    """
    gray = _to_gray(bgr)

    # Channel histograms
    hists = {}
    colors = ("blue", "green", "red")
    for i, col in enumerate(colors):
        hist = cv2.calcHist([bgr], [i], None, [256], [0, 256]).flatten()
        hists[col] = hist.tolist()
    gray_hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()

    # CLAHE on L channel (LAB space — avoids colour shift)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_eq = clahe.apply(l_ch)
    lab_eq = cv2.merge([l_eq, a_ch, b_ch])
    bgr_eq = cv2.cvtColor(lab_eq, cv2.COLOR_LAB2BGR)

    # Standard global histogram equalization (grayscale)
    gray_eq = cv2.equalizeHist(gray)

    return {
        "technique": "Histogram Analysis & CLAHE Equalization",
        "description": (
            "Histograms show the pixel intensity distribution across B, G, R channels. "
            "CLAHE equalizes contrast locally (8×8 tiles) to reveal detail in dark "
            "workshop shadows and bright reflective metal surfaces — common in IndEgo "
            "assembly footage."
        ),
        "images": {
            "original":          _encode_png(bgr),
            "clahe_equalized":   _encode_png(bgr_eq),
            "gray_equalized":    _encode_png(gray_eq),
        },
        "metrics": {
            "gray_histogram":  gray_hist.tolist(),
            "channel_hists":   hists,
            "original_contrast_std":  float(gray.std()),
            "equalized_contrast_std": float(gray_eq.std()),
        },
    }


# ---------------------------------------------------------------------------
# 3. Gaussian Blur & Convolution Filtering
# ---------------------------------------------------------------------------

def analyze_filtering(bgr: np.ndarray) -> dict[str, Any]:
    """Apply Gaussian blur, sharpening, and custom convolution kernels.

    Demonstrates the fundamental convolution operation that underlies all
    convolutional neural networks and classical image processing.
    """
    gray = _to_gray(bgr)

    # Gaussian blur — noise reduction before edge detection
    blur_3  = cv2.GaussianBlur(gray, (3, 3), 0)
    blur_7  = cv2.GaussianBlur(gray, (7, 7), 0)
    blur_15 = cv2.GaussianBlur(gray, (15, 15), 0)

    # Sharpening kernel (unsharp masking)
    kernel_sharp = np.array([
        [ 0, -1,  0],
        [-1,  5, -1],
        [ 0, -1,  0]
    ], dtype=np.float32)
    sharpened = cv2.filter2D(gray, -1, kernel_sharp)
    sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)

    # Emboss kernel — highlights surface texture (useful for workpiece inspection)
    kernel_emboss = np.array([
        [-2, -1,  0],
        [-1,  1,  1],
        [ 0,  1,  2]
    ], dtype=np.float32)
    embossed = cv2.filter2D(gray, -1, kernel_emboss)
    embossed = np.clip(embossed + 128, 0, 255).astype(np.uint8)

    # Laplacian (second derivative) — detects regions of rapid intensity change
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    laplacian_abs = np.abs(laplacian).astype(np.uint8)

    return {
        "technique": "Convolution & Image Filtering",
        "description": (
            "Convolution applies a small kernel (filter matrix) across every pixel. "
            "Gaussian blur (kernel sizes 3, 7, 15) removes noise. The sharpening kernel "
            "enhances edges. The Laplacian (second spatial derivative) detects regions of "
            "rapid intensity change — useful for detecting fastener positions on assembly frames."
        ),
        "images": {
            "original_gray":   _encode_png(gray),
            "gaussian_blur_3": _encode_png(blur_3),
            "gaussian_blur_7": _encode_png(blur_7),
            "gaussian_blur_15":_encode_png(blur_15),
            "sharpened":       _encode_png(sharpened),
            "embossed":        _encode_png(embossed),
            "laplacian":       _encode_png(laplacian_abs),
        },
        "metrics": {
            "original_sharpness_laplacian_var":  float(cv2.Laplacian(gray, cv2.CV_64F).var()),
            "blurred_sharpness_laplacian_var":   float(cv2.Laplacian(blur_7, cv2.CV_64F).var()),
            "sharpened_laplacian_var":           float(cv2.Laplacian(sharpened, cv2.CV_64F).var()),
        },
    }


# ---------------------------------------------------------------------------
# 4. Edge Detection — Sobel & Canny
# ---------------------------------------------------------------------------

def analyze_edges(bgr: np.ndarray) -> dict[str, Any]:
    """Sobel gradient (X, Y, magnitude, direction) and Canny multi-threshold edge detection.

    Sobel computes the first derivative — the rate of change of intensity.
    Canny uses non-maximum suppression + hysteresis for clean, thin edges.
    """
    gray = cv2.GaussianBlur(_to_gray(bgr), (5, 5), 0)

    # Sobel
    sobel_x  = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y  = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    magnitude = np.sqrt(sobel_x**2 + sobel_y**2)
    direction = np.arctan2(sobel_y, sobel_x) * 180 / math.pi

    sx_abs = np.clip(np.abs(sobel_x), 0, 255).astype(np.uint8)
    sy_abs = np.clip(np.abs(sobel_y), 0, 255).astype(np.uint8)
    mag_norm = ((magnitude / magnitude.max()) * 255).astype(np.uint8) if magnitude.max() > 0 else np.zeros_like(gray)

    # Direction visualized: map -180..180 → 0..255
    dir_vis = ((direction + 180) / 360 * 255).astype(np.uint8)

    # Canny — different threshold pairs
    canny_tight  = cv2.Canny(gray, 100, 200)
    canny_medium = cv2.Canny(gray, 50, 150)
    canny_loose  = cv2.Canny(gray, 20, 80)

    edge_density = float(np.count_nonzero(canny_medium)) / (gray.shape[0] * gray.shape[1])

    return {
        "technique": "Edge Detection (Sobel + Canny)",
        "description": (
            "Sobel operator computes the image gradient (rate of pixel intensity change) "
            "in horizontal (Gx) and vertical (Gy) directions. Magnitude = √(Gx²+Gy²) "
            "gives overall edge strength. Canny adds non-maximum suppression and "
            "hysteresis thresholding to produce thin, connected edges. In TRACE, edge "
            "maps are used to quantify frame complexity and detect workpiece boundaries."
        ),
        "images": {
            "original_gray":   _encode_png(_to_gray(bgr)),
            "sobel_x":         _encode_png(sx_abs),
            "sobel_y":         _encode_png(sy_abs),
            "sobel_magnitude": _encode_png(mag_norm),
            "gradient_direction": _encode_png(dir_vis),
            "canny_tight":     _encode_png(canny_tight),
            "canny_medium":    _encode_png(canny_medium),
            "canny_loose":     _encode_png(canny_loose),
        },
        "metrics": {
            "mean_gradient_magnitude":   float(magnitude.mean()),
            "max_gradient_magnitude":    float(magnitude.max()),
            "edge_density_pct_medium":   round(edge_density * 100, 3),
            "canny_tight_edges":         int(np.count_nonzero(canny_tight)),
            "canny_medium_edges":        int(np.count_nonzero(canny_medium)),
            "canny_loose_edges":         int(np.count_nonzero(canny_loose)),
        },
    }


# ---------------------------------------------------------------------------
# 5. Morphological Operations
# ---------------------------------------------------------------------------

def analyze_morphology(bgr: np.ndarray) -> dict[str, Any]:
    """Erosion, dilation, opening, closing, morphological gradient on a binary edge map.

    Morphological operations use a structuring element (kernel) to modify shapes.
    Critical for cleaning binary masks in workpiece segmentation.
    """
    gray   = _to_gray(bgr)
    _, binary = cv2.threshold(
        cv2.GaussianBlur(gray, (5, 5), 0), 0, 255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    kernel_3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    kernel_7 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))

    eroded   = cv2.erode(binary,   kernel_3, iterations=2)
    dilated  = cv2.dilate(binary,  kernel_3, iterations=2)
    opened   = cv2.morphologyEx(binary, cv2.MORPH_OPEN,     kernel_7)
    closed   = cv2.morphologyEx(binary, cv2.MORPH_CLOSE,    kernel_7)
    gradient = cv2.morphologyEx(binary, cv2.MORPH_GRADIENT, kernel_3)
    tophat   = cv2.morphologyEx(binary, cv2.MORPH_TOPHAT,   kernel_7)
    blackhat = cv2.morphologyEx(binary, cv2.MORPH_BLACKHAT, kernel_7)

    return {
        "technique": "Morphological Operations",
        "description": (
            "Applied to an Otsu-thresholded binary image. Erosion shrinks bright regions "
            "(removes small noise). Dilation expands them (fills small holes). "
            "Opening = erosion then dilation (removes noise, preserves shape). "
            "Closing = dilation then erosion (fills gaps). Morphological gradient = "
            "dilation − erosion (detects boundaries). Top-hat and Black-hat extract "
            "bright/dark features relative to the background."
        ),
        "images": {
            "original_gray": _encode_png(gray),
            "binary_otsu":   _encode_png(binary),
            "eroded":        _encode_png(eroded),
            "dilated":       _encode_png(dilated),
            "opened":        _encode_png(opened),
            "closed":        _encode_png(closed),
            "gradient":      _encode_png(gradient),
            "tophat":        _encode_png(tophat),
            "blackhat":      _encode_png(blackhat),
        },
        "metrics": {
            "binary_fill_pct":   round(float(np.count_nonzero(binary))   / binary.size * 100, 2),
            "eroded_fill_pct":   round(float(np.count_nonzero(eroded))   / binary.size * 100, 2),
            "dilated_fill_pct":  round(float(np.count_nonzero(dilated))  / binary.size * 100, 2),
            "gradient_px_count": int(np.count_nonzero(gradient)),
        },
    }


# ---------------------------------------------------------------------------
# 6. SIFT / ORB Feature Detection
# ---------------------------------------------------------------------------

def analyze_keypoints(bgr: np.ndarray) -> dict[str, Any]:
    """SIFT and ORB keypoint detection + descriptor extraction.

    SIFT (Scale-Invariant Feature Transform): detects stable interest points
    invariant to scale, rotation, and illumination changes.
    ORB (Oriented FAST + Rotated BRIEF): faster binary alternative to SIFT,
    patent-free, used for real-time matching on the RTX 4050 GPU.
    """
    gray = _to_gray(bgr)

    # SIFT
    sift = cv2.SIFT_create(nfeatures=500)
    kp_sift, desc_sift = sift.detectAndCompute(gray, None)
    img_sift = cv2.drawKeypoints(
        bgr.copy(), kp_sift, None,
        flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS
    )

    # ORB
    orb = cv2.ORB_create(nfeatures=500)
    kp_orb, desc_orb = orb.detectAndCompute(gray, None)
    img_orb = cv2.drawKeypoints(
        bgr.copy(), kp_orb, None,
        flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS
    )

    # Keypoint size distribution
    sift_sizes = [kp.size for kp in kp_sift]
    sift_responses = [kp.response for kp in kp_sift]

    return {
        "technique": "Feature Detection — SIFT & ORB",
        "description": (
            "SIFT detects scale- and rotation-invariant keypoints and computes 128-d "
            "float descriptors. ORB detects FAST corners and computes 32-byte binary "
            "descriptors — 100× faster than SIFT. In TRACE, these keypoints can be "
            "matched across frames to identify repeated assembly steps or track "
            "component positions across different videos."
        ),
        "images": {
            "sift_keypoints": _encode_png(img_sift),
            "orb_keypoints":  _encode_png(img_orb),
        },
        "metrics": {
            "sift_keypoints_count":     len(kp_sift),
            "orb_keypoints_count":      len(kp_orb),
            "sift_descriptor_shape":    list(desc_sift.shape) if desc_sift is not None else [0, 128],
            "orb_descriptor_shape":     list(desc_orb.shape)  if desc_orb  is not None else [0, 32],
            "sift_mean_keypoint_size":  round(float(np.mean(sift_sizes)), 2) if sift_sizes else 0.0,
            "sift_mean_response":       round(float(np.mean(sift_responses)), 4) if sift_responses else 0.0,
        },
    }


# ---------------------------------------------------------------------------
# 7. Optical Flow — Lucas-Kanade & Farneback Dense
# ---------------------------------------------------------------------------

def analyze_optical_flow(frame1: np.ndarray, frame2: np.ndarray) -> dict[str, Any]:
    """Sparse Lucas-Kanade and dense Farneback optical flow between two frames.

    Optical flow estimates the apparent motion of pixels between two consecutive
    frames — directly maps to "what is moving" in the video.
    """
    gray1 = _to_gray(frame1)
    gray2 = _to_gray(frame2)

    # --- Sparse: Lucas-Kanade on Shi-Tomasi corners ---
    corners = cv2.goodFeaturesToTrack(
        gray1, maxCorners=200, qualityLevel=0.01, minDistance=10
    )
    lk_params = dict(
        winSize=(15, 15), maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
    )
    p1, st, _ = cv2.calcOpticalFlowPyrLK(gray1, gray2, corners, None, **lk_params)

    good_old = corners[st == 1] if corners is not None and p1 is not None else np.array([])
    good_new = p1[st == 1]      if p1 is not None else np.array([])

    lk_vis = frame2.copy()
    for new, old in zip(good_new, good_old):
        a, b = int(new[0]), int(new[1])
        c, d = int(old[0]), int(old[1])
        cv2.arrowedLine(lk_vis, (c, d), (a, b), (0, 255, 0), 1, tipLength=0.3)
        cv2.circle(lk_vis, (a, b), 3, (0, 0, 255), -1)

    # --- Dense: Farneback ---
    flow = cv2.calcOpticalFlowFarneback(
        gray1, gray2, None,
        pyr_scale=0.5, levels=3, winsize=15, iterations=3,
        poly_n=5, poly_sigma=1.2, flags=0
    )
    # Convert flow to HSV colour-coded magnitude+direction
    mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    hsv_flow = np.zeros((*gray1.shape, 3), dtype=np.uint8)
    hsv_flow[..., 0] = ang * 180 / math.pi / 2          # Hue = direction
    hsv_flow[..., 1] = 255                               # Saturation = full
    hsv_flow[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
    dense_vis = cv2.cvtColor(hsv_flow, cv2.COLOR_HSV2BGR)

    mean_motion = float(mag.mean())
    max_motion  = float(mag.max())

    return {
        "technique": "Optical Flow (Lucas-Kanade Sparse + Farneback Dense)",
        "description": (
            "Lucas-Kanade tracks Shi-Tomasi corner points from frame N to N+1 — "
            "each arrow shows how that point moved. Farneback computes a dense flow "
            "field for every pixel; hue encodes motion direction, brightness encodes "
            "magnitude. In TRACE, dense flow magnitude is used to detect high-motion "
            "intervals (assembly actions) vs. idle periods for keyframe selection."
        ),
        "images": {
            "frame1":          _encode_png(frame1),
            "frame2":          _encode_png(frame2),
            "lk_sparse_flow":  _encode_png(lk_vis),
            "dense_flow_hsv":  _encode_png(dense_vis),
        },
        "metrics": {
            "tracked_points":        int(len(good_new)),
            "mean_flow_magnitude":   round(mean_motion, 4),
            "max_flow_magnitude":    round(max_motion,  4),
            "motion_active":         mean_motion > 1.0,
        },
    }


# ---------------------------------------------------------------------------
# 8. HOG — Histogram of Oriented Gradients
# ---------------------------------------------------------------------------

def analyze_hog(bgr: np.ndarray) -> dict[str, Any]:
    """Extract HOG features — the foundation of classic object detection (DPM, early pedestrian detection).

    HOG divides the image into cells, computes gradient orientation histograms
    per cell, normalizes across blocks. The resulting vector is a compact
    description of the image's shape/texture.
    """
    # Resize to standard HOG input size
    target_h, target_w = 128, 64
    resized = cv2.resize(bgr, (target_w, target_h))
    gray_r  = _to_gray(resized)

    win_size    = (target_w, target_h)
    block_size  = (16, 16)
    block_stride= (8, 8)
    cell_size   = (8, 8)
    n_bins      = 9

    hog = cv2.HOGDescriptor(win_size, block_size, block_stride, cell_size, n_bins)
    descriptor = hog.compute(gray_r)
    descriptor = descriptor.flatten()

    # HOG visualization: draw gradient arrows per cell
    hog_vis = resized.copy()
    cell_h, cell_w = cell_size
    rows = target_h // cell_h
    cols = target_w // cell_w

    for r in range(rows):
        for c in range(cols):
            cy = r * cell_h + cell_h // 2
            cx = c * cell_w + cell_w // 2
            cell = gray_r[r*cell_h:(r+1)*cell_h, c*cell_w:(c+1)*cell_w]
            gx = cv2.Sobel(cell, cv2.CV_64F, 1, 0, ksize=3).mean()
            gy = cv2.Sobel(cell, cv2.CV_64F, 0, 1, ksize=3).mean()
            angle = math.atan2(gy, gx)
            mag   = min(math.hypot(gx, gy), cell_h // 2 - 1)
            ex = int(cx + mag * math.cos(angle))
            ey = int(cy + mag * math.sin(angle))
            cv2.arrowedLine(hog_vis, (cx, cy), (ex, ey), (0, 255, 255), 1, tipLength=0.4)

    return {
        "technique": "HOG — Histogram of Oriented Gradients",
        "description": (
            "HOG divides the frame into 8×8 pixel cells. For each cell it builds a "
            "9-bin histogram of gradient orientations. These histograms are L2-normalized "
            "across overlapping 16×16 blocks. The final 3,780-d vector compactly "
            "describes the frame's shape structure. HOG was the state-of-the-art for "
            "pedestrian/object detection before deep learning; it is still used as a "
            "fast baseline feature for industrial workpiece classification."
        ),
        "images": {
            "original_resized": _encode_png(resized),
            "hog_visualization": _encode_png(hog_vis),
        },
        "metrics": {
            "descriptor_length":   int(len(descriptor)),
            "descriptor_mean":     round(float(descriptor.mean()), 6),
            "descriptor_std":      round(float(descriptor.std()),  6),
            "descriptor_max":      round(float(descriptor.max()),  6),
            "descriptor_nonzero":  int(np.count_nonzero(descriptor)),
        },
    }


# ---------------------------------------------------------------------------
# 9. Keyframe Extraction from Video
# ---------------------------------------------------------------------------

@dataclass
class KeyframeResult:
    frame_index: int
    timestamp_s: float
    inter_frame_diff: float
    frame_bgr: np.ndarray
    edge_density: float
    sharpness: float


def extract_keyframes(
    video_path: str,
    *,
    diff_threshold: float = 15.0,
    max_frames: int = 20,
    min_interval_s: float = 2.0,
) -> dict[str, Any]:
    """Extract keyframes from a video using inter-frame difference thresholding.

    A frame is selected as a keyframe when the mean absolute difference
    from the previous selected frame exceeds `diff_threshold`. This detects
    scene changes, camera cuts, and significant motion events.

    This is exactly how TRACE populates the `images` table with 114 keyframes
    from the IndEgo manufacturing dataset.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"error": f"Cannot open video: {video_path}"}

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    min_interval_frames = int(min_interval_s * fps)

    keyframes: list[KeyframeResult] = []
    prev_gray: np.ndarray | None = None
    frame_idx = 0
    last_kf_idx = -min_interval_frames

    while cap.isOpened() and len(keyframes) < max_frames:
        ret, frame = cap.read()
        if not ret:
            break

        gray = _to_gray(frame)

        if prev_gray is not None:
            diff = float(cv2.absdiff(gray, prev_gray).mean())
            interval_ok = (frame_idx - last_kf_idx) >= min_interval_frames

            if diff > diff_threshold and interval_ok:
                edge_map = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 150)
                edge_density = float(np.count_nonzero(edge_map)) / edge_map.size
                sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
                keyframes.append(KeyframeResult(
                    frame_index=frame_idx,
                    timestamp_s=round(frame_idx / fps, 2),
                    inter_frame_diff=round(diff, 2),
                    frame_bgr=frame.copy(),
                    edge_density=round(edge_density * 100, 3),
                    sharpness=round(sharpness, 2),
                ))
                last_kf_idx = frame_idx

        prev_gray = gray
        frame_idx += 1

    cap.release()

    encoded = [
        {
            "frame_index":       kf.frame_index,
            "timestamp_s":       kf.timestamp_s,
            "inter_frame_diff":  kf.inter_frame_diff,
            "edge_density_pct":  kf.edge_density,
            "sharpness":         kf.sharpness,
            "image_png_b64":     _encode_png(kf.frame_bgr),
        }
        for kf in keyframes
    ]

    return {
        "technique": "Keyframe Extraction (Inter-Frame Difference)",
        "description": (
            "Scans the video frame-by-frame. When the mean absolute pixel difference "
            "between consecutive frames exceeds the threshold (15.0 by default), the "
            "frame is selected as a keyframe. Each keyframe's edge density and "
            "sharpness (Laplacian variance) are computed as quality metrics. "
            "This is how TRACE extracts the 114 visual keyframes from IndEgo "
            "assembly videos for indexing in vec_image."
        ),
        "video_path":   video_path,
        "total_frames": total_frames,
        "fps":          fps,
        "keyframes":    encoded,
        "metrics": {
            "total_frames_scanned":     frame_idx,
            "keyframes_extracted":      len(keyframes),
            "mean_inter_frame_diff":    round(float(np.mean([k["inter_frame_diff"] for k in encoded])), 2) if encoded else 0.0,
            "mean_edge_density_pct":    round(float(np.mean([k["edge_density_pct"]  for k in encoded])), 3) if encoded else 0.0,
            "mean_sharpness":           round(float(np.mean([k["sharpness"]          for k in encoded])), 2) if encoded else 0.0,
        },
    }


# ---------------------------------------------------------------------------
# Full pipeline runner
# ---------------------------------------------------------------------------

def run_full_ivp_pipeline(bgr: np.ndarray, bgr2: np.ndarray | None = None) -> dict[str, Any]:
    """Run all IVP techniques on a single frame (and optionally a second frame for optical flow).

    Returns a dict keyed by technique name, each containing images, metrics, and description.
    Safe to call with a synthetically generated test frame if no real video is available.
    """
    results: dict[str, Any] = {}

    results["color_spaces"] = analyze_color_spaces(bgr)
    results["histograms"]   = analyze_histograms(bgr)
    results["filtering"]    = analyze_filtering(bgr)
    results["edges"]        = analyze_edges(bgr)
    results["morphology"]   = analyze_morphology(bgr)
    results["keypoints"]    = analyze_keypoints(bgr)
    results["hog"]          = analyze_hog(bgr)

    if bgr2 is not None:
        results["optical_flow"] = analyze_optical_flow(bgr, bgr2)
    else:
        # Simulate motion by translating the frame slightly
        h, w = bgr.shape[:2]
        M = np.float32([[1, 0, 5], [0, 1, 3]])   # 5px right, 3px down
        bgr2_sim = cv2.warpAffine(bgr, M, (w, h))
        results["optical_flow"] = analyze_optical_flow(bgr, bgr2_sim)

    return results
