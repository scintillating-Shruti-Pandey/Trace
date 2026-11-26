"""IVP analysis service: runs classical computer vision on real IndEgo footage.

Three entry points share one response envelope so the UI has a single code path:

* `analyze_dataset_frame` - a real frame decoded from an IndEgo video at time t.
* `analyze_upload`        - a frame the user supplied (multipart upload).
* `analyze_dataset_range` - a real time window: sampled frames, inter-frame
  difference keyframe selection, and optical flow between consecutive frames.

Everything runs locally with OpenCV; no paid API and no network beyond the
dataset byte ranges ffmpeg pulls through TRACE's media proxy.
"""

from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np

from app.ivp import processing
from app.ivp.frames import FrameError, FrameRequest, frame_png, grab_frames
from app.ivp.manifest import ManifestError, load_manifest

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_RANGE_SECONDS = 90.0
MAX_RANGE_FRAMES = 24


def _bgr_from_bytes(data: bytes) -> np.ndarray:
    if not data:
        raise FrameError("uploaded frame is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise FrameError("uploaded frame exceeds the 8 MB limit")
    array = np.frombuffer(data, dtype=np.uint8)
    bgr = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if bgr is None:
        raise FrameError("could not decode the uploaded image as JPEG/PNG")
    return bgr


def _source(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def _bundle(
    bgr: np.ndarray, source: dict[str, Any], second: np.ndarray | None
) -> dict[str, Any]:
    started = time.perf_counter()
    results = processing.run_full_ivp_pipeline(bgr, second)
    height, width = bgr.shape[:2]
    return {
        "source": {**source, "width": int(width), "height": int(height)},
        "techniques": results,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
    }


def analyze_dataset_frame(stem: str, timestamp_s: float, width: int = 640) -> dict[str, Any]:
    """Run every technique on one real frame taken from an IndEgo video."""
    entry = load_manifest().get(stem)
    timestamp = min(max(timestamp_s, 0.0), max(entry.duration_s - 0.05, 0.0))
    frames = grab_frames(
        FrameRequest(stem=stem, start_s=timestamp, count=1, fps=1.0, width=width)
    )
    source = _source(
        "indego",
        stem=entry.stem,
        title=entry.title,
        category=entry.category,
        timestamp_s=round(timestamp, 3),
        license=entry.license,
        provenance="huggingface: FraunhoferIPK/IndEgo (pinned revision)",
    )
    return _bundle(frames[0], source, None)


def analyze_upload(data: bytes, label: str = "uploaded frame") -> dict[str, Any]:
    bgr = _bgr_from_bytes(data)
    return _bundle(bgr, _source("upload", title=label), None)


def analyze_dataset_range(
    stem: str,
    start_s: float,
    end_s: float,
    *,
    fps: float = 2.0,
    width: int = 640,
    diff_threshold: float = 15.0,
    min_interval_s: float = 2.0,
) -> dict[str, Any]:
    """Sample a real time window and derive keyframes plus optical flow."""
    entry = load_manifest().get(stem)
    start = min(max(start_s, 0.0), entry.duration_s)
    stop = min(max(end_s, start + 1.0), entry.duration_s, start + MAX_RANGE_SECONDS)
    span = max(stop - start, 1.0)
    sample_fps = max(min(fps, 4.0), 0.25)
    count = int(min(max(span * sample_fps, 2), MAX_RANGE_FRAMES))

    frames = grab_frames(
        FrameRequest(stem=stem, start_s=start, count=count, fps=sample_fps, width=width)
    )
    if len(frames) < 2:
        raise FrameError("the requested window yielded fewer than two frames")

    grays = [processing._to_gray(frame) for frame in frames]
    diffs = [
        float(cv2.absdiff(grays[index], grays[index - 1]).mean())
        for index in range(1, len(grays))
    ]

    keyframes: list[dict[str, Any]] = []
    last_index = -10**6
    min_gap = max(int(round(min_interval_s * sample_fps)), 1)
    for index in range(1, len(grays)):
        diff = diffs[index - 1]
        if diff > diff_threshold and (index - last_index) >= min_gap:
            edge_map = cv2.Canny(cv2.GaussianBlur(grays[index], (5, 5), 0), 50, 150)
            keyframes.append(
                {
                    "frame_index": index,
                    "timestamp_s": round(start + index / sample_fps, 2),
                    "inter_frame_diff": round(diff, 2),
                    "edge_density_pct": round(
                        float(np.count_nonzero(edge_map)) / edge_map.size * 100, 3
                    ),
                    "sharpness": round(
                        float(cv2.Laplacian(grays[index], cv2.CV_64F).var()), 2
                    ),
                    "image_png_b64": processing._encode_png(frames[index]),
                }
            )
            last_index = index

    motion = processing.analyze_optical_flow(frames[0], frames[1])

    return {
        "source": _source(
            "indego",
            stem=entry.stem,
            title=entry.title,
            category=entry.category,
            license=entry.license,
            provenance="huggingface: FraunhoferIPK/IndEgo (pinned revision)",
        ),
        "range": {
            "start_s": round(start, 2),
            "end_s": round(stop, 2),
            "sample_fps": sample_fps,
            "frames_analyzed": len(frames),
            "capped": (stop - start) < (end_s - start_s) - 0.01,
        },
        "keyframes": keyframes,
        "motion": motion,
        "metrics": {
            "keyframes_selected": len(keyframes),
            "mean_inter_frame_diff": round(float(np.mean(diffs)), 3),
            "diff_threshold": diff_threshold,
            "min_interval_s": min_interval_s,
            "mean_flow_magnitude": motion["metrics"]["mean_flow_magnitude"],
            "max_flow_magnitude": motion["metrics"]["max_flow_magnitude"],
            "motion_active": motion["metrics"]["motion_active"],
        },
    }


def dataset_overview() -> dict[str, Any]:
    manifest = load_manifest()
    return {
        "dataset": manifest.dataset,
        "revision": manifest.revision,
        "license": manifest.license,
        "total_videos": len(manifest.videos),
        "total_duration_s": manifest.total_duration_s,
        "videos": [
            {
                "stem": video.stem,
                "title": video.title,
                "category": video.category,
                "duration_s": video.duration_s,
                "keysteps": video.keysteps,
                "proxy_path": video.proxy_path,
            }
            for video in manifest.videos
        ],
    }


def frame_metadata(stem: str, timestamp_s: float, width: int = 640) -> dict[str, Any]:
    _, meta = frame_png(stem, timestamp_s, width)
    return meta


__all__ = [
    "FrameError",
    "ManifestError",
    "analyze_dataset_frame",
    "analyze_dataset_range",
    "analyze_upload",
    "dataset_overview",
    "frame_metadata",
]
