import json
import math
import subprocess
from pathlib import Path


def incoming_file(root: Path, relative: str) -> Path:
    root = root.resolve()
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root):
        raise ValueError("path must stay inside data/incoming")
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("incoming file is missing or empty")
    return path


def probe_video(path: Path, ffprobe: str) -> dict:
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError as exc:
        raise ValueError("ffprobe is required; use the supplied worker container") from exc
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError("ffprobe could not read this video") from exc
    info = json.loads(result.stdout)
    if not any(s.get("codec_type") == "video" for s in info.get("streams", [])):
        raise ValueError("file does not contain a video stream")
    duration = float(info.get("format", {}).get("duration", 0))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("video must have a finite positive duration")
    return {"duration_s": duration, "probe": info}
