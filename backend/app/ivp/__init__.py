"""Image and Video Processing (IVP) pipeline for TRACE.

Implements classical computer vision techniques applied to industrial video frames:
- Color space conversion (RGB → Grayscale, HSV, LAB)
- Histogram analysis and equalization (CLAHE)
- Gaussian blur and image filtering (convolution)
- Edge detection: Sobel (X/Y/magnitude) and Canny
- Morphological operations: erosion, dilation, opening, closing, gradient
- SIFT/ORB keypoint detection and feature description
- Dense Optical Flow (Farneback) for motion estimation
- HOG (Histogram of Oriented Gradients) feature extraction
- Keyframe extraction from video using inter-frame difference
"""
