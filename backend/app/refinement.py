"""Coarse-to-fine temporal refinement for video retrieval (spec §8.7).

Retrieval returns coarse segments (e.g., 30s windows).
Temporal refinement localizes the specific moment (e.g., 6–10s) based on:
1. Caption action clause temporal alignment and query term overlap
2. Sliding window scoring across the coarse segment span
3. Clamping to segment boundaries (±5s)
4. Computing human seek jump point with a 2-second lead-in (max(0, start - 2s))
"""

import math
import re
from dataclasses import dataclass

DEFAULT_WINDOW_SIZE_S = 8.0
DEFAULT_STRIDE_S = 1.0
DEFAULT_LEAD_IN_S = 2.0
CLAMP_EXPANSION_S = 5.0

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "at", "by", "for",
    "with", "about", "against", "between", "into", "through", "during", "before",
    "after", "above", "below", "from", "up", "down", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did", "this",
    "that", "these", "those", "it", "its", "procedure", "window", "video", "indego"
}


@dataclass(frozen=True)
class RefinedSpan:
    """Refined temporal prediction with seek jump point and confidence."""
    start_s: float
    end_s: float
    seek_to_s: float
    confidence: float


def tokenize_terms(text: str) -> set[str]:
    """Tokenize string into normalized lowercase terms excluding common stopwords."""
    if not text:
        return set()
    raw_tokens = re.findall(r"\b[a-zA-Z0-9_\-]+\b", text.lower())
    terms = set()
    for token in raw_tokens:
        clean = token.replace("_", " ").replace("-", " ").strip()
        for sub in clean.split():
            if len(sub) > 1 and sub not in STOPWORDS:
                terms.add(sub)
    return terms


def parse_action_clauses(caption: str) -> list[str]:
    """Extract distinct action phrases from a segmented procedure caption."""
    if not caption:
        return []
    # Strip asset title and timestamp prefixes like "[30s–60s]: "
    cleaned = re.sub(r"^.*?\[\d+s[–\-]\d+s\]:\s*", "", caption).strip()
    if not cleaned:
        cleaned = caption.strip()
    # Split by semicolon or comma if multiple actions are concatenated
    parts = re.split(r"[;,]\s*", cleaned)
    clauses = [p.strip() for p in parts if p.strip()]
    return clauses if clauses else [cleaned]


def score_window_overlap(
    w_start: float,
    w_end: float,
    action_intervals: list[tuple[float, float, set[str]]],
    query_terms: set[str],
) -> float:
    """Calculate query-term overlap score for a candidate sub-window."""
    if not query_terms or not action_intervals:
        return 0.0

    total_score = 0.0
    for act_start, act_end, act_terms in action_intervals:
        # Overlap length between candidate window and action interval
        overlap = max(0.0, min(w_end, act_end) - max(w_start, act_start))
        if overlap <= 0.0:
            continue

        matched_terms = query_terms.intersection(act_terms)
        if matched_terms:
            term_ratio = len(matched_terms) / len(query_terms)
            total_score += overlap * term_ratio

    return total_score


def refine_temporal_span(
    query: str,
    start_s: float,
    end_s: float,
    caption: str = "",
    *,
    window_size_s: float = DEFAULT_WINDOW_SIZE_S,
    stride_s: float = DEFAULT_STRIDE_S,
    lead_in_s: float = DEFAULT_LEAD_IN_S,
) -> RefinedSpan:
    """Refine a coarse retrieved segment [start_s, end_s] into a focused moment.

    Follows spec §8.7:
    - Slides a fine window across the segment interval
    - Scores windows by action term match with query
    - Clamps predicted boundaries to [max(0, start_s - 5s), end_s + 5s]
    - Computes seek jump point: max(0, pred_start - lead_in_s)
    """
    # Guard against invalid, non-finite, or inverted boundaries
    if not (math.isfinite(start_s) and math.isfinite(end_s) and start_s < end_s):
        safe_start = max(0.0, start_s if math.isfinite(start_s) else 0.0)
        return RefinedSpan(
            start_s=safe_start,
            end_s=safe_start,
            seek_to_s=max(0.0, safe_start - lead_in_s),
            confidence=0.0,
        )

    duration = end_s - start_s
    # If segment is shorter than or equal to fine window size, keep entire segment
    if duration <= window_size_s:
        return RefinedSpan(
            start_s=round(start_s, 2),
            end_s=round(end_s, 2),
            seek_to_s=round(max(0.0, start_s - lead_in_s), 2),
            confidence=1.0,
        )

    query_terms = tokenize_terms(query)
    clauses = parse_action_clauses(caption)

    # Allocate sub-intervals for each action clause across the coarse segment
    num_clauses = max(1, len(clauses))
    clause_dur = duration / num_clauses
    action_intervals: list[tuple[float, float, set[str]]] = []
    for idx, clause in enumerate(clauses):
        c_start = start_s + idx * clause_dur
        c_end = start_s + (idx + 1) * clause_dur
        action_intervals.append((c_start, c_end, tokenize_terms(clause)))

    # Identify action clauses that match query terms
    matching_clause_indices = []
    for idx, (_, _, act_terms) in enumerate(action_intervals):
        if act_terms.intersection(query_terms):
            matching_clause_indices.append(idx)

    if matching_clause_indices:
        # Expand span to cover the full extent of matching action clauses (spec §8.7)
        first_idx = min(matching_clause_indices)
        last_idx = max(matching_clause_indices)
        best_start = action_intervals[first_idx][0]
        best_end = action_intervals[last_idx][1]
        best_score = float(len(matching_clause_indices))
    else:
        # Fall back to sliding sub-window argmax
        best_start = start_s + (duration - window_size_s) / 2.0  # default to middle
        best_end = best_start + window_size_s
        best_score = -1.0

        current = start_s
        while current + window_size_s <= end_s + 1e-4:
            w_start = current
            w_end = current + window_size_s
            score = score_window_overlap(w_start, w_end, action_intervals, query_terms)

            if score > best_score:
                best_score = score
                best_start = w_start
                best_end = w_end

            current += stride_s

    # Boundary clamping (spec §8.7: clamped to segment ±5s)
    min_bound = max(0.0, start_s - CLAMP_EXPANSION_S)
    max_bound = end_s + CLAMP_EXPANSION_S
    clamped_start = max(min_bound, min(best_start, max_bound))
    clamped_end = max(clamped_start + 1.0, min(best_end, max_bound))

    # Lead-in seek timestamp (spec §8.7, §11.2)
    seek_to_s = max(0.0, clamped_start - lead_in_s)
    confidence = min(1.0, best_score / max(1.0, len(query_terms))) if best_score > 0 else 0.5

    return RefinedSpan(
        start_s=round(clamped_start, 2),
        end_s=round(clamped_end, 2),
        seek_to_s=round(seek_to_s, 2),
        confidence=round(confidence, 3),
    )
