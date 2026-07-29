"""
Falcon — Run #3 Step 2: Unified-Scaling (MONITOR@0.5) Portfolio Simulation
Run from project root: python tests/run3_portfolio_simulation.py

Second pass over run #3's raw signal log (data/backtest_results_run3_wide_universe.csv,
496-ticker Nifty 500 universe, 2024-07-25 -> 2026-07-25) -- same structure
as tests/run_gate2_unified_scaling.py: build episodes, then apply
make_unified_scaling_policy(0.5) via the portfolio simulator. MONITOR@0.5
was decided as the adopted policy in Gate 2 (data/gate2_report.md) --
this is that policy's first real test on the widened universe, not a
fresh comparison across policy variants.

Compares against Nifty buy-and-hold over the identical window
(backtesting/baselines.py's nifty_buy_hold()) -- the actual question this
whole run exists to answer: does Falcon beat just holding the index.
"""
import sys
sys.path.insert(0, ".")

import pandas as pd

from backtesting.baselines import nifty_buy_hold
from backtesting.episode_builder import build_episodes
from backtesting.portfolio_simulator import make_unified_scaling_policy, simulate_portfolio
from scoring.benchmark import get_benchmark_history

RAW_PATH = "data/backtest_results_run3_wide_universe.csv"
START_DATE = pd.Timestamp("2024-07-25")
END_DATE = pd.Timestamp("2026-07-25")


def main():
    trades = pd.read_csv(RAW_PATH)
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    print(f"Raw signals: {len(trades)}")

    episodes = build_episodes(trades)
    print(f"Episodes after absorption: {len(episodes)}")

    # make_unified_scaling_policy's RR-floor branch needs caps_applied,
    # which episode_builder.py's own schema doesn't carry -- re-attach it
    # via the founder-row merge (episode_start_date IS the founder's own
    # entry_date), same technique as tests/choke_point_decomposition.py
    # and tests/run_gate2_unified_scaling.py.
    founder_fields = trades[["ticker", "entry_date", "caps_applied"]].rename(
        columns={"entry_date": "episode_start_date"}
    )
    episodes = episodes.merge(founder_fields, on=["ticker", "episode_start_date"], how="left")

    policy = make_unified_scaling_policy(0.5)
    result = simulate_portfolio(episodes, policy, n_slots=5, base_risk_pct=1.0, starting_equity=100.0)

    total_return_pct = round(result["final_equity"] - 100.0, 2)
    max_drawdown_pct = result["max_drawdown_pct"]
    cagr_pct = result["cagr_pct"]
    calmar = round(cagr_pct / abs(max_drawdown_pct), 2) if max_drawdown_pct != 0 else 0.0

    benchmark_history = get_benchmark_history()
    benchmark_history["Date"] = pd.to_datetime(
        benchmark_history["Date"] if "Date" in benchmark_history.columns else benchmark_history.index
    ).dt.tz_localize(None)
    nifty = nifty_buy_hold(benchmark_history, START_DATE, END_DATE)

    print("\n" + "=" * 78)
    print("  RUN #3 (WIDE UNIVERSE, MONITOR@0.5) vs NIFTY BUY-AND-HOLD")
    print(f"  Window: {START_DATE.date()} -> {END_DATE.date()}")
    print("=" * 78)
    print(f"\nEpisodes deployed (n_taken):     {result['n_taken']}")
    print(f"Missed due to slot exhaustion:    {result['n_missed_due_to_slots']}")
    print(f"Slot utilization:                 {result['slot_utilization_pct']}%")
    print()
    falcon_return_str = f"{total_return_pct}%"
    nifty_return_str = f"{nifty['total_return_pct']}%"
    falcon_dd_str = f"{max_drawdown_pct}%"
    nifty_dd_str = f"{nifty['max_drawdown_pct']}%"
    print(f"{'metric':<20}{'Falcon (MONITOR@0.5)':<25}{'NIFTY buy-and-hold':<20}")
    print("-" * 65)
    print(f"{'Total return':<20}{falcon_return_str:<25}{nifty_return_str:<20}")
    print(f"{'Max drawdown':<20}{falcon_dd_str:<25}{nifty_dd_str:<20}")
    print(f"{'Calmar':<20}{calmar:<25}{nifty['calmar']:<20}")

    comparison = pd.DataFrame([
        {"strategy": "Falcon (MONITOR@0.5, wide universe)", "total_return_pct": total_return_pct,
         "max_drawdown_pct": max_drawdown_pct, "cagr_pct": cagr_pct, "calmar": calmar,
         "n_taken": result["n_taken"], "n_missed_due_to_slots": result["n_missed_due_to_slots"],
         "slot_utilization_pct": result["slot_utilization_pct"]},
        {"strategy": "NIFTY buy-and-hold", "total_return_pct": nifty["total_return_pct"],
         "max_drawdown_pct": nifty["max_drawdown_pct"], "cagr_pct": nifty["cagr_pct"], "calmar": nifty["calmar"],
         "n_taken": None, "n_missed_due_to_slots": None, "slot_utilization_pct": None},
    ])
    comparison.to_csv("data/run3_portfolio_vs_nifty.csv", index=False)
    print(f"\nComparison saved -> data/run3_portfolio_vs_nifty.csv")
    print("=" * 78)


if __name__ == "__main__":
    main()
