"""Verified IndEgo dataset manifest: the real 25 videos, usable without the database.

The manifest is produced by ``scripts/build_indego_manifest.py`` from the pinned
verification report and re-checked against Hugging Face before publication.
Nothing here decodes media; it only resolves identifiers to canonical URLs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "static" / "indego_manifest.json"

# The IndEgo release is pinned so identical inputs always resolve to identical bytes.
DATASET_URL = "https://huggingface.co/datasets/FraunhoferIPK/IndEgo"


class ManifestError(RuntimeError):
    """Raised when a requested video is not part of the verified manifest."""


@dataclass(frozen=True)
class VideoEntry:
    stem: str
    title: str
    category: str
    path: str
    source_uri: str
    duration_s: float
    keysteps: int
    width: int
    height: int
    license: str

    @property
    def proxy_path(self) -> str:
        """Same-origin path the browser reads for seekable playback."""
        return f"/api/v1/media/proxy?url={quote(self.source_uri, safe='')}"


@dataclass(frozen=True)
class Manifest:
    dataset: str
    revision: str
    license: str
    videos: tuple[VideoEntry, ...]

    def get(self, stem: str) -> VideoEntry:
        for video in self.videos:
            if video.stem == stem:
                return video
        raise ManifestError(f"unknown video stem: {stem}")

    @property
    def total_duration_s(self) -> float:
        return round(sum(video.duration_s for video in self.videos), 2)


@lru_cache(maxsize=1)
def load_manifest() -> Manifest:
    if not MANIFEST_PATH.exists():
        raise ManifestError(
            "indego_manifest.json is missing; run scripts/build_indego_manifest.py"
        )
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    videos = tuple(
        VideoEntry(
            stem=item["stem"],
            title=item["title"],
            category=item["category"],
            path=item["path"],
            source_uri=item["source_uri"],
            duration_s=float(item["duration_s"]),
            keysteps=int(item.get("keysteps", 0)),
            width=int(item.get("width", 480)),
            height=int(item.get("height", 480)),
            license=item.get("license", "CC-BY-4.0"),
        )
        for item in payload["videos"]
    )
    if not videos:
        raise ManifestError("manifest contains no videos")
    return Manifest(
        dataset=payload["dataset"],
        revision=payload["revision"],
        license=payload["license"],
        videos=videos,
    )
