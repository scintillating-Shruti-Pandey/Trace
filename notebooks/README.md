# TRACE — IVP Notebooks

This folder contains Image & Video Processing lab notebooks for the TRACE project.

## `ivp_analysis.ipynb`

A complete, self-contained Jupyter notebook demonstrating **all classical IVP techniques** applied to industrial manufacturing frames.

### Techniques demonstrated

| # | Technique | Key functions |
|---|---|---|
| 1 | Color Space Conversion | `cv2.cvtColor` → Grayscale, HSV, LAB |
| 2 | Histogram Analysis & CLAHE | `cv2.calcHist`, `cv2.createCLAHE` |
| 3 | Convolution & Filtering | `cv2.GaussianBlur`, `cv2.filter2D`, `cv2.Laplacian` |
| 4 | Edge Detection | `cv2.Sobel`, `cv2.Canny` |
| 5 | Morphological Operations | `cv2.erode`, `cv2.dilate`, `cv2.morphologyEx` |
| 6 | Feature Detection (SIFT + ORB) | `cv2.SIFT_create`, `cv2.ORB_create` |
| 7 | Optical Flow | `cv2.calcOpticalFlowPyrLK`, `cv2.calcOpticalFlowFarneback` |
| 8 | HOG Features | `cv2.HOGDescriptor` |
| 9 | Keyframe Extraction | Inter-frame difference thresholding |

### How to run

```powershell
# Install dependencies (one time)
pip install opencv-python-headless numpy matplotlib jupyter ipykernel

# Launch Jupyter
jupyter notebook notebooks/ivp_analysis.ipynb
```

### Using your own image or video

At the top of the notebook, set:
```python
IMAGE_PATH = "path/to/your/image.jpg"   # any JPEG/PNG
VIDEO_PATH = "path/to/your/video.mp4"   # any MP4/AVI
```

If you leave both as `None`, a synthetic industrial test frame is generated automatically.

---

## `scripts/ivp_demo.py`

Standalone script version — generates an HTML report with all technique outputs.

```powershell
# Synthetic frame (no files needed)
python scripts/ivp_demo.py

# Real image
python scripts/ivp_demo.py --image path/to/image.jpg

# Real video (also extracts keyframes)
python scripts/ivp_demo.py --video path/to/video.mp4

# Output goes to ivp_results/report.html — open in browser
```

---

## Integration with TRACE

These techniques are not isolated demos — they are the **classical foundation** of TRACE's visual pipeline:

- **Keyframe extraction** populates `images` table (114 frames from 25 IndEgo videos)
- **Edge density** is used as a frame quality/complexity score
- **Optical flow magnitude** marks high-motion assembly intervals for segment boundaries
- **CLAHE** pre-processes frames before SigLIP 2 visual embedding
- **SIFT/ORB** enables cross-frame feature matching across shots
- **HOG** provides a fast shape descriptor for workpiece classification baseline

The deep learning models (SigLIP 2, BGE-M3) are themselves built on the mathematical foundations established by these classical techniques — convolution, gradient computation, feature histograms.
