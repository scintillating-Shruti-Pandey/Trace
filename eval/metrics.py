"""Per-query metrics from spec 13.3. Average only across eligible query types.

Queries with no essential gold must be evaluated for abstention, not recall.
Duplicate retrieved IDs are rejected so repeated hits cannot inflate nDCG.
"""

from math import isfinite, log2


def _ranking(retrieved: list[str], k: int):
    if k < 1:
        raise ValueError("k must be positive")
    if len(retrieved) != len(set(retrieved)):
        raise ValueError("retrieved IDs must be unique")
    return retrieved[:k]


def recall_at_k(retrieved: list[str], essential: set[str], k: int = 5) -> float:
    if not essential:
        raise ValueError("recall requires at least one essential gold item")
    return float(bool(set(_ranking(retrieved, k)) & essential))


def full_set_recall_at_k(retrieved: list[str], essential: set[str], k: int = 5) -> float:
    if not essential:
        raise ValueError("full-set recall requires essential gold items")
    return float(essential.issubset(_ranking(retrieved, k)))


def reciprocal_rank(retrieved: list[str], essential: set[str], k: int = 20) -> float:
    if not essential:
        raise ValueError("MRR requires essential gold items")
    return next(
        (1.0 / rank for rank, item in enumerate(_ranking(retrieved, k), 1) if item in essential),
        0.0,
    )


def ndcg_at_k(retrieved: list[str], grades: dict[str, int], k: int = 10) -> float:
    if not grades or any(grade not in {1, 2} for grade in grades.values()):
        raise ValueError("gold grades must be 1 (helpful) or 2 (essential)")
    ranked = _ranking(retrieved, k)
    dcg = sum(
        (2 ** grades.get(item, 0) - 1) / log2(rank + 1) for rank, item in enumerate(ranked, 1)
    )
    ideal = sum(
        (2**grade - 1) / log2(rank + 1)
        for rank, grade in enumerate(sorted(grades.values(), reverse=True)[:k], 1)
    )
    return dcg / ideal


def temporal_iou(predicted: tuple[float, float], gold: tuple[float, float]) -> float:
    for start, end in (predicted, gold):
        if not isfinite(start) or not isfinite(end) or start < 0 or end <= start:
            raise ValueError("spans must be finite with 0 <= start < end")
    overlap = max(0, min(predicted[1], gold[1]) - max(predicted[0], gold[0]))
    union = predicted[1] - predicted[0] + gold[1] - gold[0] - overlap
    return overlap / union
