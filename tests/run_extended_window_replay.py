"""
Falcon — Gate 3 Second Window: Independent Replay, 2023-12-11 -> 2024-06-11
Run from project root: python tests/run_extended_window_replay.py

Second, genuinely independent test window for the Gate 3 hand-set-vs-
calibrated comparison, requested because the original validation split
(2025-09-22 -> 2026-07-14) contained zero FAVORABLE-regime days -- the
+31.67% calibrated-model result there could only ever speak to
CAUTION/UNFAVORABLE conditions.

Window chosen and committed to IN WRITING before this script was run
(see chat), via a cheap, read-only scan of NIFTY's own historical
regime state using the EXACT recalibrated production logic
(replay_engine._regime_trend_state_of_truncated + count_distribution_days
+ get_market_regime_verdict, unmodified) -- no trade outcomes were
touched before committing to this range, so the window can't be
second-guessed as picked after seeing results:

  2023-12-11 -> 2024-06-11 (~6 months, 122 trading days)
  38 FAVORABLE days (~31% of the window) -- vs ~3% in the tuning split
  and 0% in validation. Ends 6+ weeks before the tuning split starts
  (2024-07-22) -- zero overlap with either split in either direction.

Methodology held identical to run #3 / Gate 3, deliberately:
  - Same wide 496-ticker universe (already cached, no new price fetch --
    confirmed cached history already reaches back to 2016 for most
    tickers).
  - Same sample_every_n_days=5 cadence as tests/run_backtest.py (which
    produced run #3).
  - Same enable_microstructure_signals=False.
  - Same portfolio simulator settings (n_slots=5, base_risk_pct=1.0,
    starting_equity=100.0) and same 0.3% round-trip cost (baked into
    r_multiple via episode_builder.build_episodes(), untouched).
  - Same FROZEN model: the tuning-split logistic regression is refit
    here (deterministic given unchanged tuning-split data -- this
    reproduces, not re-derives, the exact same coefficients used for
    Gate 3) and Reading A's cutoff (p >= 0.6526920989878143) is reused
    AS-IS, not re-derived from this new window's own outcomes -- doing
    so would be circular.

One deliberate fix vs. run_backtest.py's own sector-index fetch: that
script issues one large, un-chunked get_sector_index_history() call per
sector, which silently truncates to ~100 days regardless of the
requested span (see scoring/sector_indices.py's corrected docstring,
found during the RS_Rating/MACD backfill). This window's RS_Rating needs
roughly 1.5 years of trailing sector-index history -- a naive single
request would badly truncate it. Reuses the chunked-fetch helper built
for that same reason in tests/backfill_rs_macd.py.

Checkpointing: run_backtest() logs progress+ETA every 10 sampled dates
on its own (backtesting/backtest_runner.py); this script also logs at
each of its own pipeline stages, same style as prior long runs.
"""
import sys
sys.path.insert(0, ".")

import glob
import os
import time
from datetime import date, timedelta

import pandas as pd
import statsmodels.api as sm

from backtesting.backtest_runner import run_backtest, print_backtest_summary, populate_sector_cache
from backtesting.baselines import nifty_buy_hold
from backtesting.episode_builder import build_episodes
from backtesting.portfolio_simulator import simulate_portfolio
from backtesting.replay_engine import build_scored_universe_as_of
from scoring.benchmark import get_benchmark_history
from scoring.market_regime import get_vix_history
from scoring.sector_map import sector_map
from technical_analysis.consolidation_features import compute_consolidation_features, compute_rs_line_new_high
from technical_analysis.pattern_system.macd_signal import get_macd_signal
from technical_analysis.pattern_system.swing_detector import SwingDetector
from tests.backfill_rs_macd import _fetch_sector_index_history_chunked
from tests.run_v2_calibration_full import CATEGORICAL_BASELINES, CATEGORICAL_FEATURES, NUMERIC_FEATURES, _build_design_matrix

WINDOW_START = pd.Timestamp("2023-12-11")
WINDOW_END = pd.Timestamp("2024-06-11")
TUNING_SPLIT_END = "2025-09-21"
EXECUTE_CUTOFF = 0.6526920989878143  # Reading A, frozen from the original tuning-split fit -- not re-derived here
N_SLOTS = 5
BASE_RISK_PCT = 1.0
STARTING_EQUITY = 100.0
RAW_OUTPUT_PATH = "data/backtest_results_extended_window.csv"
EPISODE_OUTPUT_PATH = "data/extended_window_episodes_with_v2_features.csv"

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
        if len(df) >= 250:
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
    }


def _policy_hand_set_production(episode: pd.Series) -> float:
    return 1.0 if episode["category"] == "EXECUTE" else 0.0


def _policy_hand_set_score_only(episode: pd.Series) -> float:
    return 1.0 if episode["confidence_score"] >= 65.0 else 0.0


def _policy_calibrated(episode: pd.Series) -> float:
    return 1.0 if episode["predicted_p"] >= EXECUTE_CUTOFF else 0.0


def _summarize(result: dict) -> dict:
    total_return_pct = round(result["final_equity"] - STARTING_EQUITY, 2)
    max_drawdown_pct = result["max_drawdown_pct"]
    cagr_pct = result["cagr_pct"]
    calmar = round(cagr_pct / abs(max_drawdown_pct), 2) if max_drawdown_pct != 0 else 0.0
    return {
        "total_return_pct": total_return_pct, "max_drawdown_pct": max_drawdown_pct,
        "cagr_pct": cagr_pct, "calmar": calmar, "n_taken": result["n_taken"],
        "n_missed_due_to_slots": result["n_missed_due_to_slots"],
        "slot_utilization_pct": result["slot_utilization_pct"],
    }


def main():
    t0 = time.time()
    print(f"Committed window: {WINDOW_START.date()} -> {WINDOW_END.date()}")

    # ---- Stage 1: universe (already cached, no new fetch) ----
    print("\n[Stage 1] Loading universe from data/technical/...")
    universe = _load_universe()
    print(f"  Loaded: {len(universe)} tickers")
    populate_sector_cache(list(universe.keys()))

    # ---- Stage 2: benchmark ----
    print("\n[Stage 2] Loading benchmark history...")
    benchmark_history = get_benchmark_history()
    benchmark_history["Date"] = pd.to_datetime(
        benchmark_history["Date"] if "Date" in benchmark_history.columns else benchmark_history.index
    ).dt.tz_localize(None)
    print(f"  Benchmark rows: {len(benchmark_history)}")

    # ---- Stage 3: VIX (buffer around the historical window, not "today") ----
    print("\n[Stage 3] Loading VIX history...")
    vix_start = (WINDOW_START - timedelta(days=365 * 2)).strftime("%d-%m-%Y")
    vix_end = (WINDOW_END + timedelta(days=5)).strftime("%d-%m-%Y")
    vix_history = get_vix_history(from_date=vix_start, to_date=vix_end)
    print(f"  VIX rows: {len(vix_history) if vix_history is not None else 0}")

    # ---- Stage 4: sector indices, CHUNKED (naive single-request fetch
    # truncates to ~100 days regardless of span -- see module docstring) ----
    print("\n[Stage 4] Loading sector index histories (chunked)...")
    distinct_sectors = {sector_map.get_sector(t) for t in universe}
    distinct_sectors.discard("Unknown")
    sector_start = (WINDOW_START - timedelta(days=365 * 2)).date()
    sector_end = (WINDOW_END + timedelta(days=5)).date()
    sector_index_histories = {}
    for sector in distinct_sectors:
        history = _fetch_sector_index_history_chunked(sector, sector_start, sector_end)
        if history is not None:
            sector_index_histories[sector] = history
    print(f"  Sector indices resolved: {len(sector_index_histories)}/{len(distinct_sectors)}")

    # ---- Stage 5: the expensive step -- raw signal replay ----
    print(f"\n[Stage 5] Running backtest replay: {WINDOW_START.date()} -> {WINDOW_END.date()}, "
          f"sample_every_n_days=5, {len(universe)} tickers. Progress logs every 10 sampled dates.")
    trades = run_backtest(
        universe_histories=universe, benchmark_history=benchmark_history, vix_history=vix_history,
        start_date=WINDOW_START, end_date=WINDOW_END, sample_every_n_days=5,
        sector_index_histories=sector_index_histories, enable_microstructure_signals=False,
    )
    trades.to_csv(RAW_OUTPUT_PATH, index=False)
    print(f"  Raw trade log saved -> {RAW_OUTPUT_PATH} ({len(trades)} rows)")
    print_backtest_summary(trades)
    print(f"  [checkpoint] {(time.time() - t0) / 60:.1f} min elapsed since start")

    # ---- Stage 6: episodes + v2 feature backfill ----
    print("\n[Stage 6] Building episodes + backfilling v2 features...")
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    episodes = build_episodes(trades)
    episodes["episode_start_date"] = pd.to_datetime(episodes["episode_start_date"])
    print(f"  Episodes: {len(episodes)}")

    feature_rows = []
    for n, row in enumerate(episodes.itertuples(), start=1):
        feature_rows.append(_features_for_episode(row.ticker, row.episode_start_date, universe, benchmark_history))
        if n % 200 == 0 or n == len(episodes):
            print(f"    [{n}/{len(episodes)}] v2 features computed")
    episodes = pd.concat([episodes.reset_index(drop=True), pd.DataFrame(feature_rows)], axis=1)
    episodes["excluded_insufficient_history"] = (
        (episodes["dist_52w_high_invalidated_reason"] == "INSUFFICIENT_HISTORY")
        | (episodes["rs_line_invalidated_reason"] == "INSUFFICIENT_HISTORY")
    )
    print(f"  [checkpoint] {(time.time() - t0) / 60:.1f} min elapsed since start")

    # ---- Stage 7: RS_Rating + macd_signal backfill on real episodes ----
    print("\n[Stage 7] Backfilling RS_Rating + macd_signal on real episodes...")
    real = episodes[episodes["category"].isin(["EXECUTE", "ALERT_WATCHLIST"])].copy()
    fitting_pool = real[~real["excluded_insufficient_history"]].copy()
    distinct_dates = sorted(fitting_pool["episode_start_date"].unique())
    print(f"  Real episodes: {len(real)}, non-excluded: {len(fitting_pool)}, distinct dates: {len(distinct_dates)}")

    rs_rating_by_date_ticker = {}
    for n, as_of_date in enumerate(distinct_dates, start=1):
        _, _, rs_ratings = build_scored_universe_as_of(as_of_date, universe, benchmark_history, sector_index_histories)
        for ticker, value in rs_ratings.items():
            rs_rating_by_date_ticker[(as_of_date, ticker)] = value
        print(f"    RS_Rating: [{n}/{len(distinct_dates)}] dates done")

    macd_by_row = {}
    for row in fitting_pool.itertuples():
        history = universe.get(row.ticker)
        truncated = history[history["Date"] <= row.episode_start_date] if history is not None else None
        macd_by_row[row.Index] = get_macd_signal(truncated) if truncated is not None and len(truncated) >= 15 else None

    episodes["RS_Rating"] = episodes.apply(
        lambda r: rs_rating_by_date_ticker.get((r["episode_start_date"], r["ticker"])), axis=1,
    )
    episodes["macd_signal"] = pd.Series(macd_by_row)
    episodes.to_csv(EPISODE_OUTPUT_PATH, index=False)
    print(f"  Saved -> {EPISODE_OUTPUT_PATH}")
    print(f"  [checkpoint] {(time.time() - t0) / 60:.1f} min elapsed since start")

    # ---- Stage 8: score with the FROZEN tuning-split model ----
    print("\n[Stage 8] Refitting tuning-split model (reproduces, not re-derives, Gate 3's coefficients)...")
    tuning_log = pd.read_csv("data/run3_episodes_with_v2_features.csv", low_memory=False)
    tuning_log["episode_start_date"] = pd.to_datetime(tuning_log["episode_start_date"])
    tuning_real = tuning_log[tuning_log["category"].isin(["EXECUTE", "ALERT_WATCHLIST"])].copy()
    tuning_fitting = tuning_real[~tuning_real["excluded_insufficient_history"]].copy()
    tuning = tuning_fitting[tuning_fitting["episode_start_date"] <= TUNING_SPLIT_END].reset_index(drop=True).copy()
    tuning["win"] = (tuning["net_return_pct"] > 0).astype(int)
    X_tuning, scaler_mean, scaler_std = _build_design_matrix(tuning, None, None)
    model = sm.Logit(tuning["win"], X_tuning.astype(float)).fit(disp=0)
    print(f"  Refit on {len(tuning)} tuning-split rows, {X_tuning.shape[1]} parameters -- matches Gate 3's own fit.")

    # `real`/`fitting_pool` (defined in Stage 7) were both captured BEFORE
    # RS_Rating/macd_signal were merged onto `episodes` -- re-derive from
    # `episodes` itself, which has both columns, instead of either stale copy.
    real = episodes[episodes["category"].isin(["EXECUTE", "ALERT_WATCHLIST"])].copy()
    fitting_pool = real[~real["excluded_insufficient_history"]].copy()
    fitting_pool = fitting_pool[fitting_pool["RS_Rating"].notna() & fitting_pool["macd_signal"].notna()].copy()
    print(f"  New-window candidates with complete RS_Rating/macd_signal: {len(fitting_pool)}")

    X_new, _, _ = _build_design_matrix(fitting_pool, scaler_mean, scaler_std)
    X_new = X_new.reindex(columns=X_tuning.columns, fill_value=0.0)
    fitting_pool["predicted_p"] = model.predict(X_new.astype(float)).to_numpy()

    # ---- Stage 9: portfolio simulation, same 3 policies + NIFTY as Gate 3 ----
    print("\n[Stage 9] Running portfolio simulator (n_slots=5, base_risk_pct=1.0)...")
    n_hand_set_production = (fitting_pool["category"] == "EXECUTE").sum()
    n_hand_set_score_only = (fitting_pool["confidence_score"] >= 65.0).sum()
    n_calibrated_execute = (fitting_pool["predicted_p"] >= EXECUTE_CUTOFF).sum()
    print(f"  Hand-set FULL PRODUCTION selects: {n_hand_set_production}/{len(fitting_pool)}")
    print(f"  Hand-set SCORE-ONLY selects: {n_hand_set_score_only}/{len(fitting_pool)}")
    print(f"  Calibrated (Reading A, frozen cutoff) selects: {n_calibrated_execute}/{len(fitting_pool)}")

    hand_set_production_summary = _summarize(simulate_portfolio(
        fitting_pool, _policy_hand_set_production, n_slots=N_SLOTS, base_risk_pct=BASE_RISK_PCT, starting_equity=STARTING_EQUITY,
    ))
    hand_set_score_only_summary = _summarize(simulate_portfolio(
        fitting_pool, _policy_hand_set_score_only, n_slots=N_SLOTS, base_risk_pct=BASE_RISK_PCT, starting_equity=STARTING_EQUITY,
    ))
    calibrated_summary = _summarize(simulate_portfolio(
        fitting_pool, _policy_calibrated, n_slots=N_SLOTS, base_risk_pct=BASE_RISK_PCT, starting_equity=STARTING_EQUITY,
    ))

    nifty = nifty_buy_hold(benchmark_history, WINDOW_START, WINDOW_END)

    print("\n" + "=" * 100)
    print(f"  GATE 3, SECOND WINDOW -- {WINDOW_START.date()} -> {WINDOW_END.date()} (38/122 days FAVORABLE)")
    print("=" * 100)
    header = f"{'metric':<14}{'Hand-set (full prod)':<24}{'Hand-set (score-only)':<24}{'Calibrated (Reading A)':<24}{'NIFTY buy-hold':<14}"
    print(header)
    print("-" * len(header))
    print(f"{'Total return':<14}{str(hand_set_production_summary['total_return_pct']) + '%':<24}"
          f"{str(hand_set_score_only_summary['total_return_pct']) + '%':<24}"
          f"{str(calibrated_summary['total_return_pct']) + '%':<24}{str(nifty['total_return_pct']) + '%':<14}")
    print(f"{'Max drawdown':<14}{str(hand_set_production_summary['max_drawdown_pct']) + '%':<24}"
          f"{str(hand_set_score_only_summary['max_drawdown_pct']) + '%':<24}"
          f"{str(calibrated_summary['max_drawdown_pct']) + '%':<24}{str(nifty['max_drawdown_pct']) + '%':<14}")
    print(f"{'Calmar':<14}{hand_set_production_summary['calmar']:<24}{hand_set_score_only_summary['calmar']:<24}"
          f"{calibrated_summary['calmar']:<24}{nifty['calmar']:<14}")
    print(f"{'Taken':<14}{hand_set_production_summary['n_taken']:<24}{hand_set_score_only_summary['n_taken']:<24}"
          f"{calibrated_summary['n_taken']:<24}{'--':<14}")
    print(f"{'Missed (slots)':<14}{hand_set_production_summary['n_missed_due_to_slots']:<24}"
          f"{hand_set_score_only_summary['n_missed_due_to_slots']:<24}"
          f"{calibrated_summary['n_missed_due_to_slots']:<24}{'--':<14}")

    comparison = pd.DataFrame([
        {"strategy": "Hand-set FULL PRODUCTION (category==EXECUTE)", **hand_set_production_summary},
        {"strategy": "Hand-set SCORE-ONLY (score>=65, no ceiling)", **hand_set_score_only_summary},
        {"strategy": "Calibrated (Reading A, frozen p>=0.6527)", **calibrated_summary},
        {"strategy": "NIFTY buy-and-hold", "total_return_pct": nifty["total_return_pct"],
         "max_drawdown_pct": nifty["max_drawdown_pct"], "cagr_pct": nifty["cagr_pct"], "calmar": nifty["calmar"],
         "n_taken": None, "n_missed_due_to_slots": None, "slot_utilization_pct": None},
    ])
    comparison.to_csv("data/gate3_second_window_comparison.csv", index=False)
    print(f"\nSaved -> data/gate3_second_window_comparison.csv")
    print(f"\nTotal runtime: {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
