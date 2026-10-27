"""Retrieval subsystem for Trace (spec Section 8).

Implements:
- Dense vector search over pgvector HNSW indices (vec_segment_text, vec_chunk)
- Lexical search over full-text indices (BM25 / tsvector)
- Reciprocal Rank Fusion (RRF, spec 8.4) combining dense and lexical lanes
"""

import math
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.embeddings import DIMENSIONS, MODEL, BgeM3Client
from app.expansion import expand_candidates
from app.refinement import refine_temporal_span
from app.vision import DIMENSIONS as VISUAL_DIMENSIONS, MODEL as VISUAL_MODEL, SiglipVisualClient


class SearchError(RuntimeError):
    """Sanitized retrieval error."""


def format_vector(vector: list[float] | tuple[float, ...], expected_dim: int = DIMENSIONS) -> str:
    """Format float sequence as pgvector string literal '[x,y,z]'."""
    if len(vector) != expected_dim:
        raise ValueError(f"Vector dimensions must be exactly {expected_dim}, got {len(vector)}")
    if any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in vector):
        raise ValueError("Vector contains non-finite numeric elements")
    return "[" + ",".join(str(float(x)) for x in vector) + "]"


def index_segment_vector(
    session: Session,
    segment_id: str,
    vector: list[float] | tuple[float, ...],
    model: str = MODEL,
) -> None:
    """Insert or update a 1024-d dense embedding for a video segment."""
    vec_str = format_vector(vector)
    query = text(
        """
        INSERT INTO vec_segment_text (segment_id, model, embedding)
        VALUES (:segment_id, :model, CAST(:vec AS vector))
        ON CONFLICT (segment_id)
        DO UPDATE SET model = EXCLUDED.model, embedding = EXCLUDED.embedding
        """
    )
    session.execute(query, {"segment_id": segment_id, "model": model, "vec": vec_str})


def index_chunk_vector(
    session: Session,
    chunk_id: str,
    vector: list[float] | tuple[float, ...],
    model: str = MODEL,
) -> None:
    """Insert or update a 1024-d dense embedding for a document chunk."""
    vec_str = format_vector(vector)
    query = text(
        """
        INSERT INTO vec_chunk (chunk_id, model, embedding)
        VALUES (:chunk_id, :model, CAST(:vec AS vector))
        ON CONFLICT (chunk_id)
        DO UPDATE SET model = EXCLUDED.model, embedding = EXCLUDED.embedding
        """
    )
    session.execute(query, {"chunk_id": chunk_id, "model": model, "vec": vec_str})


def index_image_vector(
    session: Session,
    image_id: str,
    vector: list[float] | tuple[float, ...],
    model: str = VISUAL_MODEL,
) -> None:
    """Insert or update a 1,152-d dense embedding for an image keyframe."""
    vec_str = format_vector(vector, expected_dim=VISUAL_DIMENSIONS)
    query = text(
        """
        INSERT INTO vec_image (image_id, model, embedding)
        VALUES (:image_id, :model, CAST(:vec AS vector))
        ON CONFLICT (image_id)
        DO UPDATE SET model = EXCLUDED.model, embedding = EXCLUDED.embedding
        """
    )
    session.execute(query, {"image_id": image_id, "model": model, "vec": vec_str})


def index_segment_visual_vector(
    session: Session,
    segment_id: str,
    vector: list[float] | tuple[float, ...],
    model: str = VISUAL_MODEL,
) -> None:
    """Insert or update a 1,152-d visual embedding for a video segment."""
    vec_str = format_vector(vector, expected_dim=VISUAL_DIMENSIONS)
    query = text(
        """
        INSERT INTO vec_segment_visual (segment_id, model, embedding)
        VALUES (:segment_id, :model, CAST(:vec AS vector))
        ON CONFLICT (segment_id)
        DO UPDATE SET model = EXCLUDED.model, embedding = EXCLUDED.embedding
        """
    )
    session.execute(query, {"segment_id": segment_id, "model": model, "vec": vec_str})


def search_images_visual(
    session: Session,
    query_vector: list[float] | tuple[float, ...],
    *,
    limit: int = 50,
    model: str = VISUAL_MODEL,
) -> list[dict[str, Any]]:
    """Dense visual search over keyframe images using pgvector cosine distance."""
    vec_str = format_vector(query_vector, expected_dim=VISUAL_DIMENSIONS)
    params: dict[str, Any] = {"vec": vec_str, "model": model, "limit": limit}

    sql = text(
        """
        SELECT
            img.id AS image_id,
            img.asset_id,
            img.segment_id,
            img.storage_key,
            img.caption,
            img.source,
            s.start_s,
            s.end_s,
            a.title AS asset_title,
            a.source_uri AS asset_source_uri,
            1.0 - (v.embedding <=> CAST(:vec AS vector)) AS score
        FROM vec_image v
        JOIN images img ON img.id = v.image_id
        LEFT JOIN segments s ON s.id = img.segment_id
        LEFT JOIN assets a ON a.id = img.asset_id
        WHERE v.model = :model
        ORDER BY v.embedding <=> CAST(:vec AS vector) ASC
        LIMIT :limit
        """
    )
    rows = session.execute(sql, params).mappings().all()
    results: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["image_id"] = str(d["image_id"])
        d["asset_id"] = str(d["asset_id"]) if d["asset_id"] else None
        d["segment_id"] = str(d["segment_id"]) if d["segment_id"] else None
        d["score"] = float(d["score"])
        results.append(d)
    return results


def search_segments_visual(
    session: Session,
    query_vector: list[float] | tuple[float, ...],
    *,
    limit: int = 50,
    model: str = VISUAL_MODEL,
    equipment_family: str | None = None,
) -> list[dict[str, Any]]:
    """Dense visual search over video segments using vec_segment_visual pgvector cosine distance."""
    vec_str = format_vector(query_vector, expected_dim=VISUAL_DIMENSIONS)
    params: dict[str, Any] = {"vec": vec_str, "model": model, "limit": limit}

    filter_clause = ""
    if equipment_family:
        filter_clause = "AND a.equipment_family = :family"
        params["family"] = equipment_family

    sql = text(
        f"""
        SELECT
            s.id AS segment_id,
            s.asset_id,
            s.idx,
            s.start_s,
            s.end_s,
            s.caption,
            s.human_caption,
            s.transcript,
            a.title AS asset_title,
            a.source_uri AS asset_source_uri,
            a.equipment_family,
            1.0 - (v.embedding <=> CAST(:vec AS vector)) AS score
        FROM vec_segment_visual v
        JOIN segments s ON s.id = v.segment_id
        JOIN assets a ON a.id = s.asset_id
        WHERE v.model = :model
          {filter_clause}
        ORDER BY v.embedding <=> CAST(:vec AS vector) ASC
        LIMIT :limit
        """
    )
    rows = session.execute(sql, params).mappings().all()
    results: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["segment_id"] = str(d["segment_id"])
        d["asset_id"] = str(d["asset_id"])
        d["score"] = float(d["score"])
        results.append(d)
    return results


def search_segments_dense(
    session: Session,
    query_vector: list[float] | tuple[float, ...],
    *,
    limit: int = 50,
    model: str = MODEL,
    equipment_family: str | None = None,
) -> list[dict[str, Any]]:
    """Dense vector search over video segments using pgvector cosine distance."""
    vec_str = format_vector(query_vector)
    params: dict[str, Any] = {"vec": vec_str, "model": model, "limit": limit}

    filter_clause = ""
    if equipment_family:
        filter_clause = "AND a.equipment_family = :family"
        params["family"] = equipment_family

    sql = text(
        f"""
        SELECT
            s.id AS segment_id,
            s.asset_id,
            s.idx,
            s.start_s,
            s.end_s,
            s.caption,
            s.human_caption,
            s.transcript,
            a.title AS asset_title,
            a.source_uri AS asset_source_uri,
            a.equipment_family,
            1.0 - (v.embedding <=> CAST(:vec AS vector)) AS score
        FROM vec_segment_text v
        JOIN segments s ON s.id = v.segment_id
        JOIN assets a ON a.id = s.asset_id
        WHERE v.model = :model
          {filter_clause}
        ORDER BY v.embedding <=> CAST(:vec AS vector) ASC
        LIMIT :limit
        """
    )
    rows = session.execute(sql, params).mappings().all()
    results: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["segment_id"] = str(d["segment_id"])
        d["asset_id"] = str(d["asset_id"])
        d["score"] = float(d["score"])
        results.append(d)
    return results


def search_chunks_dense(
    session: Session,
    query_vector: list[float] | tuple[float, ...],
    *,
    limit: int = 50,
    model: str = MODEL,
    doc_type: str | None = None,
) -> list[dict[str, Any]]:
    """Dense vector search over document chunks using pgvector cosine distance."""
    vec_str = format_vector(query_vector)
    params: dict[str, Any] = {"vec": vec_str, "model": model, "limit": limit}

    filter_clause = ""
    if doc_type:
        filter_clause = "AND c.doc_type = :doc_type"
        params["doc_type"] = doc_type

    sql = text(
        f"""
        SELECT
            c.id AS chunk_id,
            c.asset_id,
            c.idx,
            c.doc_type,
            c.section_path,
            c.page_from,
            c.page_to,
            c.text,
            c.token_count,
            a.title AS asset_title,
            1.0 - (v.embedding <=> CAST(:vec AS vector)) AS score
        FROM vec_chunk v
        JOIN chunks c ON c.id = v.chunk_id
        JOIN assets a ON a.id = c.asset_id
        WHERE v.model = :model
          {filter_clause}
        ORDER BY v.embedding <=> CAST(:vec AS vector) ASC
        LIMIT :limit
        """
    )
    rows = session.execute(sql, params).mappings().all()
    results: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["chunk_id"] = str(d["chunk_id"])
        d["asset_id"] = str(d["asset_id"])
        d["score"] = float(d["score"])
        results.append(d)
    return results


def search_chunks_lexical(
    session: Session,
    query_text: str,
    *,
    limit: int = 50,
    doc_type: str | None = None,
) -> list[dict[str, Any]]:
    """Lexical full-text search over document chunks using GIN tsvector index."""
    cleaned = query_text.strip()
    if not cleaned:
        return []

    params: dict[str, Any] = {"q": cleaned, "limit": limit}
    filter_clause = ""
    if doc_type:
        filter_clause = "AND c.doc_type = :doc_type"
        params["doc_type"] = doc_type

    sql = text(
        f"""
        SELECT
            c.id AS chunk_id,
            c.asset_id,
            c.idx,
            c.doc_type,
            c.section_path,
            c.page_from,
            c.page_to,
            c.text,
            c.token_count,
            a.title AS asset_title,
            ts_rank_cd(c.tsv, plainto_tsquery('english', :q)) AS score
        FROM chunks c
        JOIN assets a ON a.id = c.asset_id
        WHERE c.tsv @@ plainto_tsquery('english', :q)
          {filter_clause}
        ORDER BY score DESC
        LIMIT :limit
        """
    )
    rows = session.execute(sql, params).mappings().all()
    results: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["chunk_id"] = str(d["chunk_id"])
        d["asset_id"] = str(d["asset_id"])
        d["score"] = float(d["score"])
        results.append(d)
    return results


def reciprocal_rank_fusion(
    ranked_lists: list[list[dict[str, Any]]],
    id_key: str = "chunk_id",
    k: int = 60,
    top_n: int = 30,
) -> list[dict[str, Any]]:
    """Spec 8.4: Reciprocal Rank Fusion across retrieval lanes.

    RRF_score(d) = sum_{lane} (1 / (k + rank(d)))
    """
    scores: dict[str, float] = {}
    items: dict[str, dict[str, Any]] = {}

    for lane in ranked_lists:
        for rank_idx, item in enumerate(lane, start=1):
            doc_id = str(item[id_key])
            if doc_id not in items:
                items[doc_id] = dict(item)
            rrf_delta = 1.0 / (k + rank_idx)
            scores[doc_id] = scores.get(doc_id, 0.0) + rrf_delta

    sorted_ids = sorted(scores.keys(), key=lambda did: scores[did], reverse=True)[:top_n]
    fused: list[dict[str, Any]] = []
    for did in sorted_ids:
        merged = items[did]
        merged["rrf_score"] = scores[did]
        fused.append(merged)
    return fused


class SearchService:
    """Orchestrates embedding generation, dense vector search, and hybrid fusion."""

    def __init__(
        self,
        client: BgeM3Client,
        visual_client: SiglipVisualClient | None = None,
    ):
        self._client = client
        self._visual_client = visual_client

    def search_images(
        self,
        session: Session,
        query: str,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search keyframe images using SigLIP 2 visual-text query embedding."""
        if not self._visual_client:
            raise SearchError("Visual search client is not configured")
        if not query.strip():
            raise ValueError("Query string cannot be empty")
        batch = self._visual_client.embed_texts([query.strip()])
        query_vector = batch.vectors[0]
        return search_images_visual(session, query_vector, limit=limit)

    def search_video_segments(
        self,
        session: Session,
        query: str,
        *,
        limit: int = 20,
        equipment_family: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search video segments using dense BGE-M3 text query embedding."""
        if not query.strip():
            raise ValueError("Query string cannot be empty")
        batch = self._client.embed([query.strip()])
        query_vector = batch.vectors[0]
        hits = search_segments_dense(
            session,
            query_vector,
            limit=limit,
            equipment_family=equipment_family,
        )
        for h in hits:
            caption = h.get("caption") or h.get("human_caption") or ""
            start_s = float(h.get("start_s", 0.0))
            end_s = float(h.get("end_s", 0.0))
            refined = refine_temporal_span(query, start_s, end_s, caption=caption)
            h["refined_start_s"] = refined.start_s
            h["refined_end_s"] = refined.end_s
            h["seek_to_s"] = refined.seek_to_s
        return hits

    def search_documents_hybrid(
        self,
        session: Session,
        query: str,
        *,
        limit: int = 20,
        doc_type: str | None = None,
        rrf_k: int = 60,
    ) -> list[dict[str, Any]]:
        """Hybrid search combining dense BGE-M3 vectors and BM25 lexical search with RRF."""
        if not query.strip():
            raise ValueError("Query string cannot be empty")
        cleaned = query.strip()

        # Dense lane
        batch = self._client.embed([cleaned])
        query_vector = batch.vectors[0]
        dense_hits = search_chunks_dense(session, query_vector, limit=limit * 2, doc_type=doc_type)

        # Lexical lane
        lexical_hits = search_chunks_lexical(session, cleaned, limit=limit * 2, doc_type=doc_type)

        # Fuse
        return reciprocal_rank_fusion(
            [dense_hits, lexical_hits],
            id_key="chunk_id",
            k=rrf_k,
            top_n=limit,
        )

    def search_multimodal(
        self,
        session: Session,
        query: str,
        *,
        limit: int = 10,
        equipment_family: str | None = None,
        link_expansion: bool = True,
        expansion_discount: float = 0.7,
        max_expansion_neighbours: int = 2,
    ) -> dict[str, Any]:
        """Unified multi-modal search combining video segments, document chunks, and evidence-link graph expansion (§8.5)."""
        if not query.strip():
            raise ValueError("Query string cannot be empty")
        cleaned = query.strip()

        # Step 1: Video segment lane (dense + refinement)
        video_segments = self.search_video_segments(
            session,
            cleaned,
            limit=limit,
            equipment_family=equipment_family,
        )
        for s in video_segments:
            s.setdefault("lanes", ["segment_dense"])

        # Step 2: Document chunks lane (dense + BM25 hybrid RRF)
        document_chunks = self.search_documents_hybrid(
            session,
            cleaned,
            limit=limit,
        )
        for c in document_chunks:
            c.setdefault("lanes", ["chunk_hybrid_rrf"])

        # Step 3: Evidence-link graph expansion (§8.5)
        expanded_segments, expanded_chunks = expand_candidates(
            session,
            video_segments,
            document_chunks,
            query_text=cleaned,
            enabled=link_expansion,
            discount=expansion_discount,
            max_per_item=max_expansion_neighbours,
        )

        # Step 4: Keyframe visual image lane (§7.1, §8.3)
        images: list[dict[str, Any]] = []
        if self._visual_client:
            try:
                images = self.search_images(session, cleaned, limit=limit)
                for img in images:
                    img.setdefault("lanes", ["image_visual"])
            except Exception:
                pass

        return {
            "query": cleaned,
            "modality": "all",
            "link_expansion_enabled": link_expansion,
            "video_segments": expanded_segments[:limit],
            "document_chunks": expanded_chunks[:limit],
            "images": images[:limit],
        }
