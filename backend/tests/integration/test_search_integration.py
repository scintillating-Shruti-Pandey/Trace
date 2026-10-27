"""Real PostgreSQL/pgvector integration tests for dense and hybrid retrieval.

All inserts run within rollback transactions and never persist into the user's corpus.
"""

import os
from uuid import uuid4

import pytest
from app.config import Settings
from app.db import make_engine
from app.embeddings import DIMENSIONS
from app.models import Asset, Chunk, Image, Segment
from app.search import (
    index_chunk_vector,
    index_image_vector,
    index_segment_vector,
    index_segment_visual_vector,
    reciprocal_rank_fusion,
    search_chunks_dense,
    search_chunks_lexical,
    search_images_visual,
    search_segments_dense,
    search_segments_visual,
)
from app.vision import DIMENSIONS as VISUAL_DIMENSIONS, MODEL as VISUAL_MODEL
from sqlalchemy.orm import Session

pytestmark = pytest.mark.skipif(
    os.environ.get("TRACE_INTEGRATION") != "1",
    reason="set TRACE_INTEGRATION=1 with Compose running",
)


@pytest.fixture
def database():
    engine = make_engine(Settings())
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()
    engine.dispose()


def test_segment_vector_indexing_and_pgvector_search(database):
    # 1. Create a parent video asset
    vid_asset = Asset(
        kind="video",
        title="Pump Bearing Maintenance",
        source_uri="test://video1",
        storage_key="test/video1.mp4",
        license="CC-BY-4.0",
        equipment_family="hydraulic",
        checksum_sha256=uuid4().hex * 2,
        duration_s=120.0,
    )
    database.add(vid_asset)
    database.flush()

    # 2. Create two segments
    seg1 = Segment(
        asset_id=vid_asset.id,
        idx=0,
        start_s=0.0,
        end_s=30.0,
        method="manual",
        caption="Inspect hydraulic pump bearing wear",
    )
    seg2 = Segment(
        asset_id=vid_asset.id,
        idx=1,
        start_s=30.0,
        end_s=60.0,
        method="manual",
        caption="Tighten flange bolts with torque wrench",
    )
    database.add_all([seg1, seg2])
    database.flush()

    # 3. Create two distinct 1024-d unit vectors
    # Vector 1 has strong component along axis 0
    vec1 = [1.0] + [0.0] * (DIMENSIONS - 1)
    # Vector 2 has strong component along axis 1
    vec2 = [0.0, 1.0] + [0.0] * (DIMENSIONS - 2)

    index_segment_vector(database, seg1.id, vec1)
    index_segment_vector(database, seg2.id, vec2)
    database.flush()

    # 4. Search with query vector aligned with vec1
    query_vec = [0.9] + [0.0] * (DIMENSIONS - 1)
    hits = search_segments_dense(database, query_vec, limit=5, equipment_family="hydraulic")

    assert len(hits) == 2
    # seg1 should rank first with score close to 1.0
    assert hits[0]["segment_id"] == seg1.id
    assert hits[0]["score"] > 0.99
    assert hits[1]["segment_id"] == seg2.id
    assert hits[1]["score"] < 0.1


def test_chunk_vector_and_lexical_hybrid_search(database):
    # 1. Create a parent document asset
    doc_asset = Asset(
        kind="document",
        title="Centrifugal Pump Operating Manual",
        source_uri="test://manual1",
        storage_key="test/manual1.pdf",
        license="CC-BY-4.0",
        equipment_family="rotating",
        checksum_sha256=uuid4().hex * 2,
    )
    database.add(doc_asset)
    database.flush()

    # 2. Create chunks
    chunk1 = Chunk(
        asset_id=doc_asset.id,
        idx=0,
        doc_type="manual",
        section_path="3.2 Lubrication",
        text=(
            "Check oil level in the bearing housing sight glass. "
            "Refill with ISO VG 46 lubrication oil."
        ),
        token_count=18,
    )
    chunk2 = Chunk(
        asset_id=doc_asset.id,
        idx=1,
        doc_type="sop",
        section_path="4.1 Impeller Clearance",
        text="Measure radial clearance using feeler gauges. Record measurement in microns.",
        token_count=16,
    )
    database.add_all([chunk1, chunk2])
    database.flush()

    # 3. Index dense vectors
    vec1 = [1.0] + [0.0] * (DIMENSIONS - 1)
    vec2 = [0.0, 1.0] + [0.0] * (DIMENSIONS - 2)
    index_chunk_vector(database, chunk1.id, vec1)
    index_chunk_vector(database, chunk2.id, vec2)
    database.flush()

    # 4. Dense search
    dense_hits = search_chunks_dense(database, [1.0] + [0.0] * (DIMENSIONS - 1), limit=5)
    assert len(dense_hits) >= 2
    assert dense_hits[0]["chunk_id"] == chunk1.id
    assert dense_hits[0]["score"] > 0.99

    # 5. Lexical search using GIN index on tsvector
    lexical_hits = search_chunks_lexical(database, "bearing oil", limit=5)
    assert len(lexical_hits) >= 1
    assert lexical_hits[0]["chunk_id"] == chunk1.id

    # 6. Reciprocal Rank Fusion
    fused = reciprocal_rank_fusion([dense_hits, lexical_hits], id_key="chunk_id", k=60)
    assert len(fused) >= 2
    assert fused[0]["chunk_id"] == chunk1.id


def test_image_vector_indexing_and_visual_search(database):
    # 1. Create a parent video asset and segment
    asset = Asset(
        kind="video",
        title="Industrial Assembly Workstation",
        source_uri="test://video_vis",
        storage_key="test/video_vis.mp4",
        license="CC-BY-4.0",
        equipment_family="assembly",
        checksum_sha256=uuid4().hex * 2,
        duration_s=180.0,
    )
    database.add(asset)
    database.flush()

    seg = Segment(
        asset_id=asset.id,
        idx=0,
        start_s=10.0,
        end_s=25.0,
        method="manual",
        caption="attach mounting plate",
    )
    database.add(seg)
    database.flush()

    # 2. Create image keyframe
    img = Image(
        asset_id=asset.id,
        segment_id=seg.id,
        storage_key=f"keyframes/{seg.id}.jpg",
        caption="attach mounting plate",
        source="frame",
    )
    database.add(img)
    database.flush()

    # 3. Index visual vectors (1,152 dimensions)
    vec = [1.0] + [0.0] * (VISUAL_DIMENSIONS - 1)
    index_image_vector(database, img.id, vec, model=VISUAL_MODEL)
    index_segment_visual_vector(database, seg.id, vec, model=VISUAL_MODEL)
    database.flush()

    # 4. Search images visual lane
    img_hits = search_images_visual(database, vec, limit=5, model=VISUAL_MODEL)
    assert len(img_hits) >= 1
    assert img_hits[0]["image_id"] == img.id
    assert img_hits[0]["segment_id"] == seg.id
    assert img_hits[0]["score"] > 0.99

    # 5. Search segment visual lane
    seg_hits = search_segments_visual(database, vec, limit=5, model=VISUAL_MODEL)
    assert len(seg_hits) >= 1
    assert seg_hits[0]["segment_id"] == seg.id
    assert seg_hits[0]["score"] > 0.99

