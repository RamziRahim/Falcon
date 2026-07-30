"""
===============================================================================
Falcon AI Swing Trading Platform — Unified Consolidation-Quality Feature Vector
===============================================================================
Script      : consolidation_features.py
Package     : Technical Analysis

Phase 4.1/4.2 of docs/FALCON_V2_REDESIGN.md section 5: a continuous
feature vector computed for ANY consolidation, not gated behind one of
the 5 named detectors having fired. Run #1's own finding (tight triangles
beat deep cups) is evidence that the CONTINUOUS properties of a
consolidation predict outcomes better than which named silhouette it
matches -- these features are the "demote binary flags to labels,
promote continuous structure" redesign, not a sixth detector.

-------------------------------------------------------------------------
Base/prior-trend boundary: pivot-based, not a fixed calendar window
-------------------------------------------------------------------------
flat_base_detector.py defines its base as a fixed trailing window
(MIN_DURATION_DAYS=25). That's the right choice for a detector matching
one specific silhouette, but wrong here: this module needs to work for
ANY consolidation regardless of length, so the base boundary is found the
same way market_structure_engine/ascending_triangle/flat_base already
locate structure -- via macro_pivots (SwingDetector(window=5), the same
higher-timeframe pivots the rest of the pattern system uses): the base
starts at the most recent confirmed swing HIGH at or before the as-of
bar (the peak of the prior advance), and the prior advance itself runs
from the swing LOW immediately before that HIGH. Insufficient pivots
(too little history, or no confirmed HIGH-then-LOW-before-it sequence
yet) returns an explicit invalidated_reason, same convention as every
existing detector -- never a silently wrong feature vector.

-------------------------------------------------------------------------
Nine features, two functions
-------------------------------------------------------------------------
compute_consolidation_features() covers the 8 features computable from a
single stock's own OHLCV history alone (prior_trend_strength through
dist_52w_high). compute_rs_line_new_high() is kept separate -- it is the
one feature in the spec's table with a genuinely different data
dependency (the NIFTY benchmark series, not just the stock's own price
history), built and tested as Phase 4.2. Wiring both into the historical
episode log (wide-universe backfill) is explicitly Phase 4.3, not done
here -- these are built and unit-tested standalone first, per the
human's own sequencing.
===============================================================================
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from technical_analysis.pattern_system.models import SwingPoint

TWELVE_MONTH_LOOKBACK_BARS = 252  # matches config.RS_12M / dist_52w_high's own "52-week" convention
RS_LINE_RECENCY_BARS = 5  # matches config.BREAKOUT_RECENCY_K_BARS -- "before or with" the breakout


def _find_base_boundaries(macro_pivots: list[SwingPoint], as_of_index: int) -> tuple[SwingPoint, SwingPoint] | None:
    """(swing_low, swing_high) marking [prior-advance start, base start] --
    the most recent confirmed swing HIGH at or before as_of_index, and the
    swing LOW immediately preceding it. None if that sequence doesn't
    exist yet (too little history, or no HIGH confirmed yet)."""
    relevant = [p for p in macro_pivots if p.index <= as_of_index]
    highs = [p for p in relevant if p.type == "HIGH"]
    if not highs:
        return None

    swing_high = highs[-1]
    lows_before = [p for p in relevant if p.type == "LOW" and p.index < swing_high.index]
    if not lows_before:
        return None

    return lows_before[-1], swing_high


def compute_prior_trend_strength(swing_low: SwingPoint, swing_high: SwingPoint) -> dict:
    """% gain and slope (average % gain per bar) of the advance preceding
    the base -- the "prior_trend_strength" row of the spec's table,
    returned as two flat keys rather than a nested value since this feeds
    a regression's flat input vector downstream (Phase 4.3+), not a
    display label."""
    bars = swing_high.index - swing_low.index
    if bars <= 0 or swing_low.price <= 0:
        return {"prior_trend_pct_gain": None, "prior_trend_slope": None, "prior_trend_bars": bars}

    pct_gain = (swing_high.price - swing_low.price) / swing_low.price * 100
    slope = pct_gain / bars

    return {
        "prior_trend_pct_gain": round(pct_gain, 2),
        "prior_trend_slope": round(slope, 4),
        "prior_trend_bars": bars,
    }


def compute_base_depth_pct(base_window: pd.DataFrame) -> float | None:
    """Max drawdown within the base -- (base_high - base_low) / base_high,
    same formula flat_base_detector.py already uses for its own depth
    check, applied here to a pivot-derived (not fixed-length) base
    window. Shallower (lower value) is better, per run #1's own finding."""
    if base_window.empty:
        return None
    base_high = base_window["High"].max()
    base_low = base_window["Low"].min()
    if pd.isna(base_high) or base_high <= 0:
        return None
    return round((base_high - base_low) / base_high * 100, 2)


def compute_base_length_bars(base_window: pd.DataFrame) -> int:
    return len(base_window)


def compute_contraction_slope(base_window: pd.DataFrame) -> float | None:
    """Linear-regression slope of ATR_14/Close (normalized -- raw ATR_14
    scales with the stock's own price level, which has nothing to do with
    genuine contraction quality and would make the slope incomparable
    across tickers) across the base's own bars. Negative = contracting
    (the VCP essence, made continuous instead of a four-wave count);
    positive = expanding. None if ATR_14 isn't available or the base is
    too short to fit a line through (need >= 3 points)."""
    if "ATR_14" not in base_window.columns or len(base_window) < 3:
        return None

    normalized_atr = (base_window["ATR_14"] / base_window["Close"]).dropna()
    if len(normalized_atr) < 3:
        return None

    x = np.arange(len(normalized_atr))
    slope, _ = np.polyfit(x, normalized_atr.to_numpy(), 1)
    return round(float(slope), 6)


def compute_volume_dryup_ratio(base_window: pd.DataFrame, pre_base_window: pd.DataFrame) -> dict:
    """Two sub-metrics under the spec's one "volume_dryup_ratio" row:
    base-average volume vs. pre-base-average volume (lower = more
    dry-up, i.e. contraction -- mirrors vcp_detector.py's own VDU check,
    generalized to any base length), and down-day vs. up-day average
    volume WITHIN the base (lower = more bullish, O'Neil's "accumulation"
    read: heavier volume on advances than declines)."""
    base_avg_volume = base_window["Volume"].mean() if not base_window.empty else None
    pre_base_avg_volume = pre_base_window["Volume"].mean() if not pre_base_window.empty else None

    dryup_ratio = None
    if base_avg_volume is not None and pre_base_avg_volume and pre_base_avg_volume > 0:
        dryup_ratio = round(base_avg_volume / pre_base_avg_volume, 3)

    down_days = base_window[base_window["Close"] < base_window["Open"]]
    up_days = base_window[base_window["Close"] >= base_window["Open"]]
    down_avg = down_days["Volume"].mean() if not down_days.empty else None
    up_avg = up_days["Volume"].mean() if not up_days.empty else None

    down_up_ratio = None
    if down_avg is not None and up_avg and up_avg > 0:
        down_up_ratio = round(down_avg / up_avg, 3)

    return {"volume_dryup_ratio": dryup_ratio, "volume_down_up_ratio": down_up_ratio}


def compute_pivot_proximity(base_window: pd.DataFrame, current_close: float) -> float | None:
    """Distance of the current close to the base's own resistance/pivot
    (the base's own max High) -- 0 means sitting right at the pivot,
    positive means still below it (has to travel that % to break out),
    negative means already through it."""
    if base_window.empty:
        return None
    pivot = base_window["High"].max()
    if pd.isna(pivot) or pivot <= 0:
        return None
    return round((pivot - current_close) / pivot * 100, 2)


def compute_breakout_volume_ratio(df_as_of: pd.DataFrame) -> float | None:
    """Latest bar's volume vs. its own trailing 20-day average -- mirrors
    scoring/relative_volume.py's Rel_Vol (the spec's own "extends the
    existing Rel_Vol input" framing), computed independently here so this
    module doesn't require Rel_Vol to already be assembled onto a
    candidate dict; same Volume_SMA_20-if-present-else-rolling-mean
    fallback vcp_detector.py already uses."""
    if len(df_as_of) < 2:
        return None

    latest_volume = df_as_of["Volume"].iloc[-1]
    baseline = (
        df_as_of["Volume_SMA_20"].iloc[-1] if "Volume_SMA_20" in df_as_of.columns
        else df_as_of["Volume"].iloc[:-1].tail(20).mean()
    )
    if pd.isna(baseline) or baseline <= 0:
        return None

    return round(latest_volume / baseline, 3)


def compute_dist_52w_high(df_as_of: pd.DataFrame, lookback_bars: int = TWELVE_MONTH_LOOKBACK_BARS) -> float | None:
    """Proximity to the 52-week high -- leaders break out near highs, not
    off a deep base (O'Neil). 0 means sitting at the 52-week high itself;
    positive means still below it."""
    if df_as_of.empty:
        return None
    window = df_as_of.tail(lookback_bars)
    high_52w = window["High"].max()
    current_close = df_as_of["Close"].iloc[-1]
    if pd.isna(high_52w) or high_52w <= 0:
        return None
    return round((high_52w - current_close) / high_52w * 100, 2)


def compute_consolidation_features(df: pd.DataFrame, macro_pivots: list[SwingPoint]) -> dict:
    """Assembles the 8 own-history features (everything in the spec's
    table except rs_line_new_high, see module docstring for why that one
    is kept separate) as of the LAST row of `df`. `df` should already be
    truncated to the as-of date by the caller -- this reads only the
    last row and whatever's behind it, never ahead.

    Returns a dict with "valid": False and every feature None (plus an
    "invalidated_reason") when no base can be located yet -- same
    fail-explicit convention every existing detector already follows,
    never a silently wrong feature vector.
    """
    ordered = df.sort_values("Date").reset_index(drop=True)
    as_of_index = len(ordered) - 1

    boundaries = _find_base_boundaries(macro_pivots, as_of_index)
    if boundaries is None:
        return {
            "valid": False, "invalidated_reason": "INSUFFICIENT_PIVOTS",
            "prior_trend_pct_gain": None, "prior_trend_slope": None, "prior_trend_bars": None,
            "base_depth_pct": None, "base_length_bars": None, "contraction_slope": None,
            "volume_dryup_ratio": None, "volume_down_up_ratio": None,
            "pivot_proximity": None, "breakout_volume_ratio": None, "dist_52w_high": None,
        }

    swing_low, swing_high = boundaries
    base_window = ordered.iloc[swing_high.index: as_of_index + 1]
    pre_base_start = max(0, swing_high.index - len(base_window))
    pre_base_window = ordered.iloc[pre_base_start: swing_high.index]

    prior_trend = compute_prior_trend_strength(swing_low, swing_high)
    volume_dryup = compute_volume_dryup_ratio(base_window, pre_base_window)
    current_close = ordered["Close"].iloc[-1]

    return {
        "valid": True,
        "invalidated_reason": None,
        **prior_trend,
        "base_depth_pct": compute_base_depth_pct(base_window),
        "base_length_bars": compute_base_length_bars(base_window),
        "contraction_slope": compute_contraction_slope(base_window),
        **volume_dryup,
        "pivot_proximity": compute_pivot_proximity(base_window, current_close),
        "breakout_volume_ratio": compute_breakout_volume_ratio(ordered),
        "dist_52w_high": compute_dist_52w_high(ordered),
    }


def compute_rs_line_new_high(
    stock_df: pd.DataFrame,
    benchmark_df: pd.DataFrame,
    lookback_bars: int = TWELVE_MONTH_LOOKBACK_BARS,
    recency_bars: int = RS_LINE_RECENCY_BARS,
) -> dict:
    """Phase 4.2. RS line = stock Close / benchmark Close, recomputed
    daily. "New high" (the classic O'Neil leading-strength signal --
    outperforming the index on a relative basis at a fresh extreme, not
    just that price itself is at a high) means: the RS line's own max
    over the last `recency_bars` days (the breakout day and the few days
    just before it -- `recency_bars` defaults to
    config.BREAKOUT_RECENCY_K_BARS, the same "before or with" window this
    codebase already uses for breakout recency) equals its max over the
    full trailing `lookback_bars` (~52 weeks, matching dist_52w_high's own
    convention) -- i.e. the all-time (over that lookback) high actually
    fell within the recent window, not further back.

    Both frames must have a "Date" column to align on -- an inner merge,
    so only dates present in both series are compared (a benchmark
    holiday gap silently drops that day rather than misaligning the two
    series by position).
    """
    stock = stock_df.sort_values("Date").reset_index(drop=True)
    bench = benchmark_df.sort_values("Date").reset_index(drop=True)

    merged = pd.merge(
        stock[["Date", "Close"]], bench[["Date", "Close"]],
        on="Date", suffixes=("_stock", "_bench"),
    )
    if merged.empty:
        return {"rs_line_new_high": None, "rs_line_value": None}

    merged = merged[merged["Close_bench"] > 0]
    if merged.empty:
        return {"rs_line_new_high": None, "rs_line_value": None}

    merged["rs_line"] = merged["Close_stock"] / merged["Close_bench"]

    trailing = merged["rs_line"].tail(lookback_bars)
    recent = merged["rs_line"].tail(recency_bars)
    if trailing.empty or recent.empty:
        return {"rs_line_new_high": None, "rs_line_value": None}

    is_new_high = bool(recent.max() >= trailing.max())

    return {"rs_line_new_high": is_new_high, "rs_line_value": round(merged["rs_line"].iloc[-1], 6)}
