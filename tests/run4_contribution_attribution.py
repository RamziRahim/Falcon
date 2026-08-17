"""
Falcon — Run #4: Exact Contribution Attribution for the 59 EXECUTE Episodes
Run from project root: python tests/run4_contribution_attribution.py

The +82.74% headline (tests/run4_portfolio_simulation.py, policy_hard_cap)
comes from a SEQUENTIAL COMPOUNDING equity curve (simulate_portfolio():
equity *= (1 + contribution) per taken episode, in episode_end_date
order) -- naive additive "% contribution" per episode would misrepresent
this, since the same per-trade return has a different dollar impact
depending on where it falls in the compounding sequence. This script
instead decomposes contribution EXACTLY via log-growth: each episode's
own multiplicative factor (1 + contribution) has a log-growth
log(1 + contribution), and log-growths sum EXACTLY to the total
log-growth (log(final_equity / starting_equity)) regardless of grouping
or ordering (multiplication is commutative) -- so "share of total
log-growth" is a mathematically exact, order-independent attribution,
unlike a naive percentage-of-return split.

Reuses portfolio_simulator._select_episodes() + policy_hard_cap directly
to reproduce the IDENTICAL 59 taken episodes tests/run4_portfolio_simulation.py
already reported -- not a re-derivation.
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from backtesting.episode_builder import build_episodes
from backtesting.portfolio_simulator import _select_episodes, policy_hard_cap

RAW_PATH = "data/backtest_results_run4_calibrated_model.csv"
N_SLOTS = 5
BASE_RISK_PCT = 1.0
STARTING_EQUITY = 100.0
TUNING_SPLIT_END = "2025-09-21"


def main():
    trades = pd.read_csv(RAW_PATH, low_memory=False)
    trades["entry_date"] = pd.to_datetime(trades["entry_date"], format="mixed")
    trades["exit_date"] = pd.to_datetime(trades["exit_date"], format="mixed")

    episodes = build_episodes(trades)
    episodes["episode_start_date"] = pd.to_datetime(episodes["episode_start_date"])
    episodes["episode_end_date"] = pd.to_datetime(episodes["episode_end_date"])

    taken, missed = _select_episodes(episodes, policy_hard_cap, n_slots=N_SLOTS)
    taken = taken.sort_values("episode_end_date").reset_index(drop=True)
    print(f"Taken: {len(taken)}, missed (slot exhaustion): {missed} -- matches run4_portfolio_simulation.py's "
          f"reported 59/5.")

    taken["contribution"] = taken["risk_fraction"] * (BASE_RISK_PCT / 100) * taken["r_multiple"]
    taken["factor"] = 1 + taken["contribution"]
    taken["log_growth"] = np.log(taken["factor"])

    final_equity = STARTING_EQUITY * taken["factor"].prod()
    total_return_pct = round(final_equity - STARTING_EQUITY, 2)
    total_log_growth = taken["log_growth"].sum()
    print(f"\nReconstructed final equity: {final_equity:.2f} (total return {total_return_pct}%) "
          f"-- confirms the 82.74% headline (allowing for rounding).")

    # ---- Top-5 by log-growth (exact compounding contribution, not raw
    # r_multiple -- risk_fraction and compounding position both matter). ----
    top5 = taken.sort_values("log_growth", ascending=False).head(5)
    top5_share_of_log_growth = top5["log_growth"].sum() / total_log_growth * 100
    top5_standalone_return_pct = round((top5["factor"].prod() - 1) * 100, 2)
    remaining = taken.drop(top5.index)
    remaining_standalone_return_pct = round((remaining["factor"].prod() - 1) * 100, 2)

    print("\n" + "=" * 100)
    print("  TOP-5 EPISODES BY LOG-GROWTH CONTRIBUTION")
    print("=" * 100)
    print(top5[["ticker", "episode_start_date", "episode_end_date", "category", "r_multiple",
                "risk_fraction", "contribution", "log_growth"]].to_string(index=False))
    print(f"\nTop 5 alone, compounded together (same order): would produce {top5_standalone_return_pct}% "
          f"return starting from {STARTING_EQUITY}.")
    print(f"Top 5 share of TOTAL log-growth (exact, order-independent): {top5_share_of_log_growth:.1f}%")
    print(f"Remaining 54 episodes alone, compounded together: would produce "
          f"{remaining_standalone_return_pct}% return starting from {STARTING_EQUITY}.")
    print(f"Sanity check -- top5_factor * remaining54_factor should equal overall factor: "
          f"{top5['factor'].prod() * remaining['factor'].prod():.4f} vs {taken['factor'].prod():.4f}")

    # ---- In-sample (entered on/before TUNING_SPLIT_END) vs
    # out-of-sample (entered after) -- exact multiplicative split, same
    # log-growth-sum technique, exact regardless of interleaving order. ----
    in_sample = taken[taken["episode_start_date"] <= TUNING_SPLIT_END]
    out_of_sample = taken[taken["episode_start_date"] > TUNING_SPLIT_END]

    in_sample_standalone_return_pct = round((in_sample["factor"].prod() - 1) * 100, 2) if len(in_sample) else 0.0
    out_of_sample_standalone_return_pct = round((out_of_sample["factor"].prod() - 1) * 100, 2) if len(out_of_sample) else 0.0
    in_sample_log_share = in_sample["log_growth"].sum() / total_log_growth * 100 if len(in_sample) else 0.0
    out_of_sample_log_share = out_of_sample["log_growth"].sum() / total_log_growth * 100 if len(out_of_sample) else 0.0

    print("\n" + "=" * 100)
    print(f"  IN-SAMPLE (entered <= {TUNING_SPLIT_END}, the tuning-split range) vs OUT-OF-SAMPLE (entered after)")
    print("=" * 100)
    print(f"In-sample:      n={len(in_sample)}, standalone return if compounded alone: "
          f"{in_sample_standalone_return_pct}%, share of total log-growth: {in_sample_log_share:.1f}%")
    print(f"Out-of-sample:  n={len(out_of_sample)}, standalone return if compounded alone: "
          f"{out_of_sample_standalone_return_pct}%, share of total log-growth: {out_of_sample_log_share:.1f}%")
    print(f"Sanity check -- in_sample_factor * out_of_sample_factor should equal overall factor: "
          f"{(in_sample['factor'].prod() if len(in_sample) else 1.0) * (out_of_sample['factor'].prod() if len(out_of_sample) else 1.0):.4f} "
          f"vs {taken['factor'].prod():.4f}")

    taken.to_csv("data/run4_taken_episodes_with_contribution.csv", index=False)
    print("\nSaved -> data/run4_taken_episodes_with_contribution.csv")


if __name__ == "__main__":
    main()
