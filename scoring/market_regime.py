"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : market_regime.py
Package     : Scoring

Purpose
-------
Market-regime awareness: India VIX level/bucket (A1) and O'Neil-style
distribution-day counting on the benchmark index (A2). Cheap, standalone
data -- not wired into any decision logic yet (deferred to the Tier 1/2
decision layer).

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
