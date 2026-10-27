"""Unit tests for coarse-to-fine temporal refinement (spec §8.7).

Validates:
- Sub-window sliding and argmax localization
- Action clause term matching
- Boundary clamping
- Seek lead-in arithmetic (max(0, start - 2s))
- Edge cases (short segments, zero start, inverted bounds)
"""

from app.refinement import (
    parse_action_clauses,
    refine_temporal_span,
    tokenize_terms,
)


def test_tokenize_terms_and_stopwords():
    terms = tokenize_terms("Disassemble the bearing housing and rotor!")
    # Stopwords 'the' and 'and' should be removed
    assert "the" not in terms
    assert "and" not in terms
    assert "disassemble" in terms
    assert "bearing" in terms
    assert "housing" in terms
    assert "rotor" in terms


def test_parse_action_clauses():
    caption = "IndEgo Assembly 01 [30s–60s]: connect base; attach vertical bar, inspect fixture"
    clauses = parse_action_clauses(caption)
    assert len(clauses) == 3
    assert clauses[0] == "connect base"
    assert clauses[1] == "attach vertical bar"
    assert clauses[2] == "inspect fixture"


def test_refine_temporal_span_short_segment():
    # 6-second segment is shorter than default 8s window
    span = refine_temporal_span(
        query="inspect rotor",
        start_s=12.0,
        end_s=18.0,
        caption="inspect rotor",
    )
    assert span.start_s == 12.0
    assert span.end_s == 18.0
    assert span.seek_to_s == 10.0  # 12 - 2


def test_refine_temporal_span_sub_window_localization():
    # 30-second window [30s–60s] with two sequential actions:
    # 30–45s: "disassemble rotor"
    # 45–60s: "inspect bearing housing"
    caption = "IndEgo Repair [30s–60s]: disassemble rotor; inspect bearing housing"
    
    # Query for the second action
    span = refine_temporal_span(
        query="inspect bearing housing",
        start_s=30.0,
        end_s=60.0,
        caption=caption,
        window_size_s=8.0,
    )
    # The refined 8s window should be localized in the second half (>= 45.0s)
    assert span.start_s >= 45.0
    assert span.end_s <= 60.0
    assert span.seek_to_s == round(span.start_s - 2.0, 2)


def test_refine_temporal_span_seek_lead_in_near_zero():
    # When action starts at 1.0s, seek should clamp at 0.0s (not -1.0s)
    span = refine_temporal_span(
        query="initial setup",
        start_s=1.0,
        end_s=15.0,
        caption="initial setup",
        lead_in_s=2.0,
    )
    assert span.seek_to_s == 0.0


def test_refine_temporal_span_invalid_bounds():
    # Inverted span (end < start)
    span = refine_temporal_span(
        query="test",
        start_s=40.0,
        end_s=20.0,
    )
    assert span.start_s == 40.0
    assert span.end_s == 40.0
    assert span.seek_to_s == 38.0
    assert span.confidence == 0.0
