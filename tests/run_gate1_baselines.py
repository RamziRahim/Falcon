"""
Falcon — Gate 1 baselines + cap-vs-scale runner (Phase 1.5/1.6)
Run from project root: python tests/run_gate1_baselines.py

Loads the same universe/benchmark run #1 used, runs the three I-4
baselines and the I-5/1.6 policy comparison against run #1's actual
episode log, and prints everything needed for the Gate 1 report.
"""
import glob
import os
import sys

sys.path.insert(0, ".")

import pandas as pd

from backtesting.baselines import naive_momentum_baseline, nifty_buy_hold, random_entry_control, summarize_random_control
from backtesting.episode_builder import build_episodes
from backtesting.portfolio_simulator import compare_policies
from scoring.benchmark import get_benchmark_history

print("Loading universe from data/technical/...")
universe_histories = {}
for path in sorted(glob.glob("data/technical/*.parquet")):
    ticker = os.path.basename(path).replace(".parquet", "")
    df = pd.read_parquet(path)
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    df = df.sort_values("Date").reset_index(drop=True)
    if len(df) >= 250:
        universe_histories[ticker] = df
print(f"  Loaded: {len(universe_histories)} tickers")

print("Loading benchmark history...")
benchmark_history = get_benchmark_history()
benchmark_history["Date"] = pd.to_datetime(
    benchmark_history["Date"] if "Date" in benchmark_history.columns else benchmark_history.index
).dt.tz_localize(None)

trades = pd.read_csv("data/backtest_results.csv")
episodes = build_episodes(trades)
episodes["episode_start_date"] = pd.to_datetime(episodes["episode_start_date"])
episodes["episode_end_date"] = pd.to_datetime(episodes["episode_end_date"])

start_date = episodes["episode_start_date"].min()
end_date = pd.to_datetime(trades["entry_date"]).max()
print(f"Window: {start_date.date()} -> {end_date.date()}")

# ---------------------------------------------------------------------------
# I-4 Baselines
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("  BASELINE 1: NIFTY BUY-AND-HOLD")
print("=" * 70)
buy_hold = nifty_buy_hold(benchmark_history, start_date, end_date)
print(buy_hold)

execute_episodes = episodes[episodes["category"] == "EXECUTE"]
median_target_pct = trades["target_pct"].median()
median_stop_pct = trades["stop_pct"].median()
print(f"\nUsing median target_pct={median_target_pct:.2f}%, stop_pct={median_stop_pct:.2f}% "
      f"(from run #1's actual signals) for the random-entry control's risk sizing.")

print("\n" + "=" * 70)
print("  BASELINE 2: RANDOM-ENTRY CONTROL (K=100)")
print("=" * 70)
random_draws = random_entry_control(
    universe_histories, start_date, end_date,
    target_pct=median_target_pct, stop_pct=median_stop_pct, k=100, max_holding_days=20, seed=42,
)
random_summary = summarize_random_control(random_draws)
print(random_summary)

execute_net_expectancy = execute_episodes["net_return_pct"].mean()
print(f"\nEXECUTE episode-level net expectancy: {execute_net_expectancy:.2f}%")
print(f"Random control 95th percentile (net): {random_summary['p95_net_return_pct']:.2f}%")
print(f"EXECUTE beats random control's 95th percentile: "
      f"{execute_net_expectancy > random_summary['p95_net_return_pct']}")

print("\n" + "=" * 70)
print("  BASELINE 3: NAIVE MOMENTUM")
print("=" * 70)
window_dates = benchmark_history[
    (benchmark_history["Date"] >= start_date) & (benchmark_history["Date"] <= end_date)
].sort_values("Date")["Date"]
sample_dates = list(window_dates.iloc[::5])
print(f"Sampling every 5th trading day -> {len(sample_dates)} sample dates")

momentum_results = naive_momentum_baseline(universe_histories, sample_dates, lookback_days=63, max_holding_days=20)
print(f"Momentum trades taken: {len(momentum_results)}")
if not momentum_results.empty:
    print(f"  mean net_return_pct: {momentum_results['net_return_pct'].mean():.2f}%")
    print(f"  win_rate: {(momentum_results['net_return_pct'] > 0).mean() * 100:.1f}%")

# ---------------------------------------------------------------------------
# 1.6 Cap-vs-scale policy comparison
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("  1.6 CAP-VS-SCALE POLICY COMPARISON (n_slots=5, base_risk_pct=1.0)")
print("=" * 70)
comparison = compare_policies(episodes, n_slots=5, base_risk_pct=1.0)
print(comparison.to_string(index=False))

comparison.to_csv("data/gate1_policy_comparison.csv", index=False)
momentum_results.to_csv("data/gate1_momentum_baseline.csv", index=False)
random_draws.to_csv("data/gate1_random_control_draws.csv", index=False)
print("\nSaved: data/gate1_policy_comparison.csv, data/gate1_momentum_baseline.csv, data/gate1_random_control_draws.csv")
