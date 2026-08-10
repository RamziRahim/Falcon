"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : market_regime.py
Package     : Scoring

Purpose
-------
Market-regime awareness: NIFTY 50's own trend state (get_market_trend_state,
the primary regime signal as of the trend-based redesign -- see its own
docstring for why this replaced VIX), O'Neil-style distribution-day
counting on the benchmark index, and India VIX level/bucket (kept for
other future uses, e.g. stop-loss width -- no longer the regime signal
itself).

India VIX columns confirmed via a live call to nselib's
capital_market.india_vix_data() and against nselib/constants.py's
india_vix_data_column: TIMESTAMP ("17-JUL-2026" style), CLOSE_INDEX_VAL,
VIX_PERC_CHG (both plain floats, no comma-formatting to clean).

Distribution days reuse scoring/benchmark.py's already-cached NIFTY 50
history -- no new fetch, no new caching layer.
===============================================================================
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from nselib import capital_market

from config import DATA_FOLDER

from common.logger import get_logger

logger = get_logger(__name__)

VIX_CACHE_PATH = Path(DATA_FOLDER) / "vix_cache.json"

# VIX is daily data -- refresh once a day, not on every call.
REFRESH_INTERVAL_HOURS = 24

# Starting thresholds, not backtested yet -- revisit once #16 (backtesting)
# has real data on what VIX level actually correlates with worse breakout
# follow-through in this dataset.
VIX_LOW_THRESHOLD = 15.0
VIX_ELEVATED_THRESHOLD = 20.0

DISTRIBUTION_DAY_DECLINE_THRESHOLD = -0.002  # O'Neil: down >0.2%


def _classify_vix_regime(level: float) -> str:
    """LOW (<15), NORMAL (15-20 inclusive), ELEVATED (>20)."""

    if level < VIX_LOW_THRESHOLD:
        return "LOW"

    if level <= VIX_ELEVATED_THRESHOLD:
        return "NORMAL"

    return "ELEVATED"


def _load_vix_cache_if_fresh() -> dict | None:

    if not VIX_CACHE_PATH.exists():
        return None

    try:

        with open(VIX_CACHE_PATH, "r", encoding="utf-8") as fh:
            cached = json.load(fh)

        fetched_at = datetime.fromisoformat(cached["fetched_at"])

        if datetime.now() - fetched_at > timedelta(hours=REFRESH_INTERVAL_HOURS):
            return None

        return cached["result"]

    except Exception as ex:

        logger.warning("Failed to load VIX cache: %s", ex)
        return None


def _save_vix_cache(result: dict) -> None:

    try:

        VIX_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

        with open(VIX_CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump({"fetched_at": datetime.now().isoformat(), "result": result}, fh, indent=2)

    except Exception as ex:

        logger.warning("Failed to save VIX cache: %s", ex)


def get_current_vix() -> dict | None:
    """
    Returns {'level': float, 'change_pct': float, 'regime': str} for the
    most recent India VIX close, or None if the fetch fails -- callers
    should treat None as "regime unknown", not crash.
    """

    cached = _load_vix_cache_if_fresh()

    if cached is not None:
        return cached

    try:

        raw = capital_market.india_vix_data(period="1M")

        if raw is None or raw.empty:
            raise ValueError("india_vix_data() returned no rows")

        latest = raw.iloc[-1]

        result = {
            "level": float(latest["CLOSE_INDEX_VAL"]),
            "change_pct": float(latest["VIX_PERC_CHG"]),
            "regime": _classify_vix_regime(float(latest["CLOSE_INDEX_VAL"])),
        }

        _save_vix_cache(result)
        return result

    except Exception as ex:

        logger.warning("India VIX fetch failed, regime unknown: %s", ex)
        return None


def get_vix_history(from_date: str, to_date: str) -> pd.DataFrame | None:
    """
    Fetches India VIX daily closes over an explicit historical range --
    unlike get_current_vix() (always the latest value, 24h-cached), this
    is for backtesting/replay_engine.py's point-in-time replay, which
    needs the VIX regime as of an arbitrary past date, not just today's.
    Confirmed live that nselib's india_vix_data() accepts a real
    from_date/to_date range (not just the 'period' shorthand).

    Parameters
    ----------
    from_date, to_date : str
        'dd-mm-YYYY', nselib's own date format.

    Returns
    -------
    pd.DataFrame | None
        Sorted ascending by Date, columns Date/VIX_Level/VIX_Regime (the
        same LOW/NORMAL/ELEVATED buckets as get_current_vix(), via
        _classify_vix_regime). None if the fetch fails -- callers should
        treat that as "regime unknown for this range," not crash, same
        convention as get_current_vix().

    Deliberately not cached to a file: get_current_vix() caches because
    it's called repeatedly during live scans. This is meant to be called
    once per backtest run for the whole replay period and then truncated
    locally per replay date -- a persistent cache would be unnecessary
    complexity for a single-fetch-per-run access pattern.
    """

    try:

        raw = capital_market.india_vix_data(from_date=from_date, to_date=to_date)

        if raw is None or raw.empty:
            return None

        result = pd.DataFrame({
            "Date": pd.to_datetime(raw["TIMESTAMP"], format="%d-%b-%Y"),
            "VIX_Level": raw["CLOSE_INDEX_VAL"].astype(float),
        }).sort_values("Date").reset_index(drop=True)

        result["VIX_Regime"] = result["VIX_Level"].apply(_classify_vix_regime)

        return result

    except Exception as ex:

        logger.warning("India VIX history fetch failed for %s to %s: %s", from_date, to_date, ex)
        return None


MIN_TREND_STATE_ROWS = 20  # same floor pattern_engine.py/backtesting use -- a
                           # shorter view can't support real fractal detection


def get_market_trend_state(benchmark_history: pd.DataFrame) -> str:
    """
    Runs the existing market_structure_engine against NIFTY 50's own price
    history -- the same code already computing Trend_State for every
    individual stock, just applied to the benchmark instead. Returns
    UPTREND / DOWNTREND / CHOPPY, the same three values already used
    everywhere else, no new vocabulary.

    Replaces India VIX as the market-regime signal: confirmed via
    backtesting/regime_threshold_calibration.py (9.5 years, COVID-excluded)
    that high VIX does NOT precede worse NIFTY forward returns at a
    20-day horizon in this data -- if anything, mildly the opposite. VIX
    measures fear/volatility, a related but different concept from what
    O'Neil/Minervini "market health" actually means: trend direction.
    Conflating the two was the likely root cause, not a threshold
    calibration error. VIX itself isn't discarded -- flagged as a
    candidate input elsewhere (e.g. stop-loss width) in a future task,
    not part of this one.

    Local imports (not module-level) deliberately: this module stays
    lightweight for callers that only need VIX/distribution-day data,
    without pulling in pattern_engine.py's full detector-import chain.
    """
    from technical_analysis.pattern_engine import macro_swing_detector
    from technical_analysis.pattern_system.market_structure import market_structure_engine

    if benchmark_history is None or len(benchmark_history) < MIN_TREND_STATE_ROWS:
        return "CHOPPY"  # honestly-unknown default -- same as market_structure_engine's
                          # own fallback when it can't determine a real trend

    macro_pivots = macro_swing_detector.detect_swings(benchmark_history)
    structure = market_structure_engine.analyze_structure(benchmark_history, macro_pivots)
    return structure["trend_state"]


def get_recalibrated_market_trend_state(df: pd.DataFrame, vote_window: int = 3) -> str:
    """
    B-7: recalibrated market-level trend classification -- used for the
    regime signal (get_market_regime_verdict()'s nifty_trend_state input)
    specifically, NOT for per-stock pattern-detection gating or
    sector-breadth Pct_Uptrend (both still use get_market_trend_state()'s
    original rule; see that function's own docstring for why this is
    deliberately scoped narrowly).

    Moved here from backtesting/replay_engine.py (originally
    _regime_trend_state_of_truncated) so the live scan path
    (decision_engine/live_scorer.py's _compute_live_market_verdict()) and
    the backtest/replay path share the exact same regime logic the v2
    consolidation-quality model was trained on -- market_regime_verdict is
    one of that model's own fitted categorical features (docs/
    FALCON_V2_REDESIGN.md section 5), so a live path computing regime
    differently from the training data would silently feed the model an
    input it was never calibrated against. replay_engine.py re-exports
    this under its original name for its own internal call site and for
    tests/backtesting/test_replay_engine.py's existing references --
    behavior is unchanged, only the location moved.

    market_structure_engine.analyze_structure()'s original rule requires
    the SINGLE most recently confirmed HIGH pivot AND the single most
    recently confirmed LOW pivot to BOTH be higher than their own
    predecessor to call UPTREND. A real, sustained recovery routinely
    produces one "back-and-fill" pivot pair (a higher high followed by a
    slightly lower low before continuing up) that flips this rule to
    CHOPPY even though the broader structure is still trending -- verified
    directly against run #1's tuning split (2024-07-22 -> 2025-09-21):
    NIFTY's real 2025-03-04 trough-to-recovery leg read CHOPPY on 99 of
    136 days (72.8%) under the original rule.

    Recalibrated (tuning split only): DOWNTREND keeps the ORIGINAL strict
    single-most-recent-pivot-pair rule -- a false negative on a real
    downtrend is costlier than one on an uptrend, so this side is
    deliberately not loosened. UPTREND uses a majority vote over the last
    `vote_window` confirmed HIGH pivots and the last `vote_window`
    confirmed LOW pivots independently (a strict majority of each must be
    "higher" than their own predecessor), tolerating one back-and-fill
    pivot without flipping the whole classification to CHOPPY. Anything
    that clears neither test (including too few confirmed pivots to vote)
    is CHOPPY, same fallback as before.

    Verified on the tuning split: this asymmetric design took FAVORABLE
    from 6 to 9 days (of 292) while leaving UNFAVORABLE UNCHANGED at 75 --
    a symmetric majority-vote-on-both-sides variant also tried during
    calibration raised FAVORABLE to 9 but ALSO raised UNFAVORABLE to 86
    (worse), which is why DOWNTREND was deliberately left on the original
    strict rule instead of also being loosened.

    Local import (not module-level), same reasoning as
    get_market_trend_state()'s own: this module stays lightweight for
    callers that only need VIX/distribution-day data, without pulling in
    pattern_engine.py's full detector-import chain.
    """
    from technical_analysis.pattern_engine import macro_swing_detector

    if len(df) < MIN_TREND_STATE_ROWS:
        return "UNKNOWN"

    macro_pivots = macro_swing_detector.detect_swings(df)
    highs = [p for p in macro_pivots if p.type == "HIGH"]
    lows = [p for p in macro_pivots if p.type == "LOW"]

    if not highs or not lows:
        return "CHOPPY"

    if not highs[-1].is_higher and not lows[-1].is_higher:
        return "DOWNTREND"

    if len(highs) >= vote_window and len(lows) >= vote_window:
        recent_highs = highs[-vote_window:]
        recent_lows = lows[-vote_window:]
        highs_higher = sum(1 for p in recent_highs if p.is_higher)
        lows_higher = sum(1 for p in recent_lows if p.is_higher)
        majority = vote_window // 2 + 1

        if highs_higher >= majority and lows_higher >= majority:
            return "UPTREND"

    return "CHOPPY"


def count_distribution_days(benchmark_df: pd.DataFrame, lookback: int = 25) -> int | None:
    """
    Counts days in the last `lookback` trading days where the benchmark
    closed down >0.2% on volume higher than the prior day (O'Neil's
    standard distribution-day definition). More distribution days in a
    rolling window = more institutional selling pressure = worse regime
    for new breakout entries.

    Returns None (not a crash) if benchmark_df is missing required columns
    or has too little history.
    """

    try:

        if benchmark_df is None or benchmark_df.empty:
            return None

        if not {"Close", "Volume"}.issubset(benchmark_df.columns):
            return None

        recent = benchmark_df.tail(lookback + 1).copy()

        recent["pct_change"] = recent["Close"].pct_change()
        recent["vol_higher"] = recent["Volume"] > recent["Volume"].shift(1)

        distribution_days = recent[
            (recent["pct_change"] < DISTRIBUTION_DAY_DECLINE_THRESHOLD) & (recent["vol_higher"])
        ]

        return len(distribution_days)

    except Exception as ex:

        logger.warning("Distribution-day count failed: %s", ex)
        return None
