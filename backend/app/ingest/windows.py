"""Spec 6.1 secondary temporal index, independent of media/model runtimes."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class FixedWindow:
    start_s: float
    end_s: float
    method: str = "fixed-30s"


def fixed_windows(duration_s: float) -> tuple[FixedWindow, ...]:
    """30-second windows at 15-second stride, clipping the final window.

    Stop once a window reaches the end; do not add a redundant trailing window
    wholly contained in its predecessor. Does not decode or persist media.
    The six-hour bound follows the spec's entire-corpus duration ceiling.
    """
    if (
        isinstance(duration_s, bool)
        or not isinstance(duration_s, (int, float))
        or not math.isfinite(duration_s)
        or not 0 < duration_s <= 6 * 3600
    ):
        raise ValueError("duration_s must be finite, positive and at most six hours")
    count = max(1, math.ceil((duration_s - 30) / 15) + 1)
    return tuple(
        FixedWindow(float(i * 15), min(float(i * 15 + 30), float(duration_s))) for i in range(count)
    )
