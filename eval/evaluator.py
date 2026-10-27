"""Core evaluation logic and data structures for Trace retrieval benchmarks.

Strictly adheres to records/ENGINEERING_SPEC.md §1.4, §13.3, and §16:
- Whole-video retrieval evaluates deduplicated asset rankings against essential asset IDs.
- Segment-level retrieval evaluates raw segment hits.
- Temporal IoU verifies top-1 retrieved segment against matching asset-specific gold intervals.
- Unanswerable queries evaluate abstention rate based on similarity threshold.
- Pure functions suitable for unit testing with offline fixtures.
"""

from math import isfinite
from typing import Any

from eval.metrics import recall_at_k, reciprocal_rank, temporal_iou


def deduplicate_video_ranking(results: list[dict[str, Any]]) -> list[str]:
    """Extract deduplicated list of asset IDs in order of first appearance."""
    seen = set()
    ranked_videos = []
    for r in results:
        aid = str(r.get("asset_id", ""))
        if aid and aid not in seen:
            seen.add(aid)
            ranked_videos.append(aid)
    return ranked_videos


def compute_temporal_iou_for_top1(
    top_seg: dict[str, Any] | None,
    gold_spans_by_asset: dict[str, list[list[float]]],
    *,
    use_refined: bool = True,
) -> float:
    """Compute temporal IoU for top-1 segment against the target asset's gold intervals.

    If use_refined is True and refined_start_s / refined_end_s are present,
    evaluates the predicted refined moment. Otherwise evaluates raw segment bounds.
    Returns 0.0 if results are empty, top segment is from a non-gold video,
    or intervals are non-overlapping.
    """
    if not top_seg:
        return 0.0

    asset_id = str(top_seg.get("asset_id", ""))
    spans = gold_spans_by_asset.get(asset_id, [])
    if not spans:
        return 0.0

    try:
        if use_refined and "refined_start_s" in top_seg and "refined_end_s" in top_seg:
            start = float(top_seg["refined_start_s"])
            end = float(top_seg["refined_end_s"])
        else:
            start = float(top_seg.get("start_s", 0.0))
            end = float(top_seg.get("end_s", 0.0))

        if not (isfinite(start) and isfinite(end) and 0 <= start < end):
            return 0.0
        pred_span = (start, end)

        best_iou = 0.0
        for span in spans:
            g_start, g_end = float(span[0]), float(span[1])
            if isfinite(g_start) and isfinite(g_end) and 0 <= g_start < g_end:
                iou = temporal_iou(pred_span, (g_start, g_end))
                if iou > best_iou:
                    best_iou = iou
        return best_iou
    except (ValueError, TypeError, IndexError):
        return 0.0


def evaluate_single_query(
    query_record: dict[str, Any],
    retrieved_results: list[dict[str, Any]],
    abstention_threshold: float = 0.55,
) -> dict[str, Any]:
    """Evaluate one query against retrieved search results.

    Handles both answerable video-only queries and unanswerable queries.
    """
    qtype = query_record.get("type", "video-only")
    top_score = float(retrieved_results[0]["score"]) if retrieved_results else 0.0

    if qtype == "unanswerable":
        abstained = top_score < abstention_threshold
        return {
            "query_id": query_record.get("query_id"),
            "type": "unanswerable",
            "query": query_record.get("query"),
            "top_score": top_score,
            "abstained": abstained,
            "correct": abstained,
        }

    # Answerable query
    essential_assets = set(query_record.get("essential_asset_ids", []))
    essential_segments = set(query_record.get("essential_segment_ids", []))

    # 1. Whole-video evaluation (deduplicated by asset)
    ranked_videos = deduplicate_video_ranking(retrieved_results)
    v_r1 = recall_at_k(ranked_videos, essential_assets, k=1) if essential_assets else 0.0
    v_r3 = recall_at_k(ranked_videos, essential_assets, k=3) if essential_assets else 0.0
    v_r5 = recall_at_k(ranked_videos, essential_assets, k=5) if essential_assets else 0.0
    v_r10 = recall_at_k(ranked_videos, essential_assets, k=10) if essential_assets else 0.0
    v_mrr = reciprocal_rank(ranked_videos, essential_assets, k=20) if essential_assets else 0.0

    # 2. Segment-level evaluation (raw segment hits)
    ranked_segments = [str(r["segment_id"]) for r in retrieved_results]
    s_r1 = recall_at_k(ranked_segments, essential_segments, k=1) if essential_segments else 0.0
    s_r5 = recall_at_k(ranked_segments, essential_segments, k=5) if essential_segments else 0.0
    s_mrr = (
        reciprocal_rank(ranked_segments, essential_segments, k=20)
        if essential_segments
        else 0.0
    )

    # 3. Asset-aware temporal IoU (evaluates predicted refined span; also records raw segment IoU)
    top_seg = retrieved_results[0] if retrieved_results else None
    gold_spans = query_record.get("gold_spans_by_asset", {})
    iou = compute_temporal_iou_for_top1(top_seg, gold_spans, use_refined=True)
    raw_iou = compute_temporal_iou_for_top1(top_seg, gold_spans, use_refined=False)

    return {
        "query_id": query_record.get("query_id"),
        "type": "video-only",
        "query": query_record.get("query"),
        "action_label": query_record.get("action_label"),
        "top_score": top_score,
        "video_recall@1": v_r1,
        "video_recall@3": v_r3,
        "video_recall@5": v_r5,
        "video_recall@10": v_r10,
        "video_mrr@20": v_mrr,
        "segment_recall@1": s_r1,
        "segment_recall@5": s_r5,
        "segment_mrr@20": s_mrr,
        "temporal_iou": iou,
        "raw_segment_iou": raw_iou,
        "iou_at_03": 1.0 if iou >= 0.3 else 0.0,
        "iou_at_05": 1.0 if iou >= 0.5 else 0.0,
    }
