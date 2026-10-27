from math import log2

import pytest

from eval.metrics import full_set_recall_at_k, ndcg_at_k, recall_at_k, reciprocal_rank, temporal_iou


def test_recall_boundary_and_multi_hop():
    retrieved = ["a", "b", "c", "d", "gold", "other-gold"]
    assert recall_at_k(retrieved, {"gold"}, 5) == 1
    assert recall_at_k(retrieved, {"other-gold"}, 5) == 0
    assert full_set_recall_at_k(retrieved, {"gold", "other-gold"}, 5) == 0
    assert full_set_recall_at_k(retrieved, {"gold", "other-gold"}, 6) == 1


def test_mrr_cutoff():
    assert reciprocal_rank(["a", "b", "g"], {"g"}) == pytest.approx(1 / 3)
    assert reciprocal_rank([str(i) for i in range(21)], {"20"}) == 0


def test_ndcg_graded_and_missing():
    ideal = 3 + 1 / log2(3)
    assert ndcg_at_k(["helpful", "essential"], {"essential": 2, "helpful": 1}) == pytest.approx(
        (1 + 3 / log2(3)) / ideal
    )
    assert ndcg_at_k(["missing"], {"gold": 2}) == 0
    with pytest.raises(ValueError):
        ndcg_at_k(["gold", "gold"], {"gold": 2})


def test_temporal_overlap():
    assert temporal_iou((10, 20), (15, 25)) == pytest.approx(1 / 3)
    assert temporal_iou((0, 10), (20, 30)) == 0
    assert temporal_iou((0, 10), (0, 10)) == 1
    for span in [(5, 5), (-1, 2), (0, float("inf"))]:
        with pytest.raises(ValueError):
            temporal_iou(span, (0, 10))


def test_unanswerable_is_not_a_retrieval_success():
    with pytest.raises(ValueError):
        recall_at_k([], set())
    with pytest.raises(ValueError):
        full_set_recall_at_k([], set())
