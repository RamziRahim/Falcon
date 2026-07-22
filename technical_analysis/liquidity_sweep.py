"""
===============================================================================
Falcon AI Swing Trading Platform — Liquidity Sweep Detection
===============================================================================
Script      : liquidity_sweep.py
Package     : Technical Analysis

Mechanically-definable ICT/SMC-style liquidity sweep: does the most recent
bar wick through a prior swing low/high and close back inside the prior
range (a "sweep-and-reject"), as opposed to genuinely breaking out through
it. No inference about other traders' intent -- purely a price-action
check on Low/High/Close against a trailing window.

Distinct from technical_analysis.pattern_system.market_structure's own
is_liquidity_sweep (volume-filtered, anchored to macro swing PIVOTS, BOS-
aware) -- that's a different, already-shipped mechanism serving a
different purpose (market structure classification). This module is a
simpler, standalone check: min/max Low/High over a trailing window, no
volume filter, no pivot detection. The two coexist; neither replaces the
other.
===============================================================================
"""
from __future__ import annotations

import pandas as pd

NO_SWEEP_RESULT = {
    "swept": False,
    "direction": None,
    "swing_level": None,
    "sweep_bar_low": None,
    "sweep_bar_high": None,
}


def detect_liquidity_sweep(history: pd.DataFrame, lookback: int = 20) -> dict:
    """
    Detects whether the most recent bar (history's last row) swept a
    prior swing low (SSL) or swing high (BSL) and closed back inside the
    prior range.

    Definition
    ----------
    Prior swing low/high = min(Low) / max(High) over the `lookback` bars
    immediately preceding the current bar (current bar itself excluded --
    the same self-reference discipline used throughout this project's
    other pattern detectors: including today's own bar in the window it's
    being compared against would make a genuine sweep nearly impossible
    to satisfy).

    SSL sweep: current Low < prior swing low, AND current Close > prior
    swing low (wicked through, closed back inside).
    BSL sweep: current High > prior swing high, AND current Close < prior
    swing high.

    A genuine breakout (current bar closes BEYOND the level, not back
    inside it) does not need a separate exclusion check: it already fails
    the Close condition above by construction -- e.g. an SSL candidate
    that closes below the swept low fails "Close > prior swing low" and
    falls through to no-sweep, exactly as it should.

    Returns
    -------
    dict : swept (bool), direction ("SSL"/"BSL"/None), swing_level
    (float | None, the level that was swept), sweep_bar_low,
    sweep_bar_high (float | None, the current bar's own Low/High).
    swept=False (not a crash) when history has fewer than lookback+1 rows.
    """
    if history is None or len(history) < lookback + 1:
        return dict(NO_SWEEP_RESULT)

    ordered = history.sort_values("Date").reset_index(drop=True)

    prior_window = ordered.iloc[-(lookback + 1):-1]
    current_bar = ordered.iloc[-1]

    prior_swing_low = prior_window["Low"].min()
    prior_swing_high = prior_window["High"].max()

    current_low = current_bar["Low"]
    current_high = current_bar["High"]
    current_close = current_bar["Close"]

    if current_low < prior_swing_low and current_close > prior_swing_low:
        return {
            "swept": True,
            "direction": "SSL",
            "swing_level": prior_swing_low,
            "sweep_bar_low": current_low,
            "sweep_bar_high": current_high,
        }

    if current_high > prior_swing_high and current_close < prior_swing_high:
        return {
            "swept": True,
            "direction": "BSL",
            "swing_level": prior_swing_high,
            "sweep_bar_low": current_low,
            "sweep_bar_high": current_high,
        }

    return dict(NO_SWEEP_RESULT)
