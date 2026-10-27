"""Unit tests for retrieval evaluation logic in eval.evaluator.

Tests whole-video deduplication, asset-aware temporal IoU, segment hit rate,
and unanswerable query abstention using deterministic offline fixtures.
"""

from eval.evaluator import (
    compute_temporal_iou_for_top1,
    deduplicate_video_ranking,
    evaluate_single_query,
)


def test_deduplicate_video_ranking():
    # Segments from videos A, B, A, C, B
    results = [
        {"asset_id": "vid-A", "segment_id": "seg-1"},
        {"asset_id": "vid-B", "segment_id": "seg-2"},
        {"asset_id": "vid-A", "segment_id": "seg-3"},
        {"asset_id": "vid-C", "segment_id": "seg-4"},
        {"asset_id": "vid-B", "segment_id": "seg-5"},
    ]
    ranked = deduplicate_video_ranking(results)
    assert ranked == ["vid-A", "vid-B", "vid-C"]


def test_deduplicate_video_ranking_empty():
    assert deduplicate_video_ranking([]) == []


def test_compute_temporal_iou_matching_asset():
    gold_spans = {
        "vid-A": [[10.0, 30.0]],
        "vid-B": [[50.0, 80.0]],
    }

    # Top segment is in vid-A and overlaps [15.0, 35.0]
    # Overlap: [15, 30] = 15; Union: [10, 35] = 25 -> IoU = 15/25 = 0.6
    top_seg = {"asset_id": "vid-A", "start_s": 15.0, "end_s": 35.0}
    iou = compute_temporal_iou_for_top1(top_seg, gold_spans)
    assert abs(iou - 0.6) < 1e-4


def test_compute_temporal_iou_wrong_asset_returns_zero():
    gold_spans = {
        "vid-A": [[10.0, 30.0]],
    }

    # Top segment has exact same timestamps [10.0, 30.0] but belongs to vid-C!
    # Must return 0.0 because it's a completely different video.
    top_seg = {"asset_id": "vid-C", "start_s": 10.0, "end_s": 30.0}
    iou = compute_temporal_iou_for_top1(top_seg, gold_spans)
    assert iou == 0.0


def test_compute_temporal_iou_empty_or_invalid():
    gold_spans = {"vid-A": [[10.0, 30.0]]}
    assert compute_temporal_iou_for_top1(None, gold_spans) == 0.0
    assert compute_temporal_iou_for_top1({}, gold_spans) == 0.0
    # Inverted span (end < start)
    assert compute_temporal_iou_for_top1(
        {"asset_id": "vid-A", "start_s": 30.0, "end_s": 10.0}, gold_spans
    ) == 0.0


def test_evaluate_single_query_whole_video_vs_segment():
    query_record = {
        "query_id": "q-001",
        "type": "video-only",
        "query": "assemble hinge",
        "essential_asset_ids": ["vid-A"],
        "essential_segment_ids": ["seg-gold-1"],
        "gold_spans_by_asset": {"vid-A": [[10.0, 40.0]]},
    }

    # Scenario:
    # Rank 1 is vid-A, but a window segment (seg-window-99), not seg-gold-1.
    # Rank 2 is vid-B.
    # Rank 3 is vid-A with seg-gold-1.
    results = [
        {
            "asset_id": "vid-A",
            "segment_id": "seg-window-99",
            "start_s": 10.0,
            "end_s": 40.0,
            "score": 0.85,
        },
        {
            "asset_id": "vid-B",
            "segment_id": "seg-other-2",
            "start_s": 0.0,
            "end_s": 30.0,
            "score": 0.70,
        },
        {
            "asset_id": "vid-A",
            "segment_id": "seg-gold-1",
            "start_s": 10.0,
            "end_s": 40.0,
            "score": 0.65,
        },
    ]

    metrics = evaluate_single_query(query_record, results)

    # Whole-video retrieval: vid-A is at rank 1!
    assert metrics["video_recall@1"] == 1.0
    assert metrics["video_recall@5"] == 1.0
    assert metrics["video_mrr@20"] == 1.0

    # Segment-level retrieval: seg-gold-1 is at rank 3, NOT rank 1!
    assert metrics["segment_recall@1"] == 0.0
    assert metrics["segment_recall@5"] == 1.0
    assert abs(metrics["segment_mrr@20"] - (1.0 / 3.0)) < 1e-4

    # Temporal IoU for top-1 segment (seg-window-99 is in vid-A, exactly covers [10, 40])
    assert abs(metrics["temporal_iou"] - 1.0) < 1e-4


def test_evaluate_single_query_unanswerable():
    unanswerable = {
        "query_id": "u-001",
        "type": "unanswerable",
        "query": "unrelated procedure",
    }

    # Case 1: Low similarity score below threshold (0.55) -> abstained correctly
    low_res = [{"score": 0.42, "asset_id": "vid-X", "segment_id": "s-1"}]
    res1 = evaluate_single_query(unanswerable, low_res, abstention_threshold=0.55)
    assert res1["abstained"] is True
    assert res1["correct"] is True

    # Case 2: High similarity score above threshold (0.55) -> failed to abstain
    high_res = [{"score": 0.68, "asset_id": "vid-X", "segment_id": "s-1"}]
    res2 = evaluate_single_query(unanswerable, high_res, abstention_threshold=0.55)
    assert res2["abstained"] is False
    assert res2["correct"] is False


def test_evaluate_single_query_empty_results():
    query_record = {
        "query_id": "q-empty",
        "type": "video-only",
        "essential_asset_ids": ["vid-A"],
        "essential_segment_ids": ["seg-1"],
        "gold_spans_by_asset": {"vid-A": [[0.0, 10.0]]},
    }

    metrics = evaluate_single_query(query_record, [])
    assert metrics["video_recall@1"] == 0.0
    assert metrics["video_recall@5"] == 0.0
    assert metrics["video_mrr@20"] == 0.0
    assert metrics["segment_recall@1"] == 0.0
    assert metrics["temporal_iou"] == 0.0
