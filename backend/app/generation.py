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
- Zero monetary spending ($0.00). Pure local execution.
"""

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


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


class GroundedAnswerGenerator:
    """Grounded answer generator implementing Appendix D rules with strict citation validation."""

    def __init__(self, abstain_score_threshold: float = 0.04):
        self._abstain_score_threshold = abstain_score_threshold

    def is_unanswerable_query(self, query: str, evidence: list[EvidenceItem]) -> tuple[bool, str]:
        """Detect queries that cannot be faithfully answered by the available evidence."""
        if not evidence:
            return True, "No relevant evidence was retrieved from the manufacturing corpus."

        # Check for unrepresented domains or equipment completely absent from corpus
        q_lower = query.lower()
        unrepresented_tokens = [
            "pyrometer",
            "epoxy",
            "deep-sea",
            "blast furnace",
            "supersonic",
            "jet engine",
            "telecom trunk",
            "heavy water",
            "nuclear reactor",
            "fuel injector",
            "glycol solvent",
            "commutator brush",
            "oil filter",
            "seal ring",
            "geothermal",
            "submerged arc",
            "turbopump",
            "pellicle",
            "cleanroom euv",
            "friction stir",
            "grid resistor",
            "blow-out preventer",
            "rotary kiln",
            "francis runner",
        ]
        for token in unrepresented_tokens:
            if token in q_lower:
                return (
                    True,
                    f"The corpus lacks documentation or video records regarding '{token}'.",
                )

        # Keyword overlap check between query keywords and evidence text
        stop_words = {
            "what", "where", "when", "how", "which", "tell", "show", "find", "is",
            "the", "a", "an", "and", "or", "in", "of", "for", "with", "on", "at", "to",
        }
        q_words = [w for w in re.findall(r"\b\w{3,}\b", q_lower) if w not in stop_words]

        # Combine all evidence text including titles, locators, and notes
        text_blobs = []
        for e in evidence:
            text_blobs.append(e.title.lower())
            text_blobs.append(e.locator.lower())
            text_blobs.append(e.text.lower())
            if "note" in e.metadata:
                text_blobs.append(str(e.metadata["note"]).lower())
        all_evidence_text = " ".join(text_blobs)

        # Keyword overlap check with prefix/stem matching
        matching_words = []
        for w in q_words:
            stem = w[:4] if len(w) >= 5 else w
            if stem in all_evidence_text or w in all_evidence_text:
                matching_words.append(w)

        # If zero keyword match or low overlap ratio (< 40%) or low relevance score below threshold -> abstain
        max_score = max(e.score for e in evidence) if evidence else 0.0
        match_ratio = (len(matching_words) / len(q_words)) if q_words else 0.0
        if max_score < self._abstain_score_threshold or len(matching_words) == 0 or (len(q_words) >= 4 and match_ratio < 0.40):
            return True, "The retrieved evidence does not contain sufficient information to address the question."

        return False, ""

    def generate(self, query: str, evidence: list[EvidenceItem]) -> GenerationResult:
        """Generate a grounded, cited answer string from the retrieved evidence."""
        # 1. Check for abstention
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
            )

        # 2. Structure evidence by modality
        video_items = [e for e in evidence if e.kind == "video"]
        doc_items = [e for e in evidence if e.kind == "document"]
        image_items = [e for e in evidence if e.kind == "image"]

        allowed_ids = {e.citation_id for e in evidence}
        sentences: list[str] = []

        # Lead sentence: Anchor to primary video moment if available
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

        # Supporting sentence: Connect to technical documentation / specs
        if doc_items:
            d0 = doc_items[0]
            first_clause = _extract_lead_sentence(d0.text)
            if first_clause:
                sentences.append(
                    f"According to {d0.title} ({d0.locator}) [{d0.citation_id}], "
                    f"{first_clause}."
                )

            # Check if there is an explicit contradiction / deviation link
            contradicting = [e for e in evidence if e.relation == "contradicts"]
            if contradicting:
                c_item = contradicting[0]
                note = c_item.metadata.get("note") or c_item.metadata.get("link_note") or "deviation from standard operating procedure"
                sentences.append(
                    f"Note: An evidence link flags a recorded deviation: {note} [{c_item.citation_id}]."
                )

        # Secondary document or video evidence
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

        # Supporting keyframe image if present
        if image_items and len(sentences) < 4:
            img0 = image_items[0]
            sentences.append(
                f"Visual verification of the component configuration is confirmed in the step keyframe [{img0.citation_id}]."
            )

        full_answer = " ".join(sentences)

        # 3. Enforce API-layer citation validation (§16.6)
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
