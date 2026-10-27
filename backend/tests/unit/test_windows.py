import math

import pytest
from app.ingest.windows import fixed_windows


@pytest.mark.parametrize(
    "duration,expected",
    [
        (8, [(0, 8)]),
        (30, [(0, 30)]),
        (31, [(0, 30), (15, 31)]),
        (45, [(0, 30), (15, 45)]),
        (60, [(0, 30), (15, 45), (30, 60)]),
        (60.25, [(0, 30), (15, 45), (30, 60), (45, 60.25)]),
    ],
)
def test_expected_temporal_boundaries(duration, expected):
    windows = fixed_windows(duration)
    assert [(w.start_s, w.end_s) for w in windows] == expected
    assert all(w.method == "fixed-30s" for w in windows)


def test_coverage_no_gaps_and_no_redundant_tail():
    for duration in [0.01, 29.99, 30.01, 120, 208.4, 876.043, 21600]:
        windows = fixed_windows(duration)
        assert windows[0].start_s == 0
        assert windows[-1].end_s == duration
        assert all(0 <= w.start_s < w.end_s <= duration for w in windows)
        assert all(w.end_s - w.start_s <= 30 for w in windows)
        for left, right in zip(windows, windows[1:]):
            assert right.start_s == left.start_s + 15
            assert right.start_s <= left.end_s
            assert right.end_s > left.end_s


@pytest.mark.parametrize("duration", [0, -1, math.inf, math.nan, True, "60", None, 21601])
def test_invalid_durations(duration):
    with pytest.raises(ValueError):
        fixed_windows(duration)
