"""
Falcon — Analysis Orchestrator (Phase 0 definition-of-done)
Run from project root: python tests/run_analysis.py

Thin orchestrator, extended in later phases: loads run #1's raw signal
log (data/backtest_results.csv), collapses it into trade episodes via
backtesting.episode_builder.build_episodes(), and prints a side-by-side
raw-signal-count vs episode-count vs gross/net expectancy comparison per
category. Confirms the episode-collapsing plumbing actually works before
Phase 1 builds the full diagnostic suite on top of episode-level data --
this script does no diagnosis itself.
"""
import sys
sys.path.insert(0, ".")

import pandas as pd

from backtesting.backtest_runner import compute_expectancy, print_ceiling_attribution
from backtesting.component_diagnostics import print_component_diagnostics
from backtesting.episode_builder import build_episodes
from backtesting.shadow_log import print_unfavorable_shadow_log

RAW_RESULTS_PATH = "data/backtest_results.csv"


def _expectancy(df: pd.DataFrame, return_column: str) -> float:
    if df.empty:
        return 0.0

    wins = df[df[return_column] > 0]
    losses = df[df[return_column] <= 0]  # includes exact breakeven

    win_rate = len(wins) / len(df)
    loss_rate = 1 - win_rate
    avg_win = wins[return_column].mean() if not wins.empty else 0.0
    avg_loss = losses[return_column].mean() if not losses.empty else 0.0

    return compute_expectancy(win_rate, avg_win, loss_rate, avg_loss)


def main():
    print(f"Loading run #1 raw signal log from {RAW_RESULTS_PATH}...")
    trades = pd.read_csv(RAW_RESULTS_PATH)
    print(f"  Raw signals: {len(trades)}")

    episodes = build_episodes(trades)
    print(f"  Episodes after absorption: {len(episodes)}")

    print("\n" + "=" * 78)
    print("  RAW SIGNALS vs EPISODES, BY CATEGORY")
    print("=" * 78)

    categories = sorted(set(trades["category"]) | set(episodes["category"]))
    for category in categories:
        raw_n = int((trades["category"] == category).sum())
        ep = episodes[episodes["category"] == category]
        ep_n = len(ep)
        reduction_pct = (1 - ep_n / raw_n) * 100 if raw_n else 0.0
        gross_exp = _expectancy(ep, "gross_return_pct")
        net_exp = _expectancy(ep, "net_return_pct")
        print(
            f"  {category}: raw_signals={raw_n}, episodes={ep_n} "
            f"(-{reduction_pct:.1f}% from absorption)  "
            f"gross_expectancy={gross_exp:.2f}%  net_expectancy={net_exp:.2f}%"
        )

    print("=" * 78 + "\n")

    print("=" * 78)
    print("  CEILING ATTRIBUTION -- EPISODE LEVEL (Phase 1.2)")
    print("  (net_return_pct, i.e. already net of ROUND_TRIP_COST_PCT)")
    print("=" * 78)
    print_ceiling_attribution(episodes, return_column="net_return_pct")

    print_component_diagnostics(episodes)

    print_unfavorable_shadow_log(episodes)


if __name__ == "__main__":
    main()
