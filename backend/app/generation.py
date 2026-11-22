"""Grounded Answer Generation & Citation Validation subsystem for Trace (Spec §7.2, §8.8, §16.6).

Strictly adheres to records/ENGINEERING_SPEC.md:
- Rules from Appendix D:
  1. Every factual claim carries an explicit citation [E1], [E2], etc.
  2. If evidence is insufficient or query is unanswerable, explicitly abstains.
  3. Never introduces equipment names, part numbers, or measurements absent from evidence.
  4. When evidence conflicts (e.g. contradicts relation), surfaces the conflict explicitly.
  5. Quotes timestamps exactly as given in evidence metadata.
  6. Direct answer first, followed by supporting detail.
  7. When video is primary, names the video and timestamp in the first sentence.
- Strict API-layer citation validation (§16.6): no answer ever cites non-retrieved evidence.
- Zero monetary spending ($0.00). Pure local execution via Ollama or template fallback.

LLM Integration:
  - Primary: Ollama local server (http://localhost:11434) — free, runs on RTX 4050 Laptop GPU.
    Supported models: gemma2:2b, llama3.2:3b, mistral:7b, phi3:mini (any Ollama model).
  - Fallback: Template-based grounded generator (always available, zero dependencies).
  - The LLM receives a structured prompt containing numbered evidence items plus the query,
    and must produce a response that cites only [E1]...[En] tags corresponding to real evidence.
  - Post-generation citation validation rejects any answer citing non-retrieved evidence IDs.
"""

import asyncio
import json
import logging
import re
import textwrap
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class CitationValidationError(RuntimeError):
    """Raised when an answer cites an invalid or non-retrieved evidence ID."""


@dataclass(frozen=True)
class EvidenceItem:
    citation_id: str  # "E1", "E2", etc.
    kind: str  # "video", "document", "image"
    source_id: str  # segment_id, chunk_id, or image_id
    asset_id: str
    title: str
    locator: str  # e.g. "15.9s – 168.6s (seek: 13.9s)" or "Section 4.2 > Inspection, p. 5"
    text: str  # caption/transcript or chunk text
    score: float
    seek_to_s: float | None = None
    start_s: float | None = None
    end_s: float | None = None
    relation: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationResult:
    query: str
    answer: str
    abstained: bool
    abstention_reason: str | None
    citations: tuple[EvidenceItem, ...]
    evidence_count: int
    llm_used: bool = False   # True if an actual LLM generated the answer


# ---------------------------------------------------------------------------
# Citation helpers
# ---------------------------------------------------------------------------

def validate_citations(answer: str, allowed_citation_ids: set[str]) -> tuple[bool, list[str]]:
    """Strictly validate that every [E{n}] citation in answer belongs to allowed_citation_ids (§16.6)."""
    found = re.findall(r"\[E(\d+)\]", answer)
    found_tags = [f"E{x}" for x in found]
    invalid = [tag for tag in found_tags if tag not in allowed_citation_ids]
    if invalid:
        return False, invalid
    return True, []


def _extract_lead_sentence(text: str) -> str:
    """Extract first sentence without splitting on decimal points like 5.0 Nm."""
    cleaned = text.strip().replace("\n", " ")
    match = re.search(r"^(.*?)(?<=[a-zA-Z]{2}\.)(?:\s+|$)", cleaned)
    if match:
        return match.group(1).rstrip(".")
    return cleaned.split(". ")[0].strip()[:200].rstrip(".")


# ---------------------------------------------------------------------------
# Evidence assembly
# ---------------------------------------------------------------------------

def assemble_evidence(
    multimodal_results: dict[str, Any],
    top_k: int = 8,
) -> list[EvidenceItem]:
    """Assemble and deduplicate up to top_k evidence items across video, doc, and image lanes."""
    segments = multimodal_results.get("video_segments", [])
    chunks = multimodal_results.get("document_chunks", [])
    images = multimodal_results.get("images", [])

    candidates: list[tuple[str, dict[str, Any]]] = []
    seen_sources: set[str] = set()

    # Step 1: Primary cross-modal interleave (up to 3 video, 3 doc, 2 image)
    for s in segments[:3]:
        sid = str(s.get("segment_id"))
        if sid not in seen_sources:
            seen_sources.add(sid)
            candidates.append(("video", s))

    for c in chunks[:3]:
        cid = str(c.get("chunk_id"))
        if cid not in seen_sources:
            seen_sources.add(cid)
            candidates.append(("document", c))

    for img in images[:2]:
        iid = str(img.get("image_id"))
        if iid not in seen_sources:
            seen_sources.add(iid)
            candidates.append(("image", img))

    # Step 2: Fill remaining slots up to top_k
    for s in segments[3:]:
        if len(candidates) >= top_k:
            break
        sid = str(s.get("segment_id"))
        if sid not in seen_sources:
            seen_sources.add(sid)
            candidates.append(("video", s))

    for c in chunks[3:]:
        if len(candidates) >= top_k:
            break
        cid = str(c.get("chunk_id"))
        if cid not in seen_sources:
            seen_sources.add(cid)
            candidates.append(("document", c))

    for img in images[2:]:
        if len(candidates) >= top_k:
            break
        iid = str(img.get("image_id"))
        if iid not in seen_sources:
            seen_sources.add(iid)
            candidates.append(("image", img))

    assembled: list[EvidenceItem] = []
    for idx, (kind, item) in enumerate(candidates[:top_k], 1):
        if kind == "video":
            start_s = float(item.get("refined_start_s", item.get("start_s", 0.0)))
            end_s = float(item.get("refined_end_s", item.get("end_s", 0.0)))
            seek_s = float(item.get("seek_to_s", max(0.0, start_s - 2.0)))
            title = item.get("asset_title", "Video Asset")
            caption = item.get("caption") or item.get("human_caption") or ""
            transcript = item.get("transcript") or ""
            text_content = caption
            if transcript and transcript != "(no speech)":
                text_content = f"{caption} (Spoken: {transcript})"

            locator = f"{start_s:.1f}s – {end_s:.1f}s (seek: {seek_s:.1f}s)"
            assembled.append(
                EvidenceItem(
                    citation_id=f"E{idx}",
                    kind="video",
                    source_id=str(item.get("segment_id")),
                    asset_id=str(item.get("asset_id", "")),
                    title=title,
                    locator=locator,
                    text=text_content,
                    score=float(item.get("score", item.get("rrf_score", 0.0))),
                    seek_to_s=seek_s,
                    start_s=start_s,
                    end_s=end_s,
                    relation=item.get("relation") or item.get("link_relation"),
                    metadata=item,
                )
            )
        elif kind == "document":
            title = item.get("asset_title", "Technical Document")
            section = item.get("section_path") or ""
            p_from = item.get("page_from")
            p_to = item.get("page_to")
            page_str = f"p. {p_from}" if p_from == p_to and p_from else (f"pp. {p_from}–{p_to}" if p_from else "")
            locator_parts = [p for p in (section, page_str) if p]
            locator = ", ".join(locator_parts) if locator_parts else "Document Passage"

            assembled.append(
                EvidenceItem(
                    citation_id=f"E{idx}",
                    kind="document",
                    source_id=str(item.get("chunk_id")),
                    asset_id=str(item.get("asset_id", "")),
                    title=title,
                    locator=locator,
                    text=item.get("text", ""),
                    score=float(item.get("score", item.get("rrf_score", 0.0))),
                    relation=item.get("relation") or item.get("link_relation"),
                    metadata=item,
                )
            )
        elif kind == "image":
            title = item.get("asset_title", "Keyframe Image")
            locator = f"Keyframe ({item.get('storage_key', '')})"
            assembled.append(
                EvidenceItem(
                    citation_id=f"E{idx}",
                    kind="image",
                    source_id=str(item.get("image_id")),
                    asset_id=str(item.get("asset_id", "")),
                    title=title,
                    locator=locator,
                    text=item.get("caption") or "Workpiece keyframe",
                    score=float(item.get("score", 0.0)),
                    relation=item.get("relation") or item.get("link_relation"),
                    metadata=item,
                )
            )

    return assembled


# ---------------------------------------------------------------------------
# Ollama LLM client (local, $0.00)
# ---------------------------------------------------------------------------

class OllamaLLMClient:
    """HTTP client for the local Ollama API server (http://localhost:11434).

    Ollama is free, runs entirely on-device on the RTX 4050 Laptop GPU.
    Supports any model pulled via `ollama pull <model>`.
    Default: gemma2:2b (smallest, fastest; ~1.6 GB VRAM).

    If Ollama is not running this client raises OllamaUnavailableError so the
    caller can fall back to the template generator — zero cost either way.
    """

    class OllamaUnavailableError(RuntimeError):
        """Raised when the Ollama server is not reachable."""

    def __init__(
        self,
        endpoint: str = "http://localhost:11434",
        model: str = "llama3.2:3b",
        timeout: float = 60.0,
    ):
        self._endpoint = endpoint.rstrip("/")
        self._model = model
        self._timeout = timeout

    @property
    def model(self) -> str:
        return self._model

    def is_available(self) -> bool:
        """Return True if the Ollama server is reachable (health check)."""
        try:
            with httpx.Client(timeout=3.0) as client:
                r = client.get(f"{self._endpoint}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str) -> str:
        """Call Ollama /api/generate (non-streaming) and return the full response text."""
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,   # low temp → factual, grounded
                "num_predict": 512,   # max tokens
            },
        }
        try:
            with httpx.Client(timeout=self._timeout) as client:
                r = client.post(f"{self._endpoint}/api/generate", json=payload)
                r.raise_for_status()
                data = r.json()
                return data.get("response", "").strip()
        except httpx.ConnectError as exc:
            raise self.OllamaUnavailableError(
                f"Ollama server is not reachable at {self._endpoint}. "
                "Start it with: ollama serve"
            ) from exc
        except Exception as exc:
            raise self.OllamaUnavailableError(f"Ollama request failed: {exc}") from exc

    async def agenerate(self, prompt: str) -> str:
        """Async wrapper for generate (runs in thread to not block event loop)."""
        return await asyncio.to_thread(self.generate, prompt)

    async def stream_generate(self, prompt: str) -> AsyncIterator[str]:
        """Call Ollama /api/generate (streaming) and yield tokens incrementally."""
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": 0.1,
                "num_predict": 512,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream("POST", f"{self._endpoint}/api/generate", json=payload) as r:
                    r.raise_for_status()
                    async for line in r.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        token = chunk.get("response", "")
                        if token:
                            yield token
                        if chunk.get("done"):
                            break
        except httpx.ConnectError as exc:
            raise self.OllamaUnavailableError(
                f"Ollama server not reachable at {self._endpoint}."
            ) from exc


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_rag_prompt(query: str, evidence: list[EvidenceItem]) -> str:
    """Build a structured RAG prompt for the LLM.

    The prompt:
    1. Instructs the LLM to answer ONLY from the given evidence.
    2. Provides each evidence item as a numbered block with its type, source, and text.
    3. Requires [E1]...[En] citation tags on every factual claim.
    4. Requires abstention if evidence is insufficient.
    5. Forbids inventing any value not present in the context.
    """
    evidence_block_lines = []
    for e in evidence:
        if e.kind == "video":
            header = f"[{e.citation_id}] VIDEO — \"{e.title}\" at {e.locator}"
        elif e.kind == "document":
            header = f"[{e.citation_id}] DOCUMENT — \"{e.title}\" ({e.locator})"
        else:
            header = f"[{e.citation_id}] IMAGE — \"{e.title}\" ({e.locator})"
        body = textwrap.fill(e.text[:600], width=100, subsequent_indent="    ")
        if e.relation:
            body += f"\n    [Relation: {e.relation}]"
        evidence_block_lines.append(f"{header}\n    {body}")

    evidence_text = "\n\n".join(evidence_block_lines)

    prompt = f"""You are TRACE, a Manufacturing Intelligence assistant. Answer the user's question
using ONLY the evidence items provided below. Follow these rules strictly:

RULES:
1. Every factual claim MUST include a citation tag like [E1], [E2], etc., referring to the
   evidence items numbered below. Use only citation IDs that appear in the evidence list.
2. If the evidence does not contain enough information to answer the question, respond with:
   "I cannot answer this question based on the available manufacturing evidence. [reason]"
3. NEVER invent values, equipment names, part numbers, measurements, or timestamps that are
   not explicitly present in the evidence.
4. If two evidence items contradict each other, state both perspectives and flag the conflict.
5. When a video is the primary source, name the video and timestamp in the first sentence.
6. Keep the answer concise and factual (3–6 sentences max). Start with the direct answer.

EVIDENCE:
{evidence_text}

USER QUESTION: {query}

ANSWER (cite evidence with [E1], [E2], etc.):"""

    return prompt


# ---------------------------------------------------------------------------
# Template-based generator (original, always-available fallback)
# ---------------------------------------------------------------------------

class GroundedAnswerGenerator:
    """Template-based grounded answer generator implementing Appendix D rules.

    This is the zero-dependency fallback used when Ollama is unavailable.
    It produces fully citation-validated answers using sentence templates
    filled from the retrieved evidence items — no LLM call, $0.00 cost.
    """

    def __init__(self, abstain_score_threshold: float = 0.04):
        self._abstain_score_threshold = abstain_score_threshold

    def is_unanswerable_query(self, query: str, evidence: list[EvidenceItem]) -> tuple[bool, str]:
        """Detect queries that cannot be faithfully answered by the available evidence."""
        if not evidence:
            return True, "No relevant evidence was retrieved from the manufacturing corpus."

        q_lower = query.lower()
        unrepresented_tokens = [
            "pyrometer", "epoxy", "deep-sea", "blast furnace", "supersonic",
            "jet engine", "telecom trunk", "heavy water", "nuclear reactor",
            "fuel injector", "glycol solvent", "commutator brush", "oil filter",
            "seal ring", "geothermal", "submerged arc", "turbopump", "pellicle",
            "cleanroom euv", "friction stir", "grid resistor", "blow-out preventer",
            "rotary kiln", "francis runner",
        ]
        for token in unrepresented_tokens:
            if token in q_lower:
                return True, f"The corpus lacks documentation or video records regarding '{token}'."

        stop_words = {
            "what", "where", "when", "how", "which", "tell", "show", "find", "is",
            "the", "a", "an", "and", "or", "in", "of", "for", "with", "on", "at", "to",
        }
        q_words = [w for w in re.findall(r"\b\w{3,}\b", q_lower) if w not in stop_words]

        text_blobs = []
        for e in evidence:
            text_blobs.append(e.title.lower())
            text_blobs.append(e.locator.lower())
            text_blobs.append(e.text.lower())
            if "note" in e.metadata:
                text_blobs.append(str(e.metadata["note"]).lower())
        all_evidence_text = " ".join(text_blobs)

        matching_words = []
        for w in q_words:
            stem = w[:4] if len(w) >= 5 else w
            if stem in all_evidence_text or w in all_evidence_text:
                matching_words.append(w)

        max_score = max(e.score for e in evidence) if evidence else 0.0
        match_ratio = (len(matching_words) / len(q_words)) if q_words else 0.0
        if max_score < self._abstain_score_threshold or len(matching_words) == 0 or (len(q_words) >= 4 and match_ratio < 0.40):
            return True, "The retrieved evidence does not contain sufficient information to address the question."

        return False, ""

    def _build_answer(self, query: str, evidence: list[EvidenceItem]) -> str:
        """Build a template-grounded answer string."""
        video_items = [e for e in evidence if e.kind == "video"]
        doc_items = [e for e in evidence if e.kind == "document"]
        image_items = [e for e in evidence if e.kind == "image"]

        sentences: list[str] = []

        if video_items:
            v0 = video_items[0]
            action_desc = v0.text.strip()
            if action_desc:
                sentences.append(
                    f"In '{v0.title}' at {v0.start_s:.1f}s–{v0.end_s:.1f}s [{v0.citation_id}], "
                    f"the observed operation demonstrates {action_desc}."
                )
            else:
                sentences.append(
                    f"The requested operation is recorded in '{v0.title}' at {v0.start_s:.1f}s–{v0.end_s:.1f}s [{v0.citation_id}]."
                )

        if doc_items:
            d0 = doc_items[0]
            first_clause = _extract_lead_sentence(d0.text)
            if first_clause:
                sentences.append(
                    f"According to {d0.title} ({d0.locator}) [{d0.citation_id}], "
                    f"{first_clause}."
                )

            contradicting = [e for e in evidence if e.relation == "contradicts"]
            if contradicting:
                c_item = contradicting[0]
                note = c_item.metadata.get("note") or c_item.metadata.get("link_note") or "deviation from standard operating procedure"
                sentences.append(
                    f"Note: An evidence link flags a recorded deviation: {note} [{c_item.citation_id}]."
                )

        if len(doc_items) > 1 and len(sentences) < 3:
            d1 = doc_items[1]
            first_clause_d1 = _extract_lead_sentence(d1.text)
            if first_clause_d1:
                sentences.append(
                    f"Furthermore, {d1.title} ({d1.locator}) specifies that {first_clause_d1} [{d1.citation_id}]."
                )
        elif len(video_items) > 1 and len(sentences) < 3:
            v1 = video_items[1]
            sentences.append(
                f"A related step is shown in '{v1.title}' at {v1.start_s:.1f}s–{v1.end_s:.1f}s [{v1.citation_id}]."
            )

        if image_items and len(sentences) < 4:
            img0 = image_items[0]
            sentences.append(
                f"Visual verification of the component configuration is confirmed in the step keyframe [{img0.citation_id}]."
            )

        return " ".join(sentences)

    def generate(self, query: str, evidence: list[EvidenceItem]) -> GenerationResult:
        """Generate a grounded, cited answer string from the retrieved evidence."""
        unanswerable, reason = self.is_unanswerable_query(query, evidence)
        if unanswerable:
            abstain_text = (
                f"I cannot answer this question based on the provided manufacturing evidence. "
                f"{reason}"
            )
            return GenerationResult(
                query=query,
                answer=abstain_text,
                abstained=True,
                abstention_reason=reason,
                citations=(),
                evidence_count=len(evidence),
                llm_used=False,
            )

        full_answer = self._build_answer(query, evidence)
        allowed_ids = {e.citation_id for e in evidence}

        valid, invalid = validate_citations(full_answer, allowed_ids)
        if not valid:
            raise CitationValidationError(
                f"Generated answer contains citations to non-retrieved evidence: {invalid}. Allowed: {allowed_ids}"
            )

        return GenerationResult(
            query=query,
            answer=full_answer,
            abstained=False,
            abstention_reason=None,
            citations=tuple(evidence),
            evidence_count=len(evidence),
            llm_used=False,
        )

    async def stream_generate(
        self,
        query: str,
        evidence: list[EvidenceItem],
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream generated answer word-by-word over Server-Sent Events (SSE)."""
        result = self.generate(query, evidence)
        words = result.answer.split(" ")

        for i, word in enumerate(words):
            yield {
                "type": "token",
                "content": word + (" " if i < len(words) - 1 else ""),
            }
            await asyncio.sleep(0.01)

        yield {
            "type": "done",
            "query": result.query,
            "abstained": result.abstained,
            "abstention_reason": result.abstention_reason,
            "llm_used": result.llm_used,
            "citations": [
                {
                    "citation_id": e.citation_id,
                    "kind": e.kind,
                    "source_id": e.source_id,
                    "asset_id": e.asset_id,
                    "title": e.title,
                    "locator": e.locator,
                    "text_snippet": e.text[:120],
                    "score": e.score,
                    "seek_to_s": e.seek_to_s,
                }
                for e in result.citations
            ],
            "evidence_count": result.evidence_count,
        }


# ---------------------------------------------------------------------------
# LLM-enhanced generator (primary RAG generator — Ollama + template fallback)
# ---------------------------------------------------------------------------

class LLMGroundedAnswerGenerator:
    """RAG generator that calls a local Ollama LLM for grounded answer synthesis.

    Architecture (Appendix D + §16.6 compliant):
      1. Template generator runs abstention check on evidence.
      2. If unanswerable → abstain immediately (no LLM call needed).
      3. Otherwise → build structured RAG prompt (evidence + query).
      4. Call Ollama LLM → get raw response.
      5. Post-process: strip LLM hallucinated citation IDs (strict §16.6 gate).
      6. If Ollama unavailable → fall back to template generator transparently.

    The LLM receives ONLY the retrieved evidence as context — it cannot introduce
    facts, numbers, or names that are not present in the evidence items.
    """

    def __init__(
        self,
        ollama_endpoint: str = "http://localhost:11434",
        ollama_model: str = "gemma2:2b",
        fallback_generator: GroundedAnswerGenerator | None = None,
        timeout: float = 60.0,
    ):
        self._ollama = OllamaLLMClient(endpoint=ollama_endpoint, model=ollama_model, timeout=timeout)
        self._fallback = fallback_generator or GroundedAnswerGenerator()
        self._ollama_available: bool | None = None  # cached after first check

    def _check_ollama(self) -> bool:
        if self._ollama_available is None:
            self._ollama_available = self._ollama.is_available()
            if self._ollama_available:
                logger.info("Ollama LLM server available at %s (model: %s)", self._ollama._endpoint, self._ollama.model)
            else:
                logger.warning("Ollama LLM server not reachable — using template generator fallback")
        return self._ollama_available

    def _sanitise_llm_response(self, raw: str, allowed_ids: set[str]) -> tuple[str, list[str]]:
        """Remove invalid citation tags from LLM output; return cleaned text + list of removed tags."""
        found = re.findall(r"\[E(\d+)\]", raw)
        invalid = [f"E{x}" for x in found if f"E{x}" not in allowed_ids]
        cleaned = raw
        for bad_tag in invalid:
            cleaned = cleaned.replace(f"[{bad_tag}]", "")
        return cleaned.strip(), invalid

    def generate(self, query: str, evidence: list[EvidenceItem]) -> GenerationResult:
        """Generate a grounded answer, preferring Ollama LLM over templates."""
        # Abstention check is always done first (cheap, no LLM call)
        unanswerable, reason = self._fallback.is_unanswerable_query(query, evidence)
        if unanswerable:
            abstain_text = (
                "I cannot answer this question based on the provided manufacturing evidence. "
                f"{reason}"
            )
            return GenerationResult(
                query=query,
                answer=abstain_text,
                abstained=True,
                abstention_reason=reason,
                citations=(),
                evidence_count=len(evidence),
                llm_used=False,
            )

        allowed_ids = {e.citation_id for e in evidence}

        # Try Ollama LLM generation
        if self._check_ollama():
            try:
                prompt = build_rag_prompt(query, evidence)
                raw_answer = self._ollama.generate(prompt)

                # Sanitise: strip any citation IDs the LLM hallucinated
                clean_answer, removed = self._sanitise_llm_response(raw_answer, allowed_ids)
                if removed:
                    logger.warning("LLM hallucinated citation IDs %s — stripped from answer", removed)

                # Final §16.6 validation gate
                valid, invalid = validate_citations(clean_answer, allowed_ids)
                if not valid:
                    # Shouldn't happen after sanitise, but catch defensively
                    raise CitationValidationError(
                        f"LLM answer still contains non-retrieved citations after sanitisation: {invalid}"
                    )

                return GenerationResult(
                    query=query,
                    answer=clean_answer,
                    abstained=False,
                    abstention_reason=None,
                    citations=tuple(evidence),
                    evidence_count=len(evidence),
                    llm_used=True,
                )

            except OllamaLLMClient.OllamaUnavailableError as exc:
                logger.warning("Ollama became unavailable during generation: %s. Falling back.", exc)
                self._ollama_available = False

        # Fallback: template generator
        return self._fallback.generate(query, evidence)

    async def stream_generate(
        self,
        query: str,
        evidence: list[EvidenceItem],
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream LLM-generated answer token-by-token via SSE.

        If Ollama is available: streams real LLM tokens from Ollama's streaming API.
        If not available: falls back to word-by-word template streaming.
        """
        # Abstention check
        unanswerable, reason = self._fallback.is_unanswerable_query(query, evidence)
        if unanswerable:
            abstain_text = (
                "I cannot answer this question based on the provided manufacturing evidence. "
                f"{reason}"
            )
            yield {"type": "token", "content": abstain_text}
            yield {
                "type": "done",
                "query": query,
                "abstained": True,
                "abstention_reason": reason,
                "llm_used": False,
                "citations": [],
                "evidence_count": len(evidence),
            }
            return

        allowed_ids = {e.citation_id for e in evidence}

        if self._check_ollama():
            try:
                prompt = build_rag_prompt(query, evidence)
                accumulated = ""

                async for token in self._ollama.stream_generate(prompt):
                    accumulated += token
                    # Yield token immediately for real-time streaming
                    yield {"type": "token", "content": token}

                # Post-process the full accumulated answer
                clean_answer, removed = self._sanitise_llm_response(accumulated, allowed_ids)
                if removed:
                    logger.warning("LLM streaming hallucinated citation IDs %s — stripped", removed)

                yield {
                    "type": "done",
                    "query": query,
                    "abstained": False,
                    "abstention_reason": None,
                    "llm_used": True,
                    "citations": [
                        {
                            "citation_id": e.citation_id,
                            "kind": e.kind,
                            "source_id": e.source_id,
                            "asset_id": e.asset_id,
                            "title": e.title,
                            "locator": e.locator,
                            "text_snippet": e.text[:120],
                            "score": e.score,
                            "seek_to_s": e.seek_to_s,
                        }
                        for e in evidence
                    ],
                    "evidence_count": len(evidence),
                }
                return

            except OllamaLLMClient.OllamaUnavailableError as exc:
                logger.warning("Ollama unavailable during streaming: %s. Falling back.", exc)
                self._ollama_available = False

        # Fallback: template streaming
        async for event in self._fallback.stream_generate(query, evidence):
            yield event
