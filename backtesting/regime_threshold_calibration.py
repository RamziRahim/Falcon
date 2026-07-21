"""
===============================================================================
Falcon AI Swing Trading Platform — Market Regime Threshold Calibration
===============================================================================
Script      : regime_threshold_calibration.py
Package     : Backtesting

Cheap, standalone diagnostic (same spirit as run_full_pipeline.py and
data_source_comparison.py, not a production module) -- tests whether
leadership_decision_engine.get_market_regime_verdict()'s VIX (<15/15-20/>20)
and distribution-day (>=6) cutoffs, borrowed from general US-market
practice, actually separate good and bad forward conditions for NIFTY
specifically. Deliberately does NOT re-run the 3-hour full replay: this
only needs benchmark_history + vix_history, both already cheap to fetch
(no pattern detection, no per-ticker replay).

-------------------------------------------------------------------------
Confirmed live, not guessed
-------------------------------------------------------------------------
scoring.market_regime.get_vix_history() returns columns Date/VIX_Level/
VIX_Regime (its own clean contract, not nselib's raw CLOSE_INDEX_VAL) --
this module reads VIX_Level, not the raw nselib column name the original
sketch assumed.

scoring.benchmark.get_benchmark_history()'s Date column is tz-aware
(Asia/Kolkata, confirmed earlier in data_source_comparison.py); vix_history's
Date is tz-naive. Same normalization needed before merging on Date, or the
merge silently produces zero matches instead of an error.

A single get_vix_history() call comfortably covers a 9+ year range in
~9 seconds (2364 rows fetched live) -- no chunking needed.
===============================================================================
"""
from __future__ import annotations

import pandas as pd

from scoring.market_regime import DISTRIBUTION_DAY_DECLINE_THRESHOLD

FORWARD_DAYS_DEFAULT = 20


def _normalize_dates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    return df


def analyze_vix_vs_forward_returns(
    benchmark_history: pd.DataFrame, vix_history: pd.DataFrame, forward_days: int = FORWARD_DAYS_DEFAULT
) -> pd.DataFrame:
    """
    For every trading day in the window, that day's VIX level vs NIFTY's
    actual forward return over the next `forward_days` sessions. Bucketed
    by VIX decile (not the current fixed <15/15-20/>20 cutoffs) -- directly
    answers "does higher VIX actually precede worse NIFTY returns in this
    data," rather than assuming borrowed thresholds are correct.
    """
    bench = _normalize_dates(benchmark_history)
    vix = _normalize_dates(vix_history)

    merged = bench.merge(vix, on="Date", how="inner").sort_values("Date").reset_index(drop=True)

    merged["forward_return_pct"] = (
        merged["Close"].shift(-forward_days) / merged["Close"] - 1
    ) * 100
    merged = merged.dropna(subset=["forward_return_pct"])

    merged["vix_decile"] = pd.qcut(merged["VIX_Level"], 10, labels=False, duplicates="drop")

    return merged.groupby("vix_decile").agg(
        vix_range=("VIX_Level", lambda x: f"{x.min():.1f}-{x.max():.1f}"),
        avg_forward_return=("forward_return_pct", "mean"),
        n_days=("forward_return_pct", "count"),
    )


def _rolling_distribution_day_count(benchmark_history: pd.DataFrame, lookback_window: int) -> pd.Series:
    """Same distribution-day definition as scoring.market_regime.count_distribution_days()
    (down >0.2% on higher volume than the prior day), applied as a rolling
    count across the whole series rather than a single point-in-time
    snapshot of just the tail."""
    df = benchmark_history.sort_values("Date").reset_index(drop=True)
    pct_change = df["Close"].pct_change()
    vol_higher = df["Volume"] > df["Volume"].shift(1)
    is_distribution_day = (pct_change < DISTRIBUTION_DAY_DECLINE_THRESHOLD) & vol_higher
    return is_distribution_day.rolling(window=lookback_window).sum()


def analyze_distribution_days_vs_forward_returns(
    benchmark_history: pd.DataFrame, forward_days: int = FORWARD_DAYS_DEFAULT, lookback_window: int = 25
) -> pd.DataFrame:
    """
    For every day, the rolling distribution-day count over the prior
    `lookback_window` days vs NIFTY's forward return from that day.
    Bucketed 0-2/3-5/6-8/9+ -- does the current ">=6 = UNFAVORABLE" cutoff
    actually align with where forward returns get worse in this data?
    """
    df = _normalize_dates(benchmark_history).sort_values("Date").reset_index(drop=True)

    df["distribution_day_count"] = _rolling_distribution_day_count(df, lookback_window)
    df["forward_return_pct"] = (df["Close"].shift(-forward_days) / df["Close"] - 1) * 100

    df = df.dropna(subset=["distribution_day_count", "forward_return_pct"])

    bins = [-1, 2, 5, 8, float("inf")]
    labels = ["0-2", "3-5", "6-8", "9+"]
    df["distribution_day_bucket"] = pd.cut(df["distribution_day_count"], bins=bins, labels=labels)

    return df.groupby("distribution_day_bucket", observed=True).agg(
        avg_forward_return=("forward_return_pct", "mean"),
        n_days=("forward_return_pct", "count"),
    )


if __name__ == "__main__":
    from scoring.benchmark import get_benchmark_history
    from scoring.market_regime import get_vix_history

    benchmark_history = get_benchmark_history()
    vix_history = get_vix_history(from_date="01-01-2017", to_date=pd.Timestamp.today().strftime("%d-%m-%Y"))

    print("=== VIX decile vs 20-day forward NIFTY return ===")
    print(analyze_vix_vs_forward_returns(benchmark_history, vix_history).to_string())

    print("\n=== Distribution-day bucket vs 20-day forward NIFTY return ===")
    print(analyze_distribution_days_vs_forward_returns(benchmark_history).to_string())
