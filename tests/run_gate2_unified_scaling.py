"""
Falcon — Gate 2 Extension: Unified Scaled-Exposure Portfolio Simulation
Run from project root: python tests/run_gate2_unified_scaling.py

Tests whether the choke-point decomposition's finding (every blocked
population -- regime, sector, pattern-requirement/MONITOR -- clears Gate
1's 2.5%+ "resembles EXECUTE" bar at the episode level) survives being
tested at the PORTFOLIO level: trading more signals means competing for
the same fixed slots, and per-episode expectancy alone can't show
drawdown/slot-contention effects (the exact reason
backtesting/portfolio_simulator.py, I-5, exists).

Compares the existing best performer (policy "e_sector_aware_caution")
against the new "unified_scaling" policy (backtesting/portfolio_simulator.py's
make_unified_scaling_policy) at both proposed MONITOR risk weights (0.5
and 0.75 -- cheap to run both). Pure post-processing on the already-
corrected CSV -- no replay, no engine change beyond the new policy
function itself (which changes no existing policy's behavior).
"""
import sys
sys.path.insert(0, ".")

import pandas as pd

from backtesting.episode_builder import build_episodes
from backtesting.portfolio_simulator import (
    make_unified_scaling_policy,
    policy_sector_aware_caution,
    simulate_portfolio,
)

CORRECTED_PATH = "data/backtest_results_run2_corrected.csv"

POLICIES = {
    "e_sector_aware_caution (baseline)": policy_sector_aware_caution,
    "f_unified_scaling (MONITOR@0.5)": make_unified_scaling_policy(0.5),
    "f_unified_scaling (MONITOR@0.75)": make_unified_scaling_policy(0.75),
}


def _calmar(cagr_pct: float, max_drawdown_pct: float) -> float:
    return round(cagr_pct / abs(max_drawdown_pct), 2) if max_drawdown_pct != 0 else 0.0


def main():
    trades = pd.read_csv(CORRECTED_PATH)
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])

    episodes = build_episodes(trades)

    # make_unified_scaling_policy's RR-floor branch needs caps_applied,
    # which episode_builder.py's own schema doesn't carry (out of its
    # original run #1 scope) -- re-attach it via the same founder-row
    # merge tests/choke_point_decomposition.py uses (episode_start_date
    # IS the founder's own entry_date, by construction).
    founder_fields = trades[["ticker", "entry_date", "caps_applied"]].rename(
        columns={"entry_date": "episode_start_date"}
    )
    episodes = episodes.merge(founder_fields, on=["ticker", "episode_start_date"], how="left")

    print("=" * 90)
    print("  UNIFIED SCALED-EXPOSURE PORTFOLIO SIMULATION (corrected run #2, 5 slots, 1% base risk)")
    print("=" * 90)

    rows = []
    for name, policy in POLICIES.items():
        result = simulate_portfolio(episodes, policy, n_slots=5, base_risk_pct=1.0, starting_equity=100.0)
        calmar = _calmar(result["cagr_pct"], result["max_drawdown_pct"])
        rows.append({
            "policy": name,
            "n_taken": result["n_taken"],
            "n_missed_due_to_slots": result["n_missed_due_to_slots"],
            "slot_utilization_pct": result["slot_utilization_pct"],
            "final_equity": result["final_equity"],
            "max_drawdown_pct": result["max_drawdown_pct"],
            "cagr_pct": result["cagr_pct"],
            "calmar": calmar,
        })
        print(f"\n{name}:")
        print(f"  episodes deployed (n_taken):  {result['n_taken']}")
        print(f"  missed due to slot exhaustion: {result['n_missed_due_to_slots']}")
        print(f"  slot utilization:              {result['slot_utilization_pct']}%")
        print(f"  final equity (start=100):     {result['final_equity']}")
        print(f"  max drawdown:                  {result['max_drawdown_pct']}%")
        print(f"  CAGR:                          {result['cagr_pct']}%")
        print(f"  Calmar:                        {calmar}")

    comparison = pd.DataFrame(rows)
    comparison.to_csv("data/gate2_unified_scaling_comparison.csv", index=False)
    print(f"\n{'=' * 90}")
    print(comparison.to_string(index=False))
    print(f"\nComparison table saved -> data/gate2_unified_scaling_comparison.csv")


if __name__ == "__main__":
    main()
