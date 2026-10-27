"""BGE-M3 adapter supporting local GPU inference and remote endpoints.

Supports:
- Local offline microservice (http://host.docker.internal:8001 or http://localhost:8001)
- Direct in-process local execution (LocalBgeM3Direct) when ML packages are available
- Hosted provider fallback (BgeM3Client with DEEPINFRA_API_KEY)
"""

import json
import math
import time
import urllib.parse
from dataclasses import dataclass

import httpx
from pydantic import SecretStr

MODEL = "BAAI/bge-m3"
ENDPOINT = "https://api.deepinfra.com/v1/openai/embeddings"
DIMENSIONS = 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class EmbeddingError(RuntimeError):
    """Sanitized error: never includes input text, credentials or response bodies."""


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: tuple[tuple[float, ...], ...]
    prompt_tokens: int
    total_tokens: int
    attempts: int
    model: str = MODEL
    provider: str = "deepinfra"
    normalization: str = "l2"
    # Model identifier is not evidence of a pinned weight revision.
    revision: str | None = None


def is_local_endpoint(endpoint: str) -> bool:
    """Return True if the endpoint URL points to a local host address."""
    parsed = urllib.parse.urlparse(endpoint)
    host = (parsed.hostname or "").lower()
    return host in ("localhost", "127.0.0.1", "host.docker.internal", "::1")


def _parse(
    payload: object, count: int, attempts: int, provider: str = "deepinfra"
) -> EmbeddingBatch:
    try:
        if not isinstance(payload, dict) or payload.get("model") != MODEL:
            raise ValueError
        rows = payload["data"]
        if not isinstance(rows, list) or len(rows) != count:
            raise ValueError
        ordered = {}
        for row in rows:
            index, vector = row["index"], row["embedding"]
            if type(index) is not int or not 0 <= index < count or index in ordered:
                raise ValueError
            if not isinstance(vector, list) or len(vector) != DIMENSIONS:
                raise ValueError
            if any(type(x) not in (int, float) or not math.isfinite(x) for x in vector):
                raise ValueError
            norm = math.hypot(*vector)
            if not math.isfinite(norm) or norm == 0:
                raise ValueError
            ordered[index] = tuple(x / norm for x in vector)
        usage = payload["usage"]
        prompt, total = usage["prompt_tokens"], usage["total_tokens"]
        if type(prompt) is not int or type(total) is not int or not 0 <= prompt <= total:
            raise ValueError
        return EmbeddingBatch(
            tuple(ordered[i] for i in range(count)),
            prompt,
            total,
            attempts,
            provider=provider,
        )
    except (KeyError, TypeError, ValueError, OverflowError):
        raise EmbeddingError("Invalid embedding response schema, vectors, model or usage") from None


class BgeM3Client:
    def __init__(
        self,
        api_key: SecretStr | None = None,
        *,
        endpoint: str | None = None,
        rate_limit_retries: int = 0,
        transport: httpx.BaseTransport | None = None,
    ):
        self._endpoint = endpoint or ENDPOINT
        self._is_local = is_local_endpoint(self._endpoint)
        if not self._is_local and (api_key is None or not api_key.get_secret_value().strip()):
            raise EmbeddingError("Set DEEPINFRA_API_KEY before requesting embeddings")
        if type(rate_limit_retries) is not int or not 0 <= rate_limit_retries <= 2:
            raise ValueError("rate_limit_retries must be 0, 1 or 2")
        self._key = api_key
        self._retries = rate_limit_retries
        self._transport = transport
        self._provider = "local" if self._is_local else "deepinfra"

    def embed(self, texts: list[str]) -> EmbeddingBatch:
        # Conservative byte guard, not a tokenizer or permission to silently truncate.
        if (
            not isinstance(texts, list)
            or not 1 <= len(texts) <= 16
            or any(not isinstance(t, str) or not t.strip() for t in texts)
        ):
            raise ValueError("Expected 1–16 nonempty text strings")
        if any(len(t.encode("utf-8")) > 4096 for t in texts):
            raise ValueError("Each text must fit within 4096 UTF-8 bytes; chunk it explicitly")

        headers = {}
        if self._key is not None and self._key.get_secret_value().strip():
            headers["Authorization"] = f"Bearer {self._key.get_secret_value()}"

        with httpx.Client(
            timeout=httpx.Timeout(30, connect=5),
            follow_redirects=False,
            trust_env=False,
            transport=self._transport,
        ) as client:
            for attempt in range(self._retries + 1):
                delay = None
                try:
                    with client.stream(
                        "POST",
                        self._endpoint,
                        headers=headers,
                        json={"model": MODEL, "input": texts, "encoding_format": "float"},
                    ) as response:
                        if response.status_code == 429 and attempt < self._retries:
                            try:
                                delay = float(response.headers.get("retry-after", "1"))
                            except ValueError:
                                delay = None
                            # Long/HTTP-date Retry-After values require caller rescheduling.
                            if delay is None or not math.isfinite(delay) or not 0 <= delay <= 10:
                                raise EmbeddingError("Rate limited; retry later")
                        elif response.status_code != 200:
                            raise EmbeddingError(f"Embedding provider HTTP {response.status_code}")
                        else:
                            raw = bytearray()
                            for chunk in response.iter_bytes(chunk_size=8192):
                                raw.extend(chunk)
                                if len(raw) > MAX_RESPONSE_BYTES:
                                    raise EmbeddingError("Embedding response exceeds size limit")
                            try:
                                payload = json.loads(raw)
                            except (ValueError, UnicodeError):
                                raise EmbeddingError(
                                    "Embedding response is not valid JSON"
                                ) from None
                            return _parse(payload, len(texts), attempt + 1, provider=self._provider)
                except httpx.HTTPError:
                    # A timeout/5xx can follow billable work: no automatic replay.
                    raise EmbeddingError(
                        "Embedding transport failed; request not replayed"
                    ) from None
                if delay is not None:
                    time.sleep(delay)
        raise EmbeddingError("Embedding request exhausted attempts")


class LocalBgeM3Direct:
    """In-process BGE-M3 runner for host scripts/benchmarks.

    Requires sentence_transformers and torch to be installed.
    """

    def __init__(self, device: str | None = None):
        try:
            import torch
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise EmbeddingError("sentence-transformers and torch required for LocalBgeM3Direct")

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self._device = device
        self._model = SentenceTransformer(
            MODEL,
            model_kwargs={"use_safetensors": True},
            device=device,
        )

    def embed(self, texts: list[str]) -> EmbeddingBatch:
        if (
            not isinstance(texts, list)
            or not 1 <= len(texts) <= 16
            or any(not isinstance(t, str) or not t.strip() for t in texts)
        ):
            raise ValueError("Expected 1–16 nonempty text strings")
        if any(len(t.encode("utf-8")) > 4096 for t in texts):
            raise ValueError("Each text must fit within 4096 UTF-8 bytes; chunk it explicitly")

        raw_vectors = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        vectors = tuple(tuple(float(x) for x in vec) for vec in raw_vectors)

        prompt_tokens = 0
        if hasattr(self._model, "tokenizer") and self._model.tokenizer is not None:
            try:
                tokens = self._model.tokenizer(texts, truncation=False)
                prompt_tokens = sum(len(ids) for ids in tokens["input_ids"])
            except Exception:
                prompt_tokens = sum(max(1, len(t) // 4) for t in texts)
        else:
            prompt_tokens = sum(max(1, len(t) // 4) for t in texts)

        return EmbeddingBatch(
            vectors=vectors,
            prompt_tokens=prompt_tokens,
            total_tokens=prompt_tokens,
            attempts=1,
            model=MODEL,
            provider="local",
        )
