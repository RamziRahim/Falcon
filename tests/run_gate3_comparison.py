"""
Falcon — Gate 3: Hand-Set Thresholds vs. Calibrated Model (validation split)
Run from project root: python tests/run_gate3_comparison.py

The adopt/reject decision this whole Phase 4 arc has been building
toward: does decision_engine/leadership_decision_engine.py's hand-picked
confidence_score cutoffs (score < 40 -> AVOID / score >= 65 -> EXECUTE /
else -> ALERT_WATCHLIST) outperform, on the held-out validation split,
the spec-complete calibrated model's Reading A threshold
(tests/run_v2_thresholds.py: predicted win probability >= 0.6527)?

-------------------------------------------------------------------------
Scope: candidate pool is held fixed
-------------------------------------------------------------------------
The calibrated model (RS_Rating, macd_signal, the 9 v2 features) was only
ever backfilled onto the 265-row fitting set (real EXECUTE/ALERT_WATCHLIST
episodes with sufficient history) -- it was never scored against MONITOR/
AVOID rows, so it cannot discover a candidate the hand-set rule never
surfaced in the first place. A fair test therefore holds the CANDIDATE
POOL fixed at the 96-row validation-split fitting set, and asks only:
"of the episodes the hand-set rule already surfaced as real trades, which
of the two selection rules -- score>=65, or calibrated p>=0.6527 -- picks
the better-performing subset?" Comparing the calibrated rule against a
wider hand-set pool (e.g. every validation-split row regardless of
category) would stack the deck against the calibrated rule for a reason
that has nothing to do with which rule is better, so that comparison is
deliberately NOT run here.

Both selection rules are run through the identical policy shape (full
size if selected, zero otherwise) and the identical portfolio-simulator
mechanics (n_slots=5, base_risk_pct=1.0, starting_equity=100.0 -- same
parameters as every other headline Falcon number in this project,
including run #3's own MONITOR@0.5 vs. NIFTY comparison) so the only
thing that differs between the two runs is the selection rule itself.
"""
import sys
sys.path.insert(0, ".")

import pandas as pd

from backtesting.baselines import nifty_buy_hold
from backtesting.portfolio_simulator import simulate_portfolio
from scoring.benchmark import get_benchmark_history

EPISODE_LOG_PATH = "data/run3_episodes_with_v2_features.csv"
TIERS_PATH = "data/v2_threshold_tiers.csv"
N_SLOTS = 5
BASE_RISK_PCT = 1.0
STARTING_EQUITY = 100.0


def _policy_hand_set_production(episode: pd.Series) -> float:
    """The full, actual current-production rule: score>=65 AND the
    regime/sector ceiling (get_ceiling() in leadership_decision_engine.py)
    -- i.e. literally category == "EXECUTE", the same test policy_hard_cap
    already encodes."""
    return 1.0 if episode["category"] == "EXECUTE" else 0.0


def _policy_hand_set_score_only(episode: pd.Series) -> float:
    """The raw 40/65 SCORE cutoff alone, with the regime/sector ceiling
    disabled -- i.e. what the confidence_score threshold by itself would
    have selected before get_ceiling() ever downgrades it. Reported
    alongside the full-production policy above because the validation
    split's market regime was CAUTION/UNFAVORABLE on all 96/96 rows (zero
    FAVORABLE days), which makes the full-production policy select ZERO
    episodes regardless of score -- collapsing "hand-set score cutoffs"
    and "hand-set score cutoffs conditioned on a regime ceiling that never
    once lifted" into one number would hide which of the two is actually
    driving the comparison."""
    return 1.0 if episode["confidence_score"] >= 65.0 else 0.0


def _policy_calibrated(episode: pd.Series) -> float:
    return 1.0 if episode["tier_reading_a_adopted"] == "EXECUTE" else 0.0


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
    log = pd.read_csv(EPISODE_LOG_PATH, low_memory=False)
    log["episode_start_date"] = pd.to_datetime(log["episode_start_date"])
    log["episode_end_date"] = pd.to_datetime(log["episode_end_date"])

    tiers = pd.read_csv(TIERS_PATH, low_memory=False)
    tiers["episode_start_date"] = pd.to_datetime(tiers["episode_start_date"])
    validation_tiers = tiers[tiers["split"] == "validation"][["episode_start_date", "ticker", "tier_reading_a_adopted"]]

    # Candidate pool: the exact 96 validation-split fitting-set rows --
    # inner join so a row without a calibrated tier (shouldn't happen,
    # coverage was 265/265) is excluded rather than silently treated as
    # not-EXECUTE under the calibrated rule.
    candidates = log.merge(validation_tiers, on=["episode_start_date", "ticker"], how="inner")
    print(f"Validation-split candidate pool: {len(candidates)} rows "
          f"(window {candidates['episode_start_date'].min().date()} -> {candidates['episode_start_date'].max().date()})")

    n_hand_set_production = (candidates["category"] == "EXECUTE").sum()
    n_hand_set_score_only = (candidates["confidence_score"] >= 65.0).sum()
    n_calibrated_execute = (candidates["tier_reading_a_adopted"] == "EXECUTE").sum()
    n_favorable_regime = (candidates["market_regime_verdict"] == "FAVORABLE").sum()
    print(f"Hand-set FULL PRODUCTION rule (score>=65 + regime/sector ceiling) selects EXECUTE for "
          f"{n_hand_set_production}/{len(candidates)} candidates")
    print(f"Hand-set SCORE-ONLY rule (score>=65, ceiling ignored) selects EXECUTE for "
          f"{n_hand_set_score_only}/{len(candidates)} candidates")
    print(f"Calibrated rule (Reading A) selects EXECUTE for {n_calibrated_execute}/{len(candidates)} candidates")
    print(f"Validation-split rows with market_regime_verdict == FAVORABLE: {n_favorable_regime}/{len(candidates)} "
          f"(this is why the full-production rule collapses to 0 -- CAUTION/UNFAVORABLE for the entire window)")

    hand_set_production_result = simulate_portfolio(
        candidates, _policy_hand_set_production, n_slots=N_SLOTS, base_risk_pct=BASE_RISK_PCT, starting_equity=STARTING_EQUITY,
    )
    hand_set_score_only_result = simulate_portfolio(
        candidates, _policy_hand_set_score_only, n_slots=N_SLOTS, base_risk_pct=BASE_RISK_PCT, starting_equity=STARTING_EQUITY,
    )
    calibrated_result = simulate_portfolio(
        candidates, _policy_calibrated, n_slots=N_SLOTS, base_risk_pct=BASE_RISK_PCT, starting_equity=STARTING_EQUITY,
    )

    hand_set_production_summary = _summarize(hand_set_production_result)
    hand_set_score_only_summary = _summarize(hand_set_score_only_result)
    calibrated_summary = _summarize(calibrated_result)

    benchmark_history = get_benchmark_history()
    benchmark_history["Date"] = pd.to_datetime(
        benchmark_history["Date"] if "Date" in benchmark_history.columns else benchmark_history.index
    ).dt.tz_localize(None)
    nifty = nifty_buy_hold(benchmark_history, candidates["episode_start_date"].min(), candidates["episode_end_date"].max())

    rows = [
        ("Hand-set FULL PRODUCTION (category==EXECUTE)", hand_set_production_summary),
        ("Hand-set SCORE-ONLY (score>=65, no ceiling)", hand_set_score_only_summary),
        ("Calibrated (Reading A, p>=0.6527)", calibrated_summary),
    ]

    print("\n" + "=" * 100)
    print("  GATE 3 -- HAND-SET vs. CALIBRATED -- VALIDATION SPLIT")
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
    print(f"{'Slot util.':<14}{str(hand_set_production_summary['slot_utilization_pct']) + '%':<24}"
          f"{str(hand_set_score_only_summary['slot_utilization_pct']) + '%':<24}"
          f"{str(calibrated_summary['slot_utilization_pct']) + '%':<24}{'--':<14}")

    comparison = pd.DataFrame([
        {"strategy": "Hand-set FULL PRODUCTION (category==EXECUTE)", **hand_set_production_summary},
        {"strategy": "Hand-set SCORE-ONLY (score>=65, no ceiling)", **hand_set_score_only_summary},
        {"strategy": "Calibrated (Reading A, p>=0.6527)", **calibrated_summary},
        {"strategy": "NIFTY buy-and-hold", "total_return_pct": nifty["total_return_pct"],
         "max_drawdown_pct": nifty["max_drawdown_pct"], "cagr_pct": nifty["cagr_pct"], "calmar": nifty["calmar"],
         "n_taken": None, "n_missed_due_to_slots": None, "slot_utilization_pct": None},
    ])
    comparison.to_csv("data/gate3_comparison.csv", index=False)
    print(f"\nSaved -> data/gate3_comparison.csv")


if __name__ == "__main__":
    main()
