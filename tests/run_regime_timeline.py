"""
Falcon — Regime Timeline + Attribution Runner (Phase 1.3 / A-2)
Run from project root: python tests/run_regime_timeline.py

Reconstructs the daily market_regime_verdict + cause across run #1's
window (see backtesting/regime_timeline.py for why this doesn't count as
re-running the replay engine), summarizes what fraction of the window
each cause covers, finds contiguous UNFAVORABLE/CAUTION periods, and
reports whether the ceiling-attribution "capped, UNFAVORABLE" episode
population clusters in one or two periods or spreads across many --
the specific question Gate 1 needs answered before trusting that
population's expectancy number.

Slow: daily trend/distribution-day reconstruction over the whole window
takes on the order of 15-20 minutes (each date re-runs swing detection
over the full truncated NIFTY history). Run in the background.
"""
import sys
sys.path.insert(0, ".")

import pandas as pd

from backtesting.episode_builder import build_episodes
from backtesting.regime_timeline import (
    attribute_episodes_to_periods,
    build_regime_timeline,
    find_contiguous_periods,
    summarize_regime_timeline,
)
from scoring.benchmark import get_benchmark_history

TIMELINE_CACHE_PATH = "data/regime_timeline.csv"


def main():
    trades = pd.read_csv("data/backtest_results.csv")
    episodes = build_episodes(trades)
    episodes["episode_start_date"] = pd.to_datetime(episodes["episode_start_date"])

    start = episodes["episode_start_date"].min()
    end = pd.to_datetime(trades["entry_date"]).max()
    print(f"Window: {start.date()} -> {end.date()}")

    print("Loading NIFTY benchmark history...")
    benchmark_history = get_benchmark_history()
    benchmark_history["Date"] = pd.to_datetime(
        benchmark_history["Date"] if "Date" in benchmark_history.columns else benchmark_history.index
    ).dt.tz_localize(None)

    print("Building daily regime timeline (this takes ~15-20 minutes)...")
    timeline = build_regime_timeline(benchmark_history, start, end)
    timeline.to_csv(TIMELINE_CACHE_PATH, index=False)
    print(f"Saved timeline -> {TIMELINE_CACHE_PATH} ({len(timeline)} days)")

    summary = summarize_regime_timeline(timeline)
    print("\n" + "=" * 70)
    print("  REGIME TIMELINE SUMMARY -- BY VERDICT")
    print("=" * 70)
    print(summary["by_verdict"].to_string(index=False))

    print("\n" + "=" * 70)
    print("  REGIME TIMELINE SUMMARY -- BY CAUSE")
    print("=" * 70)
    print(summary["by_cause"].to_string(index=False))

    for verdict in ("UNFAVORABLE", "CAUTION", "FAVORABLE"):
        periods = find_contiguous_periods(timeline, verdict)
        print(f"\n=== CONTIGUOUS {verdict} PERIODS: {len(periods)} ===")
        for p in periods:
            print(f"  {p['start_date'].date()} -> {p['end_date'].date()} ({p['n_days']} days)")

        if verdict == "UNFAVORABLE":
            unfavorable_periods = periods

    watchlist = episodes[episodes["category"] == "ALERT_WATCHLIST"]
    capped = watchlist[watchlist["confidence_score"] >= 65.0]
    capped_unfavorable = capped[capped["market_regime_verdict"] == "UNFAVORABLE"]

    print("\n" + "=" * 70)
    print(f"  UNFAVORABLE-CAPPED EPISODES ACROSS CONTIGUOUS PERIODS (n={len(capped_unfavorable)})")
    print("=" * 70)
    clustering = attribute_episodes_to_periods(capped_unfavorable, unfavorable_periods)
    print(clustering.to_string(index=False))
    print(f"\nDistinct periods touched: {len(clustering)} out of {len(unfavorable_periods)} total UNFAVORABLE periods")


if __name__ == "__main__":
    main()
