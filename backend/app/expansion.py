"""Evidence-link graph expansion for Trace retrieval (spec Section 8.5).

Connects video moments to technical documents and vice versa:
- For each surviving segment, pulls linked document chunks and injects at discounted score (x0.7).
- For each surviving document chunk, pulls linked video segments with refined timestamps.
- Guards against runaway expansion: max 2 neighbours per item, one hop only, capped at +10 items total.
- Supports the '--no-link-expansion' ablation hook (spec Section 13.5, Config A5).
"""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, Chunk, EvidenceLink, Segment
from app.refinement import refine_temporal_span

DEFAULT_EXPANSION_DISCOUNT = 0.7
DEFAULT_MAX_NEIGHBOURS_PER_ITEM = 2
DEFAULT_MAX_EXPANSION_TOTAL = 10


def expand_segment_to_chunks(
    session: Session,
    segment_item: dict[str, Any],
    *,
    discount: float = DEFAULT_EXPANSION_DISCOUNT,
    max_neighbours: int = DEFAULT_MAX_NEIGHBOURS_PER_ITEM,
) -> list[dict[str, Any]]:
    """Pull document chunks linked to a video segment via evidence_links."""
    seg_id = str(segment_item["segment_id"])
    query = (
        select(EvidenceLink, Chunk, Asset)
        .join(Chunk, EvidenceLink.chunk_id == Chunk.id)
        .join(Asset, Chunk.asset_id == Asset.id)
        .where(EvidenceLink.segment_id == seg_id)
        .order_by(EvidenceLink.confidence.desc(), EvidenceLink.created_at)
        .limit(max_neighbours)
    )
    rows = session.execute(query).all()
    expanded: list[dict[str, Any]] = []
    base_score = float(segment_item.get("score") or segment_item.get("rrf_score") or 1.0)

    for link, chunk, asset in rows:
        expanded_score = base_score * discount * float(link.confidence)
        expanded.append(
            {
                "chunk_id": str(chunk.id),
                "asset_id": str(asset.id),
                "asset_title": asset.title,
                "equipment_family": asset.equipment_family,
                "doc_type": chunk.doc_type,
                "section_path": chunk.section_path,
                "page_from": chunk.page_from,
                "page_to": chunk.page_to,
                "text": chunk.text,
                "token_count": chunk.token_count,
                "score": expanded_score,
                "rrf_score": expanded_score,
                "via_link": True,
                "link_relation": link.relation,
                "link_author": link.author,
                "link_note": link.note,
                "linked_from_id": seg_id,
                "lanes": ["link_expansion"],
            }
        )
    return expanded


def expand_chunk_to_segments(
    session: Session,
    chunk_item: dict[str, Any],
    query_text: str | None = None,
    *,
    discount: float = DEFAULT_EXPANSION_DISCOUNT,
    max_neighbours: int = DEFAULT_MAX_NEIGHBOURS_PER_ITEM,
) -> list[dict[str, Any]]:
    """Pull video segments linked to a document chunk via evidence_links."""
    chk_id = str(chunk_item["chunk_id"])
    query = (
        select(EvidenceLink, Segment, Asset)
        .join(Segment, EvidenceLink.segment_id == Segment.id)
        .join(Asset, Segment.asset_id == Asset.id)
        .where(EvidenceLink.chunk_id == chk_id)
        .order_by(EvidenceLink.confidence.desc(), EvidenceLink.created_at)
        .limit(max_neighbours)
    )
    rows = session.execute(query).all()
    expanded: list[dict[str, Any]] = []
    base_score = float(chunk_item.get("score") or chunk_item.get("rrf_score") or 1.0)

    for link, seg, asset in rows:
        expanded_score = base_score * discount * float(link.confidence)
        caption = seg.caption or seg.human_caption or ""
        start_s = float(seg.start_s)
        end_s = float(seg.end_s)

        refined = refine_temporal_span(query_text or caption, start_s, end_s, caption=caption)

        expanded.append(
            {
                "segment_id": str(seg.id),
                "asset_id": str(asset.id),
                "asset_title": asset.title,
                "asset_source_uri": asset.source_uri,
                "source_uri": asset.source_uri,
                "equipment_family": asset.equipment_family,
                "idx": seg.idx,
                "start_s": start_s,
                "end_s": end_s,
                "refined_start_s": refined.start_s,
                "refined_end_s": refined.end_s,
                "seek_to_s": refined.seek_to_s,
                "caption": seg.caption,
                "human_caption": seg.human_caption,
                "transcript": seg.transcript,
                "score": expanded_score,
                "rrf_score": expanded_score,
                "via_link": True,
                "link_relation": link.relation,
                "link_author": link.author,
                "link_note": link.note,
                "linked_from_id": chk_id,
                "lanes": ["link_expansion"],
            }
        )
    return expanded


def expand_candidates(
    session: Session,
    segments: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    query_text: str | None = None,
    *,
    enabled: bool = True,
    discount: float = DEFAULT_EXPANSION_DISCOUNT,
    max_per_item: int = DEFAULT_MAX_NEIGHBOURS_PER_ITEM,
    max_total: int = DEFAULT_MAX_EXPANSION_TOTAL,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Execute evidence-link graph expansion across candidate lists (§8.5).

    Returns (expanded_segments, expanded_chunks).
    """
    if not enabled:
        return segments, chunks

    expanded_segments = [dict(s) for s in segments]
    expanded_chunks = [dict(c) for c in chunks]

    existing_seg_ids = {str(s["segment_id"]): s for s in expanded_segments}
    existing_chk_ids = {str(c["chunk_id"]): c for c in expanded_chunks}

    total_injected = 0

    # Expand from top segments into chunks
    for seg in segments[:5]:
        if total_injected >= max_total:
            break
        linked_chunks = expand_segment_to_chunks(
            session,
            seg,
            discount=discount,
            max_neighbours=max_per_item,
        )
        for lc in linked_chunks:
            if total_injected >= max_total:
                break
            cid = lc["chunk_id"]
            if cid in existing_chk_ids:
                # Merge lanes and take higher score
                existing = existing_chk_ids[cid]
                if "link_expansion" not in existing.get("lanes", []):
                    existing.setdefault("lanes", []).append("link_expansion")
                if lc["score"] > existing.get("score", 0.0):
                    existing["score"] = lc["score"]
                    existing["via_link"] = False
                    existing["link_relation"] = lc["link_relation"]
            else:
                expanded_chunks.append(lc)
                existing_chk_ids[cid] = lc
                total_injected += 1

    # Expand from top chunks into segments
    for chk in chunks[:5]:
        if total_injected >= max_total:
            break
        linked_segs = expand_chunk_to_segments(
            session,
            chk,
            query_text=query_text,
            discount=discount,
            max_neighbours=max_per_item,
        )
        for ls in linked_segs:
            if total_injected >= max_total:
                break
            sid = ls["segment_id"]
            if sid in existing_seg_ids:
                existing = existing_seg_ids[sid]
                if "link_expansion" not in existing.get("lanes", []):
                    existing.setdefault("lanes", []).append("link_expansion")
                if ls["score"] > existing.get("score", 0.0):
                    existing["score"] = ls["score"]
                    existing["via_link"] = False
                    existing["link_relation"] = ls["link_relation"]
            else:
                expanded_segments.append(ls)
                existing_seg_ids[sid] = ls
                total_injected += 1

    # Sort each list by score descending
    expanded_segments.sort(key=lambda s: float(s.get("score", 0.0)), reverse=True)
    expanded_chunks.sort(key=lambda c: float(c.get("score", 0.0)), reverse=True)

    return expanded_segments, expanded_chunks
