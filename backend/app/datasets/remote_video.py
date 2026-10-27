"""Seekable, byte-budgeted remote MP4 decoding. No media files or disk caches.

FFmpeg reads a loopback proxy; the proxy validates each upstream byte range. Only
one pinned object is exposed, and fetched blocks live in a bounded RAM LRU cache.
"""

import hashlib
import json
import math
import re
import subprocess
import threading
from collections import OrderedDict
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.datasets.huggingface import RemoteAccessError

BLOCK = 256 * 1024


class RemoteObject:
    def __init__(self, url, size, *, budget=32 * 1024 * 1024):
        if size <= 0 or budget <= 0:
            raise ValueError("size and budget must be positive")
        self.url, self.size, self.budget = url, size, budget
        self.bytes_read = self.requests = 0
        self.cache = OrderedDict()
        self.lock = threading.Lock()
        self.error = None
        self.stopping = threading.Event()

    def block(self, index):
        with self.lock:
            if index in self.cache:
                self.cache.move_to_end(index)
                return self.cache[index]
            start = index * BLOCK
            end = min(start + BLOCK, self.size) - 1
            expected = end - start + 1
            if expected <= 0 or start < 0:
                raise RemoteAccessError("range outside object")
            if self.bytes_read + expected > self.budget:
                raise RemoteAccessError("video network byte budget exceeded")
            request = Request(
                self.url,
                headers={"Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"},
            )
            try:
                with urlopen(request, timeout=25) as response:
                    if response.status != 206 or response.headers.get("Content-Range") != (
                        f"bytes {start}-{end}/{self.size}"
                    ):
                        raise RemoteAccessError("server did not honor exact byte range")
                    data = response.read(expected)
                    self.bytes_read += len(data)
                    self.requests += 1
                    if len(data) != expected:
                        raise RemoteAccessError("short media byte range")
            except HTTPError as exc:
                raise RemoteAccessError(f"media HTTP {exc.code}", status=exc.code) from exc
            except (URLError, TimeoutError, OSError) as exc:
                raise RemoteAccessError("media network request failed") from exc
            self.cache[index] = data
            while len(self.cache) > 16:  # at most 4 MiB per active object
                self.cache.popitem(last=False)
            return data


@contextmanager
def serve_object(source):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_HEAD(self):
            self.send_response(200)
            self.send_header("Content-Length", str(source.size))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()

        def do_GET(self):
            if self.path != "/video.mp4":
                self.send_error(404)
                return
            raw = self.headers.get("Range")
            match = re.fullmatch(r"bytes=(\d+)-(\d*)", raw or "")
            if raw and not match:
                self.send_error(416)
                return
            start = int(match[1]) if match else 0
            end = min(int(match[2]), source.size - 1) if match and match[2] else source.size - 1
            if start > end or start >= source.size:
                self.send_error(416)
                return
            try:
                first = source.block(start // BLOCK)  # fail before writing response headers
                self.send_response(206 if match else 200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(end - start + 1))
                if match:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{source.size}")
                self.end_headers()
                position = start
                while position <= end and not source.stopping.is_set():
                    block = first if position == start else source.block(position // BLOCK)
                    offset = position % BLOCK
                    part = block[offset : offset + min(len(block) - offset, end - position + 1)]
                    self.wfile.write(part)
                    self.wfile.flush()
                    position += len(part)
            except (BrokenPipeError, ConnectionResetError):
                pass  # FFmpeg routinely closes a range after seeking or decoding a frame
            except RemoteAccessError as exc:
                source.error = str(exc)
                self.close_connection = True

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = False  # close waits for in-flight ranges before reporting byte totals
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/video.mp4"
    finally:
        source.stopping.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def run_decoder(args, *, timeout=60):
    try:
        result = subprocess.run(args, capture_output=True, timeout=timeout, check=True)
        return result.stdout
    except FileNotFoundError as exc:
        raise RemoteAccessError("ffmpeg/ffprobe missing; use the existing API image") from exc
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        # Avoid logging redirects, signed media URLs, or unbounded decoder diagnostics.
        raise RemoteAccessError("decoder failed or timed out") from exc


def verify_video(url, size, *, budget=32 * 1024 * 1024):
    source = RemoteObject(url, size, budget=budget)
    with serve_object(source) as local_url:
        info = json.loads(
            run_decoder(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_format",
                    "-show_streams",
                    "-of",
                    "json",
                    local_url,
                ]
            )
        )
        video = next((s for s in info["streams"] if s.get("codec_type") == "video"), None)
        duration = float(info.get("format", {}).get("duration", 0))
        if video is None or not math.isfinite(duration) or duration <= 0:
            raise RemoteAccessError("invalid video stream or duration")
        frames = []
        for fraction in (0.05, 0.5, 0.95):
            timestamp = round(duration * fraction, 3)
            pixels = run_decoder(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-nostdin",
                    "-threads",
                    "1",
                    "-ss",
                    str(timestamp),
                    "-i",
                    local_url,
                    "-map",
                    "0:v:0",
                    "-frames:v",
                    "1",
                    "-an",
                    "-sn",
                    "-vf",
                    "scale=96:96",
                    "-pix_fmt",
                    "rgb24",
                    "-f",
                    "rawvideo",
                    "pipe:1",
                ]
            )
            if len(pixels) != 96 * 96 * 3:
                raise RemoteAccessError("decoder did not produce a complete RGB frame")
            frames.append({"timestamp_s": timestamp, "sha256": hashlib.sha256(pixels).hexdigest()})
        if source.error:
            raise RemoteAccessError(source.error)
    return {
        "duration_s": duration,
        "width": video["width"],
        "height": video["height"],
        "codec": video["codec_name"],
        "frames": frames,
        "network_bytes": source.bytes_read,
        "range_requests": source.requests,
    }
