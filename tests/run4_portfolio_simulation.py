"""
Falcon — Run #4: Canonical Baseline Under the New Production categorize()
Run from project root: python tests/run4_portfolio_simulation.py

The replacement headline numbers for run #3's own, now that Phase 4.6
has replaced get_ceiling()'s hard regime/sector cap with the calibrated
v2 model for every EXECUTE-eligible, pattern-confirmed candidate. Same
496-ticker wide universe, same 2-year window, same portfolio simulator
parameters (n_slots=5, base_risk_pct=1.0, starting_equity=100.0, 0.3%
round-trip cost baked into r_multiple via episode_builder.build_episodes(),
untouched) as run #3's own tests/run3_portfolio_simulation.py.

Two policies, not one -- run #3's own headline used
make_unified_scaling_policy(0.5) ("MONITOR@0.5"), Gate 2's adopted
unified-scaling scheme. That policy's own internal gate classification
(_unified_scaling_gate()) still checks market_regime_verdict/
sector_health_verdict to decide WHY a score>=65 candidate isn't EXECUTE
("regime_ceiling" vs "sector_ceiling"), assigning partial risk on that
basis -- but under the new categorize(), regime/sector no longer
determine EXECUTE-eligibility at all; the calibrated model's predicted_p
does. Reapplying MONITOR@0.5 verbatim would still run and produce a
number, but that number's own internal "why 0.5 vs 0" story is now
built on a mechanism that no longer exists -- a score>=65,
ALERT_WATCHLIST-category row under the new system is ALERT_WATCHLIST
because predicted_p fell below the model's cutoff, not because of a
regime/sector ceiling, even though _unified_scaling_gate() would still
label it "regime_ceiling"/"sector_ceiling" and size it at 0.5. Reported
here anyway, explicitly labeled as a literal re-application for
continuity with run #3's own reported methodology, NOT as a
meaningfully-reasoned policy under the new system. policy_hard_cap
(EXECUTE-only, full size) is the primary/headline number -- it's the
new production categorize()'s own natural, unambiguous "what gets
traded" definition, with no reused-but-now-stale internal reasoning.
"""
import sys
sys.path.insert(0, ".")

import pandas as pd

from backtesting.baselines import nifty_buy_hold
from backtesting.episode_builder import build_episodes
from backtesting.portfolio_simulator import make_unified_scaling_policy, policy_hard_cap, simulate_portfolio
from scoring.benchmark import get_benchmark_history

RAW_PATH = "data/backtest_results_run4_calibrated_model.csv"
N_SLOTS = 5
BASE_RISK_PCT = 1.0
STARTING_EQUITY = 100.0


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
    trades = pd.read_csv(RAW_PATH, low_memory=False)
    # Mixed date-string formats in this file: the checkpoint/resume
    # mechanism round-tripped some rows' entry_date/exit_date through a
    # CSV write+reread mid-run (data/backtest_results_run4_calibrated_model_checkpoint.csv),
    # which serializes a Timestamp with its time component ("... 00:00:00")
    # -- rows generated after the last checkpoint don't have that
    # round-trip and stay as plain "YYYY-MM-DD" strings. Same underlying
    # dates either way, just two string shapes. Converting BOTH columns
    # here (not just entry_date) so build_episodes()'s own internal
    # pd.to_datetime(exit_date) call below receives an already-Timestamp
    # column (a no-op) instead of hitting the same mixed-format error.
    trades["entry_date"] = pd.to_datetime(trades["entry_date"], format="mixed")
    trades["exit_date"] = pd.to_datetime(trades["exit_date"], format="mixed")
    print(f"Raw signals: {len(trades)}")

    episodes = build_episodes(trades)
    print(f"Episodes after absorption: {len(episodes)}")

    # make_unified_scaling_policy's RR-floor branch needs caps_applied,
    # which episode_builder.py's own schema doesn't carry -- re-attach it
    # via the founder-row merge, same technique run3_portfolio_simulation.py
    # and choke_point_decomposition.py both use.
    founder_fields = trades[["ticker", "entry_date", "caps_applied"]].rename(
        columns={"entry_date": "episode_start_date"}
    )
    episodes = episodes.merge(founder_fields, on=["ticker", "episode_start_date"], how="left")

    START_DATE = episodes["episode_start_date"].min()
    END_DATE = episodes["episode_end_date"].max()
    print(f"Window: {START_DATE.date()} -> {END_DATE.date()}")

    hard_cap_result = simulate_portfolio(
        episodes, policy_hard_cap, n_slots=N_SLOTS, base_risk_pct=BASE_RISK_PCT, starting_equity=STARTING_EQUITY,
    )
    monitor_half_result = simulate_portfolio(
        episodes, make_unified_scaling_policy(0.5), n_slots=N_SLOTS, base_risk_pct=BASE_RISK_PCT, starting_equity=STARTING_EQUITY,
    )

    hard_cap_summary = _summarize(hard_cap_result)
    monitor_half_summary = _summarize(monitor_half_result)

    benchmark_history = get_benchmark_history()
    benchmark_history["Date"] = pd.to_datetime(
        benchmark_history["Date"] if "Date" in benchmark_history.columns else benchmark_history.index
    ).dt.tz_localize(None)
    nifty = nifty_buy_hold(benchmark_history, START_DATE, END_DATE)

    print("\n" + "=" * 100)
    print("  RUN #4 -- NEW PRODUCTION categorize() (calibrated model, no regime/sector ceiling) vs NIFTY")
    print(f"  Window: {START_DATE.date()} -> {END_DATE.date()}")
    print("=" * 100)
    header = f"{'metric':<26}{'Falcon (EXECUTE-only)':<24}{'Falcon (MONITOR@0.5)*':<24}{'NIFTY buy-hold':<16}"
    print(header)
    print("-" * len(header))
    print(f"{'Total return':<26}{str(hard_cap_summary['total_return_pct'])+'%':<24}"
          f"{str(monitor_half_summary['total_return_pct'])+'%':<24}{str(nifty['total_return_pct'])+'%':<16}")
    print(f"{'Max drawdown':<26}{str(hard_cap_summary['max_drawdown_pct'])+'%':<24}"
          f"{str(monitor_half_summary['max_drawdown_pct'])+'%':<24}{str(nifty['max_drawdown_pct'])+'%':<16}")
    print(f"{'Calmar':<26}{hard_cap_summary['calmar']:<24}{monitor_half_summary['calmar']:<24}{nifty['calmar']:<16}")
    print(f"{'Episodes taken':<26}{hard_cap_summary['n_taken']:<24}{monitor_half_summary['n_taken']:<24}{'--':<16}")
    print(f"{'Missed (slot exhaustion)':<26}{hard_cap_summary['n_missed_due_to_slots']:<24}"
          f"{monitor_half_summary['n_missed_due_to_slots']:<24}{'--':<16}")
    print(f"{'Slot utilization':<26}{str(hard_cap_summary['slot_utilization_pct'])+'%':<24}"
          f"{str(monitor_half_summary['slot_utilization_pct'])+'%':<24}{'--':<16}")
    print("\n* MONITOR@0.5 reapplied literally for continuity with run #3's own methodology -- its internal"
          "\n  regime/sector-ceiling reasoning no longer reflects why a row is ALERT_WATCHLIST under the new"
          "\n  categorize() (the calibrated model's predicted_p does). Not a meaningfully-reasoned policy here.")

    comparison = pd.DataFrame([
        {"strategy": "Falcon run #4 (EXECUTE-only, new production categorize())", **hard_cap_summary},
        {"strategy": "Falcon run #4 (MONITOR@0.5, reapplied literally)", **monitor_half_summary},
        {"strategy": "NIFTY buy-and-hold", "total_return_pct": nifty["total_return_pct"],
         "max_drawdown_pct": nifty["max_drawdown_pct"], "cagr_pct": nifty["cagr_pct"], "calmar": nifty["calmar"],
         "n_taken": None, "n_missed_due_to_slots": None, "slot_utilization_pct": None},
    ])
    comparison.to_csv("data/run4_portfolio_vs_nifty.csv", index=False)
    print(f"\nSaved -> data/run4_portfolio_vs_nifty.csv")


if __name__ == "__main__":
    main()
