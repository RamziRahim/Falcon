"""
Falcon — Phase 4.3: Backfill v2 Consolidation Features onto Run #3's Episode Log
Run from project root: python tests/backfill_v2_features.py

For every episode in run #3's historical episode log
(data/backtest_results_run3_wide_universe.csv -> episode_builder.build_episodes()),
computes technical_analysis/consolidation_features.py's full feature
vector (4.1's 8 own-history features + 4.2's rs_line_new_high) AS OF the
episode's own entry date (episode_start_date), using history truncated
to that date -- same point-in-time discipline as
backtesting/replay_engine.py's own docstring: no code path here may read
any row dated after the episode's own entry.

Both invalidated_reason fields (the pivot-boundary one from
compute_consolidation_features(), and dist_52w_high's own renamed one)
plus RS-line's own invalidated_reason are carried through to the output
CSV verbatim -- 4.4's calibration step needs to know which rows have
degraded/missing features so it can exclude or flag them, not silently
treat a None as a zero.
"""
import sys
sys.path.insert(0, ".")

import glob
import os
import time

import pandas as pd

from scoring.benchmark import get_benchmark_history
from technical_analysis.consolidation_features import compute_consolidation_features, compute_rs_line_new_high
from technical_analysis.pattern_system.swing_detector import SwingDetector
from backtesting.episode_builder import build_episodes

RUN3_PATH = "data/backtest_results_run3_wide_universe.csv"
OUTPUT_PATH = "data/run3_episodes_with_v2_features.csv"
CHECKPOINT_EVERY = 500

macro_swing_detector = SwingDetector(window=5)


def _load_universe() -> dict[str, pd.DataFrame]:
    universe = {}
    for path in sorted(glob.glob("data/technical/*.parquet")):
        ticker = os.path.basename(path).replace(".parquet", "")
        df = pd.read_parquet(path)
        df["Date"] = pd.to_datetime(df["Date"])
        if df["Date"].dt.tz is not None:
            df["Date"] = df["Date"].dt.tz_localize(None)
        df = df.sort_values("Date").reset_index(drop=True)
        universe[ticker] = df
    return universe


def _features_for_episode(ticker: str, entry_date: pd.Timestamp, universe: dict, benchmark: pd.DataFrame) -> dict:
    history = universe.get(ticker)
    if history is None:
        return {
            "consolidation_valid": False, "consolidation_invalidated_reason": "TICKER_NOT_IN_UNIVERSE",
            "prior_trend_pct_gain": None, "prior_trend_slope": None, "prior_trend_bars": None,
            "base_depth_pct": None, "base_length_bars": None, "contraction_slope": None,
            "volume_dryup_ratio": None, "volume_down_up_ratio": None,
            "pivot_proximity": None, "breakout_volume_ratio": None,
            "dist_52w_high": None, "dist_52w_high_invalidated_reason": None,
            "rs_line_new_high": None, "rs_line_invalidated_reason": "TICKER_NOT_IN_UNIVERSE", "rs_line_value": None,
            "ticker_earliest_cached_date": None, "ticker_history_days_at_entry": None,
        }

    truncated = history[history["Date"] <= entry_date].reset_index(drop=True)
    truncated_bench = benchmark[benchmark["Date"] <= entry_date].reset_index(drop=True)

    macro_pivots = macro_swing_detector.detect_swings(truncated) if len(truncated) >= 10 else []
    consolidation = compute_consolidation_features(truncated, macro_pivots)
    rs_line = compute_rs_line_new_high(truncated, truncated_bench)

    return {
        "consolidation_valid": consolidation["valid"],
        "consolidation_invalidated_reason": consolidation["invalidated_reason"],
        "prior_trend_pct_gain": consolidation["prior_trend_pct_gain"],
        "prior_trend_slope": consolidation["prior_trend_slope"],
        "prior_trend_bars": consolidation["prior_trend_bars"],
        "base_depth_pct": consolidation["base_depth_pct"],
        "base_length_bars": consolidation["base_length_bars"],
        "contraction_slope": consolidation["contraction_slope"],
        "volume_dryup_ratio": consolidation["volume_dryup_ratio"],
        "volume_down_up_ratio": consolidation["volume_down_up_ratio"],
        "pivot_proximity": consolidation["pivot_proximity"],
        "breakout_volume_ratio": consolidation["breakout_volume_ratio"],
        "dist_52w_high": consolidation["dist_52w_high"],
        "dist_52w_high_invalidated_reason": consolidation["dist_52w_high_invalidated_reason"],
        "rs_line_new_high": rs_line["rs_line_new_high"],
        "rs_line_invalidated_reason": rs_line["invalidated_reason"],
        "rs_line_value": rs_line["rs_line_value"],
        "ticker_earliest_cached_date": history["Date"].iloc[0].date() if not history.empty else None,
        "ticker_history_days_at_entry": len(truncated),
    }


def main():
    trades = pd.read_csv(RUN3_PATH, low_memory=False)
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    episodes = build_episodes(trades)
    episodes["episode_start_date"] = pd.to_datetime(episodes["episode_start_date"])
    print(f"Episodes (full historical log, all categories): {len(episodes)}")

    universe = _load_universe()
    print(f"Universe loaded: {len(universe)} tickers")

    benchmark = get_benchmark_history()
    benchmark["Date"] = pd.to_datetime(
        benchmark["Date"] if "Date" in benchmark.columns else benchmark.index
    ).dt.tz_localize(None)

    # Built in the SAME row order episodes.itertuples() iterates -- concat
    # by position below relies on this, not a join key, since a
    # (ticker, episode_start_date) pair is not guaranteed unique across
    # category_changes-absorbed episodes the way a real primary key would be.
    feature_rows = []
    t0 = time.time()
    for n, row in enumerate(episodes.itertuples(), start=1):
        feature_rows.append(_features_for_episode(row.ticker, row.episode_start_date, universe, benchmark))

        if n % CHECKPOINT_EVERY == 0 or n == len(episodes):
            elapsed = time.time() - t0
            rate = n / elapsed
            remaining = (len(episodes) - n) / rate if rate > 0 else 0
            print(f"  [{n}/{len(episodes)}] -- {elapsed/60:.1f} min elapsed, ~{remaining/60:.1f} min remaining")

    result = pd.concat(
        [episodes.reset_index(drop=True), pd.DataFrame(feature_rows)], axis=1,
    )

    result.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved -> {OUTPUT_PATH} ({len(result)} rows)")


if __name__ == "__main__":
    main()
