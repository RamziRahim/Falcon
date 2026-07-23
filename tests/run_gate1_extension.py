"""
Falcon — Gate 1 extension tests (per the human's decision #5)
Run from project root: python tests/run_gate1_extension.py

Two cheap post-processing tests on existing logs (no re-runs) requested
before Phase 2 starts, to properly evaluate the "EXECUTE ~ naive momentum"
tie flagged in the Gate 1 report:

(a) Runs the naive-momentum baseline's own trades through the SAME
    portfolio simulator (identical 5 slots, identical 1% base risk,
    identical ROUND_TRIP_COST_PCT already embedded in net_return_pct) used
    for the Falcon policy comparison, and compares Calmar ratio / max
    drawdown against Falcon's sector-aware policy (e).

    Momentum trades have no natural stop distance (the baseline is
    deliberately "no target/stop, just a fixed holding period" -- see
    baselines.py's own docstring), so there's no native r_multiple. To
    keep the sizing convention genuinely identical rather than silently
    advantaging one side, momentum's r_multiple uses the SAME reference
    risk unit already used for the random-entry control baseline (run #1's
    real median stop_pct, ~5.93%) -- i.e. "what would this same % move
    have been worth in R if it had used a typical real signal's risk
    distance." Every momentum trade is taken at full size (risk_fraction
    1.0) -- momentum has no capped/genuine/category distinction, it's a
    single undifferentiated stream.

(b) Two-sample comparison of net_return_pct: the full score>=65 population
    (EXECUTE + capped ALERT_WATCHLIST, n~108 -- every episode that scored
    EXECUTE-grade regardless of what the ceiling did to its final
    category) vs naive momentum (n=98). Welch's t-test (unequal variance,
    doesn't assume the two populations have the same spread) plus
    Mann-Whitney U as a distribution-shape-agnostic cross-check, mean
    difference with a 95% CI, and Cohen's d for effect size.
"""
import glob
import os
import sys

sys.path.insert(0, ".")

import numpy as np
import pandas as pd
from scipy import stats

from backtesting.baselines import naive_momentum_baseline
from backtesting.episode_builder import build_episodes
from backtesting.portfolio_simulator import NAMED_POLICIES, simulate_portfolio
from scoring.benchmark import get_benchmark_history

REFERENCE_STOP_PCT = 5.93  # run #1's actual median stop_pct -- see module docstring
N_SLOTS = 5
BASE_RISK_PCT = 1.0

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

trades = pd.read_csv("data/backtest_results.csv")
episodes = build_episodes(trades)
episodes["episode_start_date"] = pd.to_datetime(episodes["episode_start_date"])
episodes["episode_end_date"] = pd.to_datetime(episodes["episode_end_date"])

start_date = episodes["episode_start_date"].min()
end_date = pd.to_datetime(trades["entry_date"]).max()

benchmark_history = get_benchmark_history()
benchmark_history["Date"] = pd.to_datetime(
    benchmark_history["Date"] if "Date" in benchmark_history.columns else benchmark_history.index
).dt.tz_localize(None)
window_dates = benchmark_history[
    (benchmark_history["Date"] >= start_date) & (benchmark_history["Date"] <= end_date)
].sort_values("Date")["Date"]
sample_dates = list(window_dates.iloc[::5])

print(f"Rebuilding naive momentum baseline ({len(sample_dates)} sample dates, now with exit_date)...")
momentum = naive_momentum_baseline(universe_histories, sample_dates, lookback_days=63, max_holding_days=20)
print(f"  Momentum trades: {len(momentum)}")

# ---------------------------------------------------------------------------
# (a) Momentum through the SAME portfolio simulator as Falcon
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("  (a) MOMENTUM THROUGH THE SAME PORTFOLIO SIMULATOR")
print("=" * 70)

momentum_episodes = pd.DataFrame({
    "episode_start_date": pd.to_datetime(momentum["as_of_date"]),
    "episode_end_date": pd.to_datetime(momentum["exit_date"]),
    "r_multiple": momentum["net_return_pct"] / REFERENCE_STOP_PCT,
    "category": "MOMENTUM",           # unused by the always-take policy below
    "confidence_score": 100.0,        # unused
    "market_regime_verdict": "N/A",   # unused
    "sector_health_verdict": "N/A",   # unused
})

def _always_take_full_size(_episode) -> float:
    return 1.0

momentum_result = simulate_portfolio(
    momentum_episodes, _always_take_full_size, n_slots=N_SLOTS, base_risk_pct=BASE_RISK_PCT,
)
momentum_calmar = (
    momentum_result["cagr_pct"] / abs(momentum_result["max_drawdown_pct"])
    if momentum_result["max_drawdown_pct"] != 0 else float("inf")
)

falcon_e_result = simulate_portfolio(
    episodes, NAMED_POLICIES["e_sector_aware_caution"], n_slots=N_SLOTS, base_risk_pct=BASE_RISK_PCT,
)
falcon_e_calmar = (
    falcon_e_result["cagr_pct"] / abs(falcon_e_result["max_drawdown_pct"])
    if falcon_e_result["max_drawdown_pct"] != 0 else float("inf")
)

comparison = pd.DataFrame([
    {"system": "momentum_baseline", "n_taken": momentum_result["n_taken"],
     "n_missed_due_to_slots": momentum_result["n_missed_due_to_slots"],
     "final_equity": momentum_result["final_equity"], "max_drawdown_pct": momentum_result["max_drawdown_pct"],
     "cagr_pct": momentum_result["cagr_pct"], "calmar": round(momentum_calmar, 2)},
    {"system": "falcon_e_sector_aware", "n_taken": falcon_e_result["n_taken"],
     "n_missed_due_to_slots": falcon_e_result["n_missed_due_to_slots"],
     "final_equity": falcon_e_result["final_equity"], "max_drawdown_pct": falcon_e_result["max_drawdown_pct"],
     "cagr_pct": falcon_e_result["cagr_pct"], "calmar": round(falcon_e_calmar, 2)},
])
print(comparison.to_string(index=False))
print(f"\nFalcon-(e) wins on Calmar: {falcon_e_calmar > momentum_calmar}")
print(f"Falcon-(e) wins on max drawdown (less negative): {falcon_e_result['max_drawdown_pct'] > momentum_result['max_drawdown_pct']}")

comparison.to_csv("data/gate1_extension_portfolio_comparison.csv", index=False)

# ---------------------------------------------------------------------------
# (b) score>=65 population vs momentum -- properly powered mean comparison
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("  (b) SCORE>=65 POPULATION vs MOMENTUM -- TWO-SAMPLE COMPARISON")
print("=" * 70)

score_65_plus = episodes[episodes["confidence_score"] >= 65.0]
falcon_returns = score_65_plus["net_return_pct"].to_numpy()
momentum_returns = momentum["net_return_pct"].to_numpy()

print(f"Falcon score>=65 population: n={len(falcon_returns)}, mean={falcon_returns.mean():.2f}%, "
      f"std={falcon_returns.std(ddof=1):.2f}%")
print(f"Momentum baseline:          n={len(momentum_returns)}, mean={momentum_returns.mean():.2f}%, "
      f"std={momentum_returns.std(ddof=1):.2f}%")

t_stat, t_pvalue = stats.ttest_ind(falcon_returns, momentum_returns, equal_var=False)
u_stat, u_pvalue = stats.mannwhitneyu(falcon_returns, momentum_returns, alternative="two-sided")

mean_diff = falcon_returns.mean() - momentum_returns.mean()
se_diff = np.sqrt(falcon_returns.var(ddof=1) / len(falcon_returns) + momentum_returns.var(ddof=1) / len(momentum_returns))
# Welch-Satterthwaite degrees of freedom for the CI, matching ttest_ind(equal_var=False)
df_num = (falcon_returns.var(ddof=1) / len(falcon_returns) + momentum_returns.var(ddof=1) / len(momentum_returns)) ** 2
df_den = (
    (falcon_returns.var(ddof=1) / len(falcon_returns)) ** 2 / (len(falcon_returns) - 1)
    + (momentum_returns.var(ddof=1) / len(momentum_returns)) ** 2 / (len(momentum_returns) - 1)
)
welch_df = df_num / df_den
ci_margin = stats.t.ppf(0.975, welch_df) * se_diff
ci_low, ci_high = mean_diff - ci_margin, mean_diff + ci_margin

pooled_std = np.sqrt(((len(falcon_returns) - 1) * falcon_returns.var(ddof=1)
                      + (len(momentum_returns) - 1) * momentum_returns.var(ddof=1))
                     / (len(falcon_returns) + len(momentum_returns) - 2))
cohens_d = mean_diff / pooled_std

print(f"\nMean difference (Falcon - momentum): {mean_diff:.2f}pp, 95% CI [{ci_low:.2f}, {ci_high:.2f}]")
print(f"Welch's t-test: t={t_stat:.3f}, p={t_pvalue:.4f}")
print(f"Mann-Whitney U: U={u_stat:.1f}, p={u_pvalue:.4f}")
print(f"Cohen's d: {cohens_d:.3f}")
print(f"\nStatistically significant at alpha=0.05: {t_pvalue < 0.05}")

pd.DataFrame([{
    "falcon_n": len(falcon_returns), "falcon_mean": round(falcon_returns.mean(), 2),
    "momentum_n": len(momentum_returns), "momentum_mean": round(momentum_returns.mean(), 2),
    "mean_diff": round(mean_diff, 2), "ci_low": round(ci_low, 2), "ci_high": round(ci_high, 2),
    "t_stat": round(t_stat, 3), "t_pvalue": round(t_pvalue, 4),
    "u_stat": round(u_stat, 1), "u_pvalue": round(u_pvalue, 4),
    "cohens_d": round(cohens_d, 3),
}]).to_csv("data/gate1_extension_mean_comparison.csv", index=False)

print("\nSaved: data/gate1_extension_portfolio_comparison.csv, data/gate1_extension_mean_comparison.csv")
