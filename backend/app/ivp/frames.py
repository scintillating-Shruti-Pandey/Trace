"""Extract real IndEgo frames server-side, in RAM, without caching media to disk.

The container's ffmpeg crashes (SIGSEGV) when it opens an HTTPS URL directly, so
frames are pulled through TRACE's own HTTP media proxy. ffmpeg writes raw RGB to
stdout, which this module decodes into NumPy arrays. No video or frame is ever
persisted; a small bounded LRU keeps recently used frames in memory only.
"""

from __future__ import annotations

import os
import subprocess
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock

import cv2
import numpy as np

from app.ivp.manifest import VideoEntry, load_manifest

# The API talks to itself over loopback so ffmpeg sees a plain-HTTP origin.
INTERNAL_BASE_URL = os.environ.get("TRACE_INTERNAL_URL", "http://127.0.0.1:8000")

DECODE_TIMEOUT_S = 90
MAX_CACHE_BYTES = 48 * 1024 * 1024
MAX_WIDTH = 960


class FrameError(RuntimeError):
    """Raised when a real frame cannot be decoded from the dataset."""


@dataclass(frozen=True)
class FrameRequest:
    stem: str
    start_s: float
    count: int = 1
    fps: float = 1.0
    width: int = 640


def _even(value: float) -> int:
    rounded = int(round(value))
    return max(2, rounded - (rounded % 2))


def _target_size(entry: VideoEntry, width: int) -> tuple[int, int]:
    target_w = _even(min(max(width, 160), MAX_WIDTH))
    aspect = entry.height / entry.width if entry.width else 1.0
    return target_w, _even(target_w * aspect)


def _source_url(entry: VideoEntry) -> str:
    return f"{INTERNAL_BASE_URL}{entry.proxy_path}"


def _ffmpeg_argv(
    url: str, *, start_s: float, count: int, fps: float, size: tuple[int, int]
) -> list[str]:
    width, height = size
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-nostdin",
        "-ss", f"{max(start_s, 0.0):.3f}",
        "-i", url,
        "-an",
        "-sn",
        "-frames:v", str(max(count, 1)),
        "-vf", f"fps={max(fps, 0.1)},scale={width}:{height}",
        "-pix_fmt", "rgb24",
        "-f", "rawvideo",
        "pipe:1",
    ]


def _decode_raw(buffer: bytes, size: tuple[int, int], count: int) -> list[np.ndarray]:
    width, height = size
    frame_bytes = width * height * 3
    usable = len(buffer) // frame_bytes
    if usable == 0:
        raise FrameError("decoder produced no complete frame")
    frames = []
    for index in range(min(usable, count)):
        chunk = buffer[index * frame_bytes : (index + 1) * frame_bytes]
        rgb = np.frombuffer(chunk, dtype=np.uint8).reshape(height, width, 3)
        frames.append(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    return frames


def grab_frames(request: FrameRequest) -> list[np.ndarray]:
    """Decode `count` real frames spaced 1/fps apart, starting at `start_s`."""
    entry = load_manifest().get(request.stem)
    size = _target_size(entry, request.width)
    argv = _ffmpeg_argv(
        _source_url(entry),
        start_s=request.start_s,
        count=request.count,
        fps=request.fps,
        size=size,
    )
    try:
        result = subprocess.run(argv, capture_output=True, timeout=DECODE_TIMEOUT_S)
    except FileNotFoundError as exc:
        raise FrameError("ffmpeg is unavailable in this runtime") from exc
    except subprocess.TimeoutExpired as exc:
        raise FrameError("frame extraction timed out") from exc
    if result.returncode != 0 or not result.stdout:
        detail = (result.stderr or b"").decode("utf-8", "ignore").strip().splitlines()
        reason = detail[-1] if detail else f"ffmpeg exit {result.returncode}"
        raise FrameError(reason)
    return _decode_raw(result.stdout, size, request.count)


def grab_audio_wav(stem: str, start_s: float, duration_s: float) -> bytes:
    """Decode a bounded mono 16 kHz WAV from a real IndEgo video into memory."""
    entry = load_manifest().get(stem)
    duration = min(max(duration_s, 0.0), 60.0, max(entry.duration_s - start_s, 0.0))
    if duration <= 0:
        raise FrameError("audio interval is empty or outside the source video")
    argv = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
        "-ss", f"{max(start_s, 0.0):.3f}", "-i", _source_url(entry),
        "-t", f"{duration:.3f}", "-vn", "-ac", "1", "-ar", "16000",
        "-f", "wav", "pipe:1",
    ]
    try:
        result = subprocess.run(argv, capture_output=True, timeout=DECODE_TIMEOUT_S)
    except FileNotFoundError as exc:
        raise FrameError("ffmpeg is unavailable in this runtime") from exc
    except subprocess.TimeoutExpired as exc:
        raise FrameError("audio extraction timed out") from exc
    if result.returncode != 0 or len(result.stdout) < 44:
        detail = (result.stderr or b"").decode("utf-8", "ignore").strip().splitlines()
        reason = detail[-1] if detail else "source has no decodable audio"
        raise FrameError(reason)
    return result.stdout


class _FrameCache:
    """Bounded in-memory cache of PNG-encoded frames keyed by (stem, t, width)."""

    def __init__(self) -> None:
        self._items: OrderedDict[tuple[str, int, int], bytes] = OrderedDict()
        self._bytes = 0
        self._lock = Lock()

    @staticmethod
    def _key(stem: str, timestamp_s: float, width: int) -> tuple[str, int, int]:
        # 0.25 s granularity keeps the cache useful across slider drags.
        return stem, int(round(timestamp_s * 4)), width

    def get(self, stem: str, timestamp_s: float, width: int) -> bytes | None:
        key = self._key(stem, timestamp_s, width)
        with self._lock:
            payload = self._items.get(key)
            if payload is not None:
                self._items.move_to_end(key)
            return payload

    def put(self, stem: str, timestamp_s: float, width: int, payload: bytes) -> None:
        key = self._key(stem, timestamp_s, width)
        with self._lock:
            if key in self._items:
                self._items.move_to_end(key)
                return
            self._items[key] = payload
            self._bytes += len(payload)
            while self._bytes > MAX_CACHE_BYTES and len(self._items) > 1:
                _, evicted = self._items.popitem(last=False)
                self._bytes -= len(evicted)


_CACHE = _FrameCache()


def _encode_png(image: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".png", image, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    if not ok:
        raise FrameError("PNG encoding failed")
    return bytes(buffer)


def frame_png(stem: str, timestamp_s: float, width: int = 640) -> tuple[bytes, dict[str, object]]:
    """Return a real dataset frame as PNG plus provenance metadata."""
    entry = load_manifest().get(stem)
    timestamp = min(max(timestamp_s, 0.0), max(entry.duration_s - 0.05, 0.0))
    cached = _CACHE.get(stem, timestamp, width)
    if cached is not None:
        return cached, {
            "stem": entry.stem,
            "title": entry.title,
            "category": entry.category,
            "timestamp_s": round(timestamp, 3),
            "width": _target_size(entry, width)[0],
            "cached": True,
            "source": "huggingface:IndEgo (real dataset frame)",
        }
    frames = grab_frames(
        FrameRequest(stem=stem, start_s=timestamp, count=1, fps=1.0, width=width)
    )
    payload = _encode_png(frames[0])
    _CACHE.put(stem, timestamp, width, payload)
    height, width_px = frames[0].shape[:2]
    return payload, {
        "stem": entry.stem,
        "title": entry.title,
        "category": entry.category,
        "timestamp_s": round(timestamp, 3),
        "width": width_px,
        "height": height,
        "cached": False,
        "source": "huggingface:IndEgo (real dataset frame)",
    }
