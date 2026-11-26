"""Catalog of the classical IVP techniques TRACE exposes to the lab UI.

Kept separate from `processing.py` so the UI can render the syllabus
(grouping, theory, operator maths, parameters) without running OpenCV.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Technique:
    key: str
    name: str
    group: str
    operator: str
    summary: str
    parameters: tuple[str, ...]
    outputs: tuple[str, ...]


TECHNIQUES: tuple[Technique, ...] = (
    Technique(
        key="color_spaces",
        name="Color Space Conversion",
        group="Representation",
        operator="BGR → GRAY / HSV / LAB",
        summary=(
            "Decomposes each frame into luminance, hue-saturation, and perceptually "
            "uniform channels. Industrial inspection depends on this: thresholding "
            "is reliable in HSV where illumination varies, and in LAB where Euclidean "
            "distance approximates human colour difference."
        ),
        parameters=("source frame",),
        outputs=("original_rgb", "grayscale", "hsv", "lab"),
    ),
    Technique(
        key="histograms",
        name="Histograms & CLAHE",
        group="Representation",
        operator="hist(I), CLAHE(L)",
        summary=(
            "The histogram estimates the intensity distribution. CLAHE equalises "
            "contrast over 8×8 tiles with a clip limit, revealing detail in shadowed "
            "workshop regions and on specular metal without amplifying global noise."
        ),
        parameters=("clipLimit=2.0", "tileGridSize=8×8"),
        outputs=("original", "clahe_equalized", "gray_equalized"),
    ),
    Technique(
        key="filtering",
        name="Convolution & Filtering",
        group="Spatial domain",
        operator="I ⊛ K",
        summary=(
            "Every linear filter is a kernel slid over the image. Gaussian kernels "
            "suppress high-frequency noise; the Laplacian is a second-derivative "
            "operator that isolates rapid intensity change, the basis of sharpness "
            "scoring and defect boundaries."
        ),
        parameters=("kernel 3×3 / 7×7 / 15×15",),
        outputs=("gaussian_blur_3", "gaussian_blur_7", "sharpened", "laplacian"),
    ),
    Technique(
        key="edges",
        name="Gradient & Edge Detection",
        group="Spatial domain",
        operator="Sobel ∂/∂x, ∂/∂y → |∇I| → Canny",
        summary=(
            "Sobel approximates the image gradient, whose magnitude marks intensity "
            "transitions and whose direction is perpendicular to the edge. Canny adds "
            "non-maximum suppression and hysteresis to yield one-pixel-wide chains."
        ),
        parameters=("Canny 20/80, 50/150, 100/200",),
        outputs=("sobel_x", "sobel_y", "sobel_magnitude", "canny_medium"),
    ),
    Technique(
        key="morphology",
        name="Morphological Operators",
        group="Shape",
        operator="A ⊖ B, A ⊕ B, (A⊕B) − (A⊖B)",
        summary=(
            "Set operations on a binarised image. Erosion removes speckle, dilation "
            "closes gaps, opening denoises while preserving shape, and the "
            "morphological gradient extracts object outlines."
        ),
        parameters=("Otsu threshold", "elliptical structuring elements 3×3, 7×7"),
        outputs=("binary_otsu", "eroded", "dilated", "opened", "closed", "gradient"),
    ),
    Technique(
        key="keypoints",
        name="SIFT & ORB Keypoints",
        group="Features",
        operator="DoG extrema → 128-D descriptor / FAST+BRIEF → 32 B",
        summary=(
            "SIFT finds scale-space extrema and describes each with a 128-D "
            "gradient histogram, invariant to scale, rotation, and illumination. "
            "ORB pairs FAST corners with a rotated BRIEF descriptor for real-time "
            "matching. Both underpin frame-to-frame part tracking."
        ),
        parameters=("nfeatures=500",),
        outputs=("sift_keypoints", "orb_keypoints"),
    ),
    Technique(
        key="hog",
        name="Histogram of Oriented Gradients",
        group="Features",
        operator="cell histogram → block L2-normalisation",
        summary=(
            "Gradients are binned by orientation into 8×8 cells, then L2-normalised "
            "across overlapping 16×16 blocks, producing a 3,780-D shape descriptor. "
            "It was the pre-deep-learning standard for object detection and remains a "
            "strong low-cost baseline for workpiece classification."
        ),
        parameters=("128×64 window", "8×8 cells", "9 bins"),
        outputs=("original_resized", "hog_visualization"),
    ),
    Technique(
        key="optical_flow",
        name="Optical Flow (LK & Farneback)",
        group="Motion",
        operator="I(x+u, y+v, t+1) = I(x, y, t)",
        summary=(
            "Estimates per-pixel apparent motion between consecutive frames. "
            "Lucas-Kanade solves the flow locally for sparse Shi-Tomasi corners; "
            "Farneback fits a quadratic polynomial per neighbourhood for a dense "
            "field. Flow magnitude separates active assembly from idle time."
        ),
        parameters=("LK window 15×15, 3 pyramid levels", "Farneback 3 levels"),
        outputs=("frame1", "frame2", "lk_sparse_flow", "dense_flow_hsv"),
    ),
    Technique(
        key="keyframes",
        name="Keyframe Extraction",
        group="Motion",
        operator="mean |Iₜ − Iₜ₋ₙ| > τ",
        summary=(
            "A frame becomes a keyframe when its mean absolute difference from the "
            "last accepted keyframe exceeds a threshold, with a minimum temporal "
            "spacing. This is the exact rule TRACE used to populate the keyframe "
            "index from the IndEgo assembly videos."
        ),
        parameters=("τ=15.0", "min interval 2.0 s"),
        outputs=("keyframe thumbnails",),
    ),
)

GROUPS: tuple[str, ...] = tuple(dict.fromkeys(t.group for t in TECHNIQUES))


def catalog() -> dict[str, object]:
    return {
        "groups": list(GROUPS),
        "techniques": [asdict(technique) for technique in TECHNIQUES],
    }
