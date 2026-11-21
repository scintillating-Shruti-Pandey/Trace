#!/usr/bin/env python3
"""TRACE IVP Demo — runs the full Image & Video Processing pipeline.

Usage:
    python scripts/ivp_demo.py                      # uses synthetic test frame
    python scripts/ivp_demo.py --image path/to.jpg  # on a real image
    python scripts/ivp_demo.py --video path/to.mp4  # extracts keyframes from video

Output:
    ivp_results/  — folder of PNG images for every technique
    ivp_results/report.html — self-contained HTML report (open in browser)

Requirements:
    pip install opencv-python-headless numpy
"""

import argparse
import base64
import os
import sys

import cv2
import numpy as np

# Allow running from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.ivp.processing import (
    analyze_color_spaces,
    analyze_edges,
    analyze_filtering,
    analyze_histograms,
    analyze_hog,
    analyze_keypoints,
    analyze_morphology,
    analyze_optical_flow,
    extract_keyframes,
    run_full_ivp_pipeline,
)


# ---------------------------------------------------------------------------
# Synthetic test frame — industrial-looking grayscale gradient + shapes
# ---------------------------------------------------------------------------

def make_synthetic_frame(w: int = 640, h: int = 480) -> np.ndarray:
    """Generate a synthetic industrial-looking test frame with no external files."""
    frame = np.zeros((h, w, 3), dtype=np.uint8)

    # Background gradient (dark slate)
    for y in range(h):
        v = int(20 + (y / h) * 40)
        frame[y, :] = (v, v + 5, v + 2)

    # Simulate metal workpiece — large grey rectangle
    cv2.rectangle(frame, (80, 100), (560, 380), (120, 115, 110), -1)
    # Surface texture — noise
    noise = np.random.randint(0, 20, (280, 480, 3), dtype=np.uint8)
    frame[100:380, 80:560] = cv2.add(frame[100:380, 80:560], noise)

    # Simulate bolt holes (dark circles)
    for cx, cy in [(160, 180), (480, 180), (160, 300), (480, 300), (320, 240)]:
        cv2.circle(frame, (cx, cy), 18, (30, 28, 25), -1)
        cv2.circle(frame, (cx, cy), 14, (20, 18, 16), -1)
        cv2.circle(frame, (cx, cy),  6, (60, 55, 50), -1)

    # Simulate aluminum extrusion T-slot edges
    for y in [140, 200, 260, 320]:
        cv2.line(frame, (80, y), (560, y), (170, 165, 160), 2)
    for x in [160, 240, 320, 400, 480]:
        cv2.line(frame, (x, 100), (x, 380), (170, 165, 160), 1)

    # Simulate fastener highlights
    for cx, cy in [(200, 160), (440, 160), (200, 320), (440, 320)]:
        cv2.circle(frame, (cx, cy), 10, (200, 190, 180), -1)
        cv2.circle(frame, (cx, cy),  5, (230, 225, 220), -1)

    # Simulate tool shadow
    cv2.ellipse(frame, (320, 420), (80, 20), 0, 0, 180, (10, 10, 10), -1)

    # Text label
    cv2.putText(frame, "TRACE IVP TEST FRAME", (120, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
    cv2.putText(frame, "Industrial Assembly Workpiece", (140, 85),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 160, 160), 1)

    return frame


# ---------------------------------------------------------------------------
# HTML report generator
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>TRACE — IVP Analysis Report</title>
<style>
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 0; }}
  header {{ background: linear-gradient(135deg,#1e3a8a,#1e40af); padding: 32px 40px; }}
  header h1 {{ font-size: 2rem; margin: 0; color: #fff; }}
  header p  {{ color: #93c5fd; margin: 6px 0 0; font-size: 0.9rem; }}
  .section  {{ padding: 32px 40px; border-bottom: 1px solid #1e293b; }}
  .section h2 {{ color: #60a5fa; font-size: 1.3rem; margin: 0 0 6px; }}
  .section .tag {{ display:inline-block; background:#1e3a8a; color:#93c5fd;
                   padding:2px 10px; border-radius:4px; font-size:0.72rem;
                   font-weight:700; letter-spacing:.06em; margin-bottom:12px; }}
  .desc {{ color: #94a3b8; font-size: 0.85rem; line-height: 1.65; max-width: 820px; margin-bottom: 20px; }}
  .img-grid {{ display: flex; flex-wrap: wrap; gap: 14px; }}
  .img-box  {{ background: #1e293b; border-radius: 10px; padding: 10px;
               display: flex; flex-direction: column; align-items: center; }}
  .img-box img {{ max-width: 280px; max-height: 220px; border-radius: 6px; display: block; }}
  .img-box span {{ font-size: 0.7rem; color: #64748b; margin-top: 6px; font-family: monospace; }}
  .metrics {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 8px;
              padding: 14px 18px; margin-top: 16px; display: flex; flex-wrap: wrap; gap: 10px 32px; }}
  .metric {{ font-size: 0.78rem; }}
  .metric .k {{ color: #64748b; }}
  .metric .v {{ color: #34d399; font-weight: 600; font-family: monospace; }}
  footer {{ text-align: center; padding: 24px; color: #334155; font-size: 0.75rem; }}
</style>
</head>
<body>
<header>
  <h1>🔬 TRACE — Image &amp; Video Processing Analysis</h1>
  <p>Industrial Evidence Intelligence · Bennett University · 2026</p>
</header>
{sections}
<footer>Generated by TRACE IVP Pipeline · All processing local · Zero cloud · RTX 4050</footer>
</body>
</html>"""

SECTION_TEMPLATE = """
<div class="section">
  <div class="tag">TECHNIQUE {idx}</div>
  <h2>{name}</h2>
  <p class="desc">{desc}</p>
  <div class="img-grid">
    {images}
  </div>
  <div class="metrics">
    {metrics}
  </div>
</div>"""

IMG_TEMPLATE = '<div class="img-box"><img src="data:image/png;base64,{b64}" alt="{label}"><span>{label}</span></div>'
METRIC_TEMPLATE = '<div class="metric"><span class="k">{k}: </span><span class="v">{v}</span></div>'


def build_html_report(results: dict) -> str:
    sections = []
    for idx, (key, data) in enumerate(results.items(), 1):
        if "error" in data:
            continue
        images_html = "\n    ".join(
            IMG_TEMPLATE.format(b64=b64, label=label.replace("_", " ").title())
            for label, b64 in data.get("images", {}).items()
        )
        metrics = data.get("metrics", {})
        metrics_html = "\n    ".join(
            METRIC_TEMPLATE.format(k=k, v=(str(round(v, 4)) if isinstance(v, float) else str(v)))
            for k, v in metrics.items()
            if not isinstance(v, (list, dict))
        )
        sections.append(SECTION_TEMPLATE.format(
            idx=idx,
            name=data.get("technique", key),
            desc=data.get("description", ""),
            images=images_html,
            metrics=metrics_html,
        ))
    return HTML_TEMPLATE.format(sections="\n".join(sections))


# ---------------------------------------------------------------------------
# Save PNG images
# ---------------------------------------------------------------------------

def save_images(results: dict, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    for key, data in results.items():
        for label, b64 in data.get("images", {}).items():
            img_bytes = base64.b64decode(b64)
            path = os.path.join(out_dir, f"{key}__{label}.png")
            with open(path, "wb") as f:
                f.write(img_bytes)
            print(f"  saved: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="TRACE IVP pipeline demo")
    parser.add_argument("--image", help="Path to an image file (JPG/PNG)")
    parser.add_argument("--video", help="Path to a video file (MP4/AVI)")
    parser.add_argument("--out", default="ivp_results", help="Output directory")
    args = parser.parse_args()

    print("=" * 60)
    print("  TRACE — Image & Video Processing Pipeline")
    print("=" * 60)

    # Load or synthesize frame
    if args.image:
        bgr = cv2.imread(args.image)
        if bgr is None:
            print(f"[ERROR] Cannot read image: {args.image}")
            sys.exit(1)
        bgr = cv2.resize(bgr, (640, 480))
        print(f"[+] Loaded image: {args.image}  ({bgr.shape})")
    else:
        bgr = make_synthetic_frame()
        print("[+] Using synthetic industrial test frame (640×480)")

    # Run full pipeline
    print("\n[1/9] Running IVP pipeline...")
    results = run_full_ivp_pipeline(bgr)

    # Keyframe extraction (if video provided)
    if args.video:
        print(f"[+] Extracting keyframes from video: {args.video}")
        kf_result = extract_keyframes(args.video, diff_threshold=15.0, max_frames=20)
        results["keyframe_extraction"] = kf_result
        # Remove raw frame data from keyframes for the main results (keep metadata)
        for kf in kf_result.get("keyframes", []):
            kf.pop("image_png_b64", None)

    # Save output
    print(f"\n[2/9] Saving PNG images to {args.out}/...")
    save_images(results, args.out)

    # Build HTML report
    report_path = os.path.join(args.out, "report.html")
    print(f"[3/9] Building HTML report...")
    html = build_html_report(results)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✅ Done! Open in your browser:\n   {os.path.abspath(report_path)}")

    # Print metric summary
    print("\n--- METRIC SUMMARY ---")
    for key, data in results.items():
        m = data.get("metrics", {})
        print(f"\n{data.get('technique', key)}")
        for k, v in m.items():
            if not isinstance(v, (list, dict)):
                print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
