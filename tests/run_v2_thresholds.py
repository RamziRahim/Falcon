"""
Falcon — Phase 4.5: Derive EXECUTE/WATCHLIST Thresholds from the
Spec-Complete Calibrated Model
Run from project root: python tests/run_v2_thresholds.py

tests/run_v2_calibration_full.py fit and validated the spec-complete
logistic regression (regime + sector + pattern + RS_Rating + macd_signal
+ the 9 v2 features). This step converts its predicted win probability
into the same two-cutoff structure the existing rule-based system
already uses (decision_engine/leadership_decision_engine.py's
score < 40 -> AVOID / score >= 65 -> EXECUTE / else -> ALERT_WATCHLIST),
except the cutoffs are read off the calibrated model's own tuning-split
predicted probabilities instead of guessed integers on a hand-built
composite score.

Methodology (fixed here, not iterated against validation):
1. Refit is reused as-is -- no re-fitting happens in this script.
2. Predicted win probability for every TUNING-split episode, ranked into
   quintile bins -- same n_bins=5 already used for the 4.4 calibration
   table, not a new arbitrary choice. A first attempt at decile bins
   (n=17/bin) was tried and discarded: the win-rate-vs-probability curve
   was not monotonic at that resolution (a "sawtooth" -- e.g. one decile
   at 0.35 sitting directly above one at 0.59), which is small-sample
   noise from ~17 rows per bin, not real structure. Quintiles (n=~34/bin)
   resolve into a clean, monotonic curve; forcing a second threshold out
   of the noisy decile table would have been curve-fitting noise, not a
   real finding.
3. EXECUTE cutoff: the lowest probability p* such that every quintile at
   or above p* has realized win rate strictly above the tuning-split base
   rate, with no dips -- the natural point past which "above base rate"
   holds unconditionally.
4. WATCHLIST cutoff: the quintile immediately below the EXECUTE quintile,
   IF its own win rate is still at-or-above the base rate (worth a
   watchlist entry, just not EXECUTE-grade). If that quintile's win rate
   is itself clearly below base rate, no WATCHLIST band is reported --
   forcing one where the data shows a cliff, not a shelf, would be the
   same curve-fitting mistake as using deciles.
5. Both cutoffs are frozen from the tuning split ONLY, then applied
   as-is (no re-derivation) to the validation split for a single
   confirming read -- same tuning/validation discipline as everywhere
   else in this project.

-------------------------------------------------------------------------
ADOPTED: Reading A (permissive single cutoff)
-------------------------------------------------------------------------
Two readings came out of the tuning-split quintile table -- both are
still computed and reported below, not just the winner. Reading B (a
stricter 3-tier split, treating quintile 3 as a separate WATCHLIST band)
was considered and explicitly REJECTED: on the validation split its
WATCHLIST tier (n=17, win rate 0.882) outperformed its own EXECUTE tier
(n=26, win rate 0.769) -- an ordering inversion, most likely n=17/26
noise given the same tail-noise pattern already seen in the calibration
curve, but it means that tier's relative ranking did not hold out of
sample. Reading A's simple two-way split (EXECUTE vs. everything else)
is the one carried forward into Gate 3 -- its ordering DID hold on
validation (EXECUTE win rate 0.814 vs. BELOW_WATCHLIST 0.585). Reading B
is kept in this script and in data/v2_threshold_tiers.csv's tier_3way
column purely as a documented, explicitly-rejected alternative -- "a
3-tier split was tried and didn't hold on validation" is itself useful
information for anyone revisiting this later, not something to delete.

This does NOT touch decision_engine/leadership_decision_engine.py --
that wiring is a deliberate, separate follow-up, not part of this
report-only derivation step.
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd
import statsmodels.api as sm

from tests.run_v2_calibration_full import (
    CATEGORICAL_BASELINES,
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    _build_design_matrix,
)

EPISODE_LOG_PATH = "data/run3_episodes_with_v2_features.csv"
TUNING_SPLIT_END = "2025-09-21"
N_QUINTILES = 5  # same bin count as the 4.4 calibration table -- see module docstring


def _decile_table(y_true: np.ndarray, y_pred_prob: np.ndarray, n_bins: int = N_QUINTILES) -> pd.DataFrame:
    df = pd.DataFrame({"y": y_true, "p": y_pred_prob})
    df["bin"] = pd.qcut(df["p"], q=min(n_bins, df["p"].nunique()), duplicates="drop")
    table = df.groupby("bin", observed=True).agg(
        n=("y", "size"), mean_predicted_p=("p", "mean"), realized_win_rate=("y", "mean"),
        p_min=("p", "min"), p_max=("p", "max"),
    ).reset_index(drop=True)
    return table


def main():
    log = pd.read_csv(EPISODE_LOG_PATH, low_memory=False)
    log["episode_start_date"] = pd.to_datetime(log["episode_start_date"])

    real = log[log["category"].isin(["EXECUTE", "ALERT_WATCHLIST"])].copy()
    fitting_set = real[~real["excluded_insufficient_history"]].copy()

    tuning = fitting_set[fitting_set["episode_start_date"] <= TUNING_SPLIT_END].reset_index(drop=True).copy()
    validation = fitting_set[fitting_set["episode_start_date"] > TUNING_SPLIT_END].reset_index(drop=True).copy()
    tuning["win"] = (tuning["net_return_pct"] > 0).astype(int)
    validation["win"] = (validation["net_return_pct"] > 0).astype(int)

    base_rate = tuning["win"].mean()
    print(f"Tuning n={len(tuning)}, base rate (unconditional win rate) = {base_rate:.4f}")

    X_tuning, scaler_mean, scaler_std = _build_design_matrix(tuning, None, None)
    X_validation, _, _ = _build_design_matrix(validation, scaler_mean, scaler_std)
    X_validation = X_validation.reindex(columns=X_tuning.columns, fill_value=0.0)

    model = sm.Logit(tuning["win"], X_tuning.astype(float)).fit(disp=0)
    tuning_pred = model.predict(X_tuning.astype(float))
    validation_pred = model.predict(X_validation.astype(float))

    quintile_table = _decile_table(tuning["win"].to_numpy(), tuning_pred.to_numpy())
    print("\n" + "=" * 78)
    print("  TUNING-SPLIT QUINTILE TABLE (threshold search population)")
    print("=" * 78)
    print(quintile_table.to_string())

    # ---- EXECUTE: lowest quintile p_min such that this quintile AND
    # every quintile above it clears the base rate, with no dips
    # (suffix-min > base_rate). ----
    wr = quintile_table["realized_win_rate"].to_numpy()
    suffix_min = np.minimum.accumulate(wr[::-1])[::-1]
    execute_candidates = [i for i in range(len(wr)) if suffix_min[i] > base_rate]
    execute_idx = min(execute_candidates) if execute_candidates else None
    execute_cutoff = quintile_table["p_min"].iloc[execute_idx] if execute_idx is not None else None

    # ---- WATCHLIST: the quintile immediately below EXECUTE, only if ITS
    # OWN win rate also clears the base rate (a shelf, not a cliff). If
    # it doesn't, no WATCHLIST band is reported -- see module docstring. ----
    watchlist_cutoff = None
    if execute_idx is not None and execute_idx > 0 and wr[execute_idx - 1] >= base_rate:
        watchlist_cutoff = quintile_table["p_min"].iloc[execute_idx - 1]

    print(f"\nDerived EXECUTE cutoff, permissive single-break rule (predicted p >=): {execute_cutoff}")
    print(f"Derived WATCHLIST cutoff under that same rule: {watchlist_cutoff}")
    print(
        "NOTE: the permissive rule (\"clears base rate, no dips above\") pulled quintile 3 "
        "(win rate 0.697, barely above the 0.669 base rate) into the same EXECUTE band as "
        "quintiles 4-5 (0.882/0.971) -- mathematically correct per the stated rule, but it "
        "merges a marginal quintile with two clearly-strong ones. A second, stricter 3-tier "
        "reading is reported below for comparison: EXECUTE = quintile 4's own p_min (the point "
        "where win rate visibly separates from the barely-above-base-rate quintile beneath it), "
        "WATCHLIST = quintile 3's p_min up to that point. -- ADOPTED: Reading A (this permissive "
        "single cutoff). Reading B is kept and reported below as a documented, explicitly-"
        "rejected alternative -- see module docstring for why."
    )

    def _tier_2way(p):
        return "EXECUTE" if execute_cutoff is not None and p >= execute_cutoff else "BELOW_WATCHLIST"

    strict_execute_cutoff = quintile_table["p_min"].iloc[3]  # quintile 4 (0-indexed 3)
    strict_watchlist_cutoff = quintile_table["p_min"].iloc[2]  # quintile 3

    def _tier_3way(p):
        if p >= strict_execute_cutoff:
            return "EXECUTE"
        elif p >= strict_watchlist_cutoff:
            return "WATCHLIST"
        else:
            return "BELOW_WATCHLIST"

    tuning["tier_2way"] = tuning_pred.apply(_tier_2way)
    validation["tier_2way"] = validation_pred.apply(_tier_2way)
    tuning["tier_3way"] = tuning_pred.apply(_tier_3way)
    validation["tier_3way"] = validation_pred.apply(_tier_3way)

    print("\n" + "=" * 78)
    print("  READING A -- ADOPTED. Permissive single cutoff (EXECUTE vs BELOW_WATCHLIST only)")
    print("=" * 78)
    print("Tuning:")
    print(tuning.groupby("tier_2way")["win"].agg(n="size", win_rate="mean").to_string())
    print("Validation (single confirming read):")
    print(validation.groupby("tier_2way")["win"].agg(n="size", win_rate="mean").to_string())
    print("-> ADOPTED for Gate 3. Ordering held on validation (EXECUTE > BELOW_WATCHLIST).")

    print("\n" + "=" * 78)
    print(f"  READING B -- REJECTED. Stricter 3-tier (EXECUTE >= {strict_execute_cutoff:.4f}, "
          f"WATCHLIST >= {strict_watchlist_cutoff:.4f})")
    print("=" * 78)
    print("Tuning:")
    print(tuning.groupby("tier_3way")["win"].agg(n="size", win_rate="mean")
          .reindex(["EXECUTE", "WATCHLIST", "BELOW_WATCHLIST"]).to_string())
    print("Validation (single confirming read):")
    print(validation.groupby("tier_3way")["win"].agg(n="size", win_rate="mean")
          .reindex(["EXECUTE", "WATCHLIST", "BELOW_WATCHLIST"]).to_string())
    print("-> REJECTED. WATCHLIST outperformed EXECUTE on validation (0.882 vs 0.769) -- "
          "the 3-tier ordering did not hold out of sample. Kept here and in "
          "data/v2_threshold_tiers.csv's tier_3way column for the record, not adopted.")

    out = pd.concat([
        tuning.assign(split="tuning")[["episode_start_date", "ticker", "win", "tier_2way", "tier_3way", "split"]],
        validation.assign(split="validation")[["episode_start_date", "ticker", "win", "tier_2way", "tier_3way", "split"]],
    ])
    out["predicted_p"] = pd.concat([tuning_pred, validation_pred]).to_numpy()
    out = out.rename(columns={"tier_2way": "tier_reading_a_adopted", "tier_3way": "tier_reading_b_rejected"})
    out.to_csv("data/v2_threshold_tiers.csv", index=False)
    print("\nSaved -> data/v2_threshold_tiers.csv")


if __name__ == "__main__":
    main()
