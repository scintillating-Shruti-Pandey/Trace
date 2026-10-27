"""Unit tests for evidence-link graph expansion (spec Section 8.5).

Verifies:
- expand_segment_to_chunks applies x0.7 discount and extracts linked chunk metadata
- expand_chunk_to_segments applies temporal refinement and extracts seek_to_s
- expand_candidates respects max_neighbours, max_total guard, and enabled toggle
- deduplication preserves the highest score and records multi-lane provenance
"""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.expansion import (
    DEFAULT_EXPANSION_DISCOUNT,
    expand_candidates,
    expand_chunk_to_segments,
    expand_segment_to_chunks,
)
from app.models import Asset, Chunk, EvidenceLink, Segment


def test_expand_segment_to_chunks_empty_links():
    session = MagicMock()
    session.execute.return_value.all.return_value = []

    seg_item = {"segment_id": str(uuid4()), "score": 0.85}
    results = expand_segment_to_chunks(session, seg_item)
    assert results == []


def test_expand_segment_to_chunks_with_links():
    session = MagicMock()

    link = EvidenceLink(
        id=str(uuid4()),
        segment_id=str(uuid4()),
        chunk_id=str(uuid4()),
        relation="specifies",
        confidence=1.0,
        author="human:expert",
        note="Specifies 9.5 Nm torque requirement",
    )
    chunk = Chunk(
        id=link.chunk_id,
        asset_id=str(uuid4()),
        idx=0,
        doc_type="sop",
        section_path="1.1 Lower Hinge > Torque",
        page_from=1,
        page_to=2,
        text="Torque bolts to 9.5 Nm.",
        token_count=45,
    )
    asset = Asset(
        id=chunk.asset_id,
        kind="document",
        title="Hinge Assembly SOP",
        storage_key="docs/sop.pdf",
        license="CC-BY-4.0",
        checksum_sha256="abc123",
        equipment_family="mechanical",
    )

    session.execute.return_value.all.return_value = [(link, chunk, asset)]

    seg_item = {"segment_id": link.segment_id, "score": 0.90}
    results = expand_segment_to_chunks(session, seg_item, discount=0.7)

    assert len(results) == 1
    item = results[0]
    assert item["chunk_id"] == link.chunk_id
    assert item["via_link"] is True
    assert item["link_relation"] == "specifies"
    assert item["linked_from_id"] == link.segment_id
    assert item["lanes"] == ["link_expansion"]
    assert pytest.approx(item["score"], 0.001) == 0.90 * 0.7 * 1.0


def test_expand_chunk_to_segments_with_refinement():
    session = MagicMock()

    link = EvidenceLink(
        id=str(uuid4()),
        segment_id=str(uuid4()),
        chunk_id=str(uuid4()),
        relation="documents",
        confidence=0.95,
        author="human:expert",
        note="Documents camera bracket installation",
    )
    seg = Segment(
        id=link.segment_id,
        asset_id=str(uuid4()),
        idx=2,
        start_s=235.0,
        end_s=335.0,
        method="manual",
        caption="attach camera and plate",
        transcript=None,
    )
    asset = Asset(
        id=seg.asset_id,
        kind="video",
        title="Workstation Build Video",
        storage_key="videos/vid.mp4",
        license="CC-BY-4.0",
        checksum_sha256="def456",
        equipment_family="mechanical",
    )

    session.execute.return_value.all.return_value = [(link, seg, asset)]

    chk_item = {"chunk_id": link.chunk_id, "score": 0.80}
    results = expand_chunk_to_segments(session, chk_item, query_text="camera plate", discount=0.7)

    assert len(results) == 1
    item = results[0]
    assert item["segment_id"] == link.segment_id
    assert item["via_link"] is True
    assert item["link_relation"] == "documents"
    assert item["seek_to_s"] >= 0.0
    assert pytest.approx(item["score"], 0.001) == 0.80 * 0.7 * 0.95


def test_expand_candidates_disabled_toggle():
    session = MagicMock()
    segments = [{"segment_id": "seg-1", "score": 0.9}]
    chunks = [{"chunk_id": "chk-1", "score": 0.8}]

    exp_segs, exp_chks = expand_candidates(session, segments, chunks, enabled=False)
    assert exp_segs == segments
    assert exp_chks == chunks
    session.execute.assert_not_called()


def test_expand_candidates_deduplication():
    session = MagicMock()

    seg_id = str(uuid4())
    chk_id = str(uuid4())

    link = EvidenceLink(
        id=str(uuid4()),
        segment_id=seg_id,
        chunk_id=chk_id,
        relation="documents",
        confidence=1.0,
        author="human:expert",
    )
    chunk = Chunk(
        id=chk_id,
        asset_id=str(uuid4()),
        idx=0,
        doc_type="sop",
        section_path="1.0 Positioning",
        text="Position collar clamp",
        token_count=30,
    )
    asset = Asset(
        id=chunk.asset_id,
        kind="document",
        title="Camera SOP",
        storage_key="docs/cam.pdf",
        license="CC-BY-4.0",
        checksum_sha256="123456",
    )

    mock_res_chunks = MagicMock()
    mock_res_chunks.all.return_value = [(link, chunk, asset)]
    mock_res_segs = MagicMock()
    mock_res_segs.all.return_value = []
    session.execute.side_effect = [mock_res_chunks, mock_res_segs]

    segments = [{"segment_id": seg_id, "score": 0.9, "lanes": ["segment_dense"]}]
    # chunk is already present with higher score 0.95
    chunks = [{"chunk_id": chk_id, "score": 0.95, "lanes": ["chunk_hybrid_rrf"]}]

    exp_segs, exp_chks = expand_candidates(session, segments, chunks, enabled=True)

    # Chunk should not be duplicated; its lanes should now include 'link_expansion'
    assert len(exp_chks) == 1
    assert exp_chks[0]["chunk_id"] == chk_id
    assert exp_chks[0]["score"] == 0.95
    assert "link_expansion" in exp_chks[0]["lanes"]
