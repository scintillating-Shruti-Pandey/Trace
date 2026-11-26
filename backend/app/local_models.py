"""Optional, local-only AI helpers for TRACE.

These adapters never download model weights. Ollama calls are restricted to a
loopback/private host; faster-whisper must already be installed and its model
must already exist in the local cache. Callers can therefore fail closed with
an actionable prerequisite message instead of silently using a substitute.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

class LocalModelUnavailable(RuntimeError):
    """A requested local model or runtime is unavailable."""


def _require_local(endpoint: str) -> None:
    host = (urlparse(endpoint).hostname or "").lower()
    if host not in {"localhost", "127.0.0.1", "::1", "host.docker.internal"}:
        raise ValueError("TRACE AI adapters only allow local Ollama endpoints")


class OllamaClient:
    def __init__(self, endpoint: str, model: str, timeout_s: float = 90.0) -> None:
        _require_local(endpoint)
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s

    def chat(self, prompt: str, images: list[bytes] | None = None) -> str:
        try:
            import httpx
        except ImportError as exc:
            raise LocalModelUnavailable(
                "Local Ollama calls require the project's declared httpx dependency"
            ) from exc
        message: dict[str, Any] = {"role": "user", "content": prompt}
        if images:
            message["images"] = [base64.b64encode(image).decode("ascii") for image in images]
        try:
            response = httpx.post(
                f"{self.endpoint}/api/chat",
                json={"model": self.model, "messages": [message], "stream": False},
                timeout=self.timeout_s,
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise LocalModelUnavailable(
                f"Local Ollama model '{self.model}' is unavailable at {self.endpoint}"
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise LocalModelUnavailable("Local Ollama returned an empty response")
        return content.strip()


@dataclass(frozen=True)
class TimedWord:
    text: str
    start_s: float
    end_s: float


@dataclass(frozen=True)
class Transcription:
    text: str
    words: tuple[TimedWord, ...]
    model: str


class FasterWhisperTranscriber:
    """Lazy faster-whisper adapter; it does not fetch uncached weights."""

    def __init__(
        self,
        model_name: str = "large-v3",
        *,
        device: str = "cuda",
        compute_type: str = "int8_float16",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def transcribe(self, audio: bytes, *, language: str | None = None) -> Transcription:
        if not audio:
            return Transcription("", (), self.model_name)
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise LocalModelUnavailable(
                "ASR requires the optional faster-whisper package; it is not installed"
            ) from exc
        from io import BytesIO

        if self._model is None:
            try:
                self._model = WhisperModel(
                    self.model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                    local_files_only=True,
                )
            except TypeError as exc:
                raise LocalModelUnavailable(
                    "Installed faster-whisper must support local_files_only to prevent downloads"
                ) from exc
            except Exception as exc:
                raise LocalModelUnavailable(
                    f"ASR weights '{self.model_name}' are not available in the local cache"
                ) from exc
        try:
            segments, _info = self._model.transcribe(
                BytesIO(audio), language=language, word_timestamps=True, vad_filter=True
            )
            collected: list[TimedWord] = []
            texts: list[str] = []
            for segment in segments:
                texts.append(segment.text.strip())
                for word in segment.words or ():
                    collected.append(
                        TimedWord(word.word.strip(), float(word.start), float(word.end))
                    )
        except Exception as exc:
            raise LocalModelUnavailable("faster-whisper could not transcribe this audio") from exc
        return Transcription(" ".join(filter(None, texts)), tuple(collected), self.model_name)


def caption_frames(
    client: OllamaClient,
    frames: list[bytes],
    *,
    title: str,
    start_s: float,
    end_s: float,
    transcript: str = "",
) -> str:
    """Describe observed actions and objects in sampled frames; do not infer unseen detail."""
    if not frames:
        raise ValueError("captioning requires at least one decoded frame")
    prompt = (
        "Describe only visible actions, tools, components, and changes across these frames. "
        "Use concise, objective language. Do not infer equipment specifications or motives. "
        "If the action is unclear, say so. Optional audio transcript (may be noisy): "
        f"{transcript or '[none]'}. Video: {title}; interval {start_s:.1f}-{end_s:.1f}s."
    )
    return client.chat(prompt, frames)


class LocalQueryAnalyzer:
    """Produces bounded search rewrites and subquestions using the local Ollama model."""

    def __init__(self, client: OllamaClient, max_queries: int = 4) -> None:
        self.client = client
        self.max_queries = max(1, min(max_queries, 4))

    def analyze(self, query: str) -> list[str]:
        prompt = (
            "Rewrite the user's industrial maintenance search as up to three short, "
            "independent search queries that preserve the original intent. Do not answer. "
            "Return only a JSON object: {\"queries\":[...]}. Include the original meaning.\n"
            f"User query: {query}"
        )
        try:
            raw = self.client.chat(prompt)
            data = json.loads(raw)
            queries = data.get("queries") if isinstance(data, dict) else None
            if not isinstance(queries, list):
                return [query]
            clean = [q.strip() for q in queries if isinstance(q, str) and q.strip()]
            unique = list(dict.fromkeys([query.strip(), *clean]))
            return unique[: self.max_queries]
        except (LocalModelUnavailable, json.JSONDecodeError, AttributeError):
            return [query]


class LocalCandidateReranker:
    """Rerank a small candidate list with a local Ollama model, fail-soft."""

    def __init__(self, client: OllamaClient, max_candidates: int = 20) -> None:
        self.client = client
        self.max_candidates = max(1, min(max_candidates, 30))

    def rerank(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        limited = candidates[: self.max_candidates]
        if len(limited) < 2:
            return limited
        rendered = []
        for index, item in enumerate(limited):
            text = item.get("caption") or item.get("human_caption") or item.get("text") or ""
            title = item.get("asset_title") or item.get("title") or ""
            rendered.append({"id": str(item.get("segment_id") or item.get("chunk_id") or item.get("image_id") or index),
                             "title": str(title)[:180], "evidence": str(text)[:900]})
        prompt = (
            "Rank the evidence items for answering the query. Use only the supplied text. "
            "Return JSON {\"ranking\":[{\"id\": string, \"grade\": integer 0-3}]} "
            "with one entry per item, best first. Do not add IDs.\n"
            f"Query: {query}\nItems: {json.dumps(rendered, ensure_ascii=False)}"
        )
        try:
            result = json.loads(self.client.chat(prompt))
            ranking = result.get("ranking") if isinstance(result, dict) else None
            if not isinstance(ranking, list):
                return candidates
            allowed = {item["id"] for item in rendered}
            grades = {
                str(row.get("id")): int(row["grade"])
                for row in ranking
                if isinstance(row, dict)
                and str(row.get("id")) in allowed
                and isinstance(row.get("grade"), int)
                and 0 <= row["grade"] <= 3
            }
            if len(grades) < 2:
                return candidates
            def key(item: dict[str, Any]) -> tuple[int, float]:
                item_id = str(item.get("segment_id") or item.get("chunk_id") or item.get("image_id"))
                stable_score = item.get("rrf_score", item.get("score", 0))
                return (grades.get(item_id, -1), float(stable_score))
            head = sorted(limited, key=key, reverse=True)
            return head + candidates[len(limited):]
        except (LocalModelUnavailable, json.JSONDecodeError, TypeError, ValueError):
            return candidates


def parse_timestamped_transcript(value: str | None) -> tuple[TimedWord, ...]:
    """Read the compact '[start,end] word' representation used by optional ASR indexing."""
    if not value:
        return ()
    words: list[TimedWord] = []
    for match in re.finditer(r"\[(\d+(?:\.\d+)?),(\d+(?:\.\d+)?)\]\s*([^\s]+)", value):
        start, end = float(match.group(1)), float(match.group(2))
        if 0 <= start < end:
            words.append(TimedWord(match.group(3), start, end))
    return tuple(words)
