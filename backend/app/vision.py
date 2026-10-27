"""SigLIP 2 Visual Embedder Client for Phase 3 Image Retrieval.

Strictly adheres to records/ENGINEERING_SPEC.md §7.1, §7.2, and §16.4:
- Interacts with the local GPU-accelerated SigLIP 2 microservice on port 8002.
- Handles text embedding (for visual-text search queries) and image embedding.
- Outputs 1,152-dimensional normalized vectors matching pgvector vec_image and vec_segment_visual.
"""

import base64
import math
import urllib.parse
from dataclasses import dataclass
from typing import Any

import httpx

MODEL = "google/siglip2-so400m-patch14-384"
DIMENSIONS = 1152
DEFAULT_ENDPOINT = "http://127.0.0.1:8002"


class VisualEmbeddingError(RuntimeError):
    """Sanitized error for visual embeddings."""


def is_local_endpoint(endpoint: str) -> bool:
    parsed = urllib.parse.urlparse(endpoint)
    host = (parsed.hostname or "").lower()
    return host in ("localhost", "127.0.0.1", "host.docker.internal", "::1")


@dataclass(frozen=True)
class VisualEmbeddingBatch:
    vectors: tuple[tuple[float, ...], ...]
    model: str = MODEL
    dim: int = DIMENSIONS


class SiglipVisualClient:
    def __init__(
        self,
        endpoint: str = DEFAULT_ENDPOINT,
        *,
        timeout_s: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self._endpoint = endpoint.rstrip("/")
        self._timeout_s = timeout_s
        self._transport = transport

    def embed_texts(self, texts: list[str]) -> VisualEmbeddingBatch:
        """Embed text queries into 1,152-d SigLIP 2 visual space."""
        if not texts:
            raise ValueError("texts list cannot be empty")

        url = f"{self._endpoint}/v1/visual/embed_text"
        with httpx.Client(timeout=self._timeout_s, transport=self._transport) as client:
            resp = client.post(url, json={"texts": texts})
            if resp.status_code != 200:
                raise VisualEmbeddingError(f"HTTP {resp.status_code}: {resp.text}")
            data = resp.json()

        vectors = self._validate_vectors(data.get("vectors"), len(texts))
        return VisualEmbeddingBatch(vectors=vectors)

    def embed_images(self, image_bytes_list: list[bytes]) -> VisualEmbeddingBatch:
        """Embed raw image bytes into 1,152-d SigLIP 2 visual space."""
        if not image_bytes_list:
            raise ValueError("image_bytes_list cannot be empty")

        b64_list = [base64.b64encode(b).decode("utf-8") for b in image_bytes_list]
        url = f"{self._endpoint}/v1/visual/embed_image"
        with httpx.Client(timeout=self._timeout_s, transport=self._transport) as client:
            resp = client.post(url, json={"images_base64": b64_list})
            if resp.status_code != 200:
                raise VisualEmbeddingError(f"HTTP {resp.status_code}: {resp.text}")
            data = resp.json()

        vectors = self._validate_vectors(data.get("vectors"), len(image_bytes_list))
        return VisualEmbeddingBatch(vectors=vectors)

    def _validate_vectors(self, raw_vectors: Any, expected_count: int) -> tuple[tuple[float, ...], ...]:
        if not isinstance(raw_vectors, list) or len(raw_vectors) != expected_count:
            raise VisualEmbeddingError(f"Expected {expected_count} vectors, got {type(raw_vectors)}")

        validated = []
        for v in raw_vectors:
            if not isinstance(v, list) or len(v) != DIMENSIONS:
                raise VisualEmbeddingError(f"Expected {DIMENSIONS}-d vector, got {len(v) if isinstance(v, list) else type(v)}")
            if any(not math.isfinite(x) for x in v):
                raise VisualEmbeddingError("Vector contains non-finite numbers (NaN/Inf)")
            norm = math.hypot(*v)
            if norm == 0 or not math.isfinite(norm):
                raise VisualEmbeddingError("Zero or invalid vector norm")
            validated.append(tuple(x / norm for x in v))

        return tuple(validated)
