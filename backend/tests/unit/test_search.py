import pytest
from app.embeddings import DIMENSIONS
from app.search import (
    format_vector,
    reciprocal_rank_fusion,
)


def test_format_vector_success():
    vec = [0.1] * DIMENSIONS
    formatted = format_vector(vec)
    assert formatted.startswith("[0.1,")
    assert formatted.endswith(",0.1]")
    assert len(formatted.split(",")) == DIMENSIONS


@pytest.mark.parametrize("dim", [0, 1, 1023, 1025])
def test_format_vector_wrong_dimension(dim):
    with pytest.raises(ValueError, match=f"exactly {DIMENSIONS}"):
        format_vector([0.5] * dim)


@pytest.mark.parametrize("bad_val", [float("nan"), float("inf"), float("-inf")])
def test_format_vector_non_finite(bad_val):
    vec = [0.1] * (DIMENSIONS - 1) + [bad_val]
    with pytest.raises(ValueError, match="non-finite"):
        format_vector(vec)


def test_reciprocal_rank_fusion_order():
    lane1 = [
        {"chunk_id": "c1", "text": "pump maintenance"},
        {"chunk_id": "c2", "text": "bearing overhaul"},
    ]
    lane2 = [
        {"chunk_id": "c2", "text": "bearing overhaul"},
        {"chunk_id": "c3", "text": "shaft alignment"},
    ]

    fused = reciprocal_rank_fusion([lane1, lane2], id_key="chunk_id", k=60, top_n=10)
    # c2 appears at rank 2 in lane 1 (1/62) and rank 1 in lane 2 (1/61)
    # total score: 1/62 + 1/61 = 0.0325
    # c1 appears only in lane 1 at rank 1 (1/61 = 0.0164)
    # c3 appears only in lane 2 at rank 2 (1/62 = 0.0161)
    # Therefore order must be c2, c1, c3
    ids = [item["chunk_id"] for item in fused]
    assert ids == ["c2", "c1", "c3"]
    assert fused[0]["rrf_score"] > fused[1]["rrf_score"] > fused[2]["rrf_score"]


def test_reciprocal_rank_fusion_empty():
    assert reciprocal_rank_fusion([], id_key="chunk_id") == []
    assert reciprocal_rank_fusion([[]], id_key="chunk_id") == []
