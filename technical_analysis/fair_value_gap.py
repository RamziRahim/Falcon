"""
===============================================================================
Falcon AI Swing Trading Platform — Fair Value Gap (FVG) Detection
===============================================================================
Script      : fair_value_gap.py
Package     : Technical Analysis

Mechanically-definable ICT/SMC-style 3-candle Fair Value Gap, checked at
an arbitrary point-in-time index, both directions (bullish and bearish),
with a fill-percentage read against the most recent available price --
not just "does a gap exist," but "how much of it is still open."

Distinct from technical_analysis.pattern_system.fvg_detector's existing
FVGDetector.detect_fvgs() (bullish-only, always evaluated at the latest
row, broadcast-scan style already wired into pattern_engine.py). That
one stays as-is. This module is a standalone, bidirectional, point-in-
time check -- built for the microstructure-signal use case (checking a
specific historical gap's fill state, not just "is there one right now").
The two coexist; neither replaces the other.
===============================================================================
"""
from __future__ import annotations

import pandas as pd

NO_FVG_RESULT = {
    "has_fvg": False,
    "direction": None,
    "gap_top": None,
    "gap_bottom": None,
    "gap_filled_pct": None,
}


def detect_fvg(history: pd.DataFrame, as_of_index: int) -> dict:
    """
    Detects a 3-candle Fair Value Gap among candles A, B, C, where
    C = history's row at as_of_index and A/B are the two immediately
    preceding rows (A = as_of_index - 2, B = as_of_index - 1).

    Definition
    ----------
    Bullish FVG: A.High < C.Low (a gap between A's high and C's low; B is
    the strong displacement candle in between). gap_bottom = A.High,
    gap_top = C.Low.
    Bearish FVG: A.Low > C.High. gap_bottom = C.High, gap_top = A.Low.

    gap_filled_pct is read against the MOST RECENT row in `history`
    (history.iloc[-1], not necessarily candle C itself -- history may
    extend past as_of_index, representing price action that happened
    after the gap formed) -- 0 means untouched (price hasn't moved back
    into [gap_bottom, gap_top] at all), 100 means fully filled (price has
    traded all the way through to the opposite side), clamped to [0, 100]
    regardless of how far price has overshot beyond a full fill.

    Returns
    -------
    dict : has_fvg (bool), direction ("bullish"/"bearish"/None), gap_top,
    gap_bottom (float | None), gap_filled_pct (float | None, 0-100).
    has_fvg=False (not a crash) when as_of_index doesn't have 2 preceding
    rows, is out of bounds, or the candles don't actually form a gap
    (overlapping ranges).
    """
    if history is None or as_of_index < 2 or as_of_index >= len(history):
        return dict(NO_FVG_RESULT)

    ordered = history.sort_values("Date").reset_index(drop=True)

    candle_a = ordered.iloc[as_of_index - 2]
    candle_c = ordered.iloc[as_of_index]

    if candle_a["High"] < candle_c["Low"]:
        direction = "bullish"
        gap_bottom = candle_a["High"]
        gap_top = candle_c["Low"]
    elif candle_a["Low"] > candle_c["High"]:
        direction = "bearish"
        gap_bottom = candle_c["High"]
        gap_top = candle_a["Low"]
    else:
        return dict(NO_FVG_RESULT)

    current_close = ordered.iloc[-1]["Close"]
    gap_range = gap_top - gap_bottom

    if gap_range <= 0:
        gap_filled_pct = 0.0
    elif direction == "bullish":
        # Bullish FVG sits below the current highs -- price retracing
        # DOWN into it (toward gap_bottom) is the fill direction.
        gap_filled_pct = ((gap_top - current_close) / gap_range) * 100
    else:
        # Bearish FVG sits above the current lows -- price retracing UP
        # into it (toward gap_top) is the fill direction.
        gap_filled_pct = ((current_close - gap_bottom) / gap_range) * 100

    gap_filled_pct = max(0.0, min(100.0, gap_filled_pct))

    return {
        "has_fvg": True,
        "direction": direction,
        "gap_top": gap_top,
        "gap_bottom": gap_bottom,
        "gap_filled_pct": round(gap_filled_pct, 1),
    }
