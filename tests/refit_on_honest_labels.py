"""
Falcon -- pre-registered step 2: refit the consolidation-quality model on
honest (next-open fill) labels, judged on the validation half only.
Rules: docs/refit_preregistration.md (written before any refit result).

Run from the project root, after tests/run_backtest.py has produced
data/backtest_results_run5b_honest_fills_with_model_features.csv:

    python tests/refit_on_honest_labels.py

What it does, in order (nothing here is tuned by looking at validation):
  1. Checks run #5b reproduced run #5's decisions row for row.
  2. Builds episodes exactly as the v1 fit did; fitting population =
     EXECUTE + ALERT_WATCHLIST episodes whose model inputs are all present.
  3. Fits the SAME logistic specification as v1 (same features, baselines,
     standardisation) on the tuning half only (episode start <= 2025-09-21).
  4. Derives the EXECUTE cutoff with the SAME rule as v1 (Reading A,
     tests/run_v2_thresholds.py) on the tuning half only.
  5. Saves the artifact as models/consolidation_quality_v2_honest.json
     (NOT activated -- config.ACTIVE_MODEL_VERSION stays v1).
  6. Re-labels validation-half signal rows with the new model, applying the
     same reward:risk floor categorize() applies, and runs the unchanged
     pre-registered scorecard on them. A self-check first re-labels with v1
     and must reproduce run #5's own categories exactly.
"""
import sys
sys.path.insert(0, ".")

import json
import os
from datetime import date

import numpy as np
import pandas as pd
import statsmodels.api as sm

from backtesting.backtest_runner import MODEL_FEATURE_COLUMNS
from backtesting.episode_builder import build_episodes
from config import MIN_REWARD_RISK
from scoring.consolidation_quality_model import load_model_artifact, predict_consolidation_quality
from tests.evaluate_backtest_run import evaluate
from tests.run_v2_calibration_full import (
    CATEGORICAL_BASELINES,
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    TUNING_SPLIT_END,
    _build_design_matrix,
)

RUN5B_PATH = "data/backtest_results_run5b_honest_fills_with_model_features.csv"
RUN5_PATH = "data/backtest_results_run5_honest_fills.csv"
ARTIFACT_PATH = "models/consolidation_quality_v2_honest.json"
VALIDATION_RELABELLED_PATH = "data/refit_v2_validation_relabelled.csv"
N_QUINTILES = 5
SPLIT = pd.Timestamp(TUNING_SPLIT_END)
RR_CAPS = {"RR_BELOW_FLOOR", "PRICE_BEYOND_STOP"}   # only ever added to an EXECUTE decision
SIGNAL = ["EXECUTE", "ALERT_WATCHLIST"]


def _load(path):
    raw = pd.read_csv(path, low_memory=False)
    for col in ("entry_date", "exit_date", "signal_date"):
        if col in raw.columns:
            raw[col] = pd.to_datetime(raw[col], format="mixed")
    return raw


def check_reproduces_run5(raw5b):
    if not os.path.exists(RUN5_PATH):
        print("  (run #5 file not found -- reproduction check skipped)")
        return
    raw5 = _load(RUN5_PATH)
    cols = [c for c in raw5.columns if c in raw5b.columns]
    pd.testing.assert_frame_equal(raw5[cols].reset_index(drop=True), raw5b[cols].reset_index(drop=True))
    print(f"  run #5b reproduces run #5 exactly: {len(raw5)} rows, {len(cols)} shared columns")


def _features(row):
    return {name: row[f"mf_{name}"] for name in MODEL_FEATURE_COLUMNS}


def _complete(df):
    needed = [f"mf_{n}" for n in MODEL_FEATURE_COLUMNS if n != "macd_signal"]
    return df[needed].notna().all(axis=1)


def fitting_set(raw):
    episodes = build_episodes(raw)
    episodes["episode_start_date"] = pd.to_datetime(episodes["episode_start_date"])
    founders = raw.drop_duplicates(["ticker", "entry_date", "category"])
    feats = founders[["ticker", "entry_date", "category"] + [f"mf_{n}" for n in MODEL_FEATURE_COLUMNS]]
    eps = episodes.merge(
        feats.rename(columns={"entry_date": "episode_start_date"}),
        on=["ticker", "episode_start_date", "category"], how="left",
    )
    eps = eps[eps["category"].isin(SIGNAL)]
    eps = eps[_complete(eps)].copy()
    for name in MODEL_FEATURE_COLUMNS:
        eps[name] = eps[f"mf_{name}"]
    eps["macd_signal"] = eps["macd_signal"].fillna("NEUTRAL")
    eps["rs_line_new_high"] = eps["rs_line_new_high"].astype(str).str.lower().isin(["true", "1", "1.0"])
    eps["win"] = (eps["net_return_pct"] > 0).astype(int)
    return eps.reset_index(drop=True)


def reading_a_cutoff(y, p):
    """v1's rule (tests/run_v2_thresholds.py): quintiles of tuning-split
    predictions; EXECUTE cutoff = p_min of the lowest quintile such that it
    and every quintile above it beat the tuning base rate."""
    df = pd.DataFrame({"y": y, "p": p})
    df["bin"] = pd.qcut(df["p"], q=min(N_QUINTILES, df["p"].nunique()), duplicates="drop")
    table = df.groupby("bin", observed=True).agg(
        n=("y", "size"), mean_p=("p", "mean"), win_rate=("y", "mean"), p_min=("p", "min"),
    ).reset_index(drop=True)
    base = float(np.mean(y))
    wr = table["win_rate"].to_numpy()
    suffix_min = np.minimum.accumulate(wr[::-1])[::-1]
    ok = [i for i in range(len(wr)) if suffix_min[i] > base]
    cutoff = float(table["p_min"].iloc[min(ok)]) if ok else None
    return cutoff, table, base


def relabel(raw, artifact):
    """New category for each EXECUTE/ALERT_WATCHLIST row under `artifact`,
    replicating categorize(): model p >= cutoff -> EXECUTE, unless another
    cap applies or reward:risk is missing / below the floor."""
    out = raw.copy()
    sig = out["category"].isin(SIGNAL)
    new_p, new_cat = [], []
    for _, row in out[sig].iterrows():
        f = _features(row)
        p = None
        if all(pd.notna(f[n]) for n in artifact["numeric_features"] + artifact["boolean_features"]):
            vals = {n: f[n] for n in artifact["numeric_features"]}
            vals.update({n: str(f[n]).lower() in ("true", "1", "1.0") for n in artifact["boolean_features"]})
            vals.update(market_regime_verdict=row["market_regime_verdict"],
                        sector_health_verdict=row["sector_health_verdict"],
                        pattern_used=row["pattern_used"],
                        macd_signal=f["macd_signal"] if pd.notna(f["macd_signal"]) and f["macd_signal"] else "NEUTRAL")
            p = predict_consolidation_quality(vals, artifact)
        caps = set(str(row["caps_applied"]).split(",")) - {"", "nan"} if pd.notna(row["caps_applied"]) else set()
        rr = row["reward_risk"]
        execute = (
            p is not None and p >= artifact["execute_cutoff"] and not (caps - RR_CAPS)
            and pd.notna(rr) and rr >= MIN_REWARD_RISK
        )
        new_p.append(p)
        new_cat.append("EXECUTE" if execute else "ALERT_WATCHLIST")
    out.loc[sig, "category"] = new_cat
    out.loc[sig, "predicted_p_relabel"] = new_p
    return out


def main():
    print("1. Reproduction check")
    raw = _load(RUN5B_PATH)
    check_reproduces_run5(raw)

    print("\n2. Fitting population (EXECUTE + ALERT_WATCHLIST episodes with complete model inputs)")
    eps = fitting_set(raw)
    tuning = eps[eps["episode_start_date"] <= SPLIT].reset_index(drop=True)
    validation = eps[eps["episode_start_date"] > SPLIT].reset_index(drop=True)
    print(f"  tuning {len(tuning)} episodes (win rate {tuning['win'].mean():.3f}), "
          f"validation {len(validation)} episodes")

    print("\n3. Fit (same specification as v1, tuning half only)")
    X_tune, mean, std = _build_design_matrix(tuning, None, None)
    try:
        model = sm.Logit(tuning["win"], X_tune.astype(float)).fit(disp=0, maxiter=200)
        converged = bool(model.mle_retvals.get("converged", False))
    except Exception as ex:                       # singular matrix / perfect separation
        print(f"  FIT FAILED: {type(ex).__name__}: {ex}")
        print("\nVERDICT: REFIT NOT ESTIMABLE -> pre-registered outcome: step 2 FAILS")
        return
    if not converged:
        print("  FIT DID NOT CONVERGE")
        print("\nVERDICT: REFIT NOT ESTIMABLE -> pre-registered outcome: step 2 FAILS")
        return
    print(f"  {X_tune.shape[1]} parameters on {len(tuning)} rows; McFadden pseudo R^2 {model.prsquared:.3f}")

    print("\n4. EXECUTE cutoff (Reading A rule, tuning half only)")
    cutoff, table, base = reading_a_cutoff(tuning["win"].to_numpy(), model.predict(X_tune.astype(float)).to_numpy())
    print(table.to_string())
    print(f"  base rate {base:.3f} -> cutoff {cutoff}")
    if cutoff is None:
        print("\nVERDICT: NO QUINTILE BEATS THE BASE RATE -> pre-registered outcome: step 2 FAILS")
        return

    artifact = {
        "version": "v2_honest", "generated_date": date.today().isoformat(),
        "source": {"run": RUN5B_PATH, "tuning_split_end": TUNING_SPLIT_END, "n_tuning_rows": len(tuning),
                   "label": "net_return_pct > 0 under next-open fills (run #5)"},
        "numeric_features": NUMERIC_FEATURES, "categorical_features": CATEGORICAL_FEATURES,
        "categorical_baselines": CATEGORICAL_BASELINES, "boolean_features": ["rs_line_new_high"],
        "scaler_mean": mean.to_dict(), "scaler_std": std.to_dict(),
        "coefficients": model.params.to_dict(), "execute_cutoff": cutoff,
        "mcfadden_pseudo_r2": round(float(model.prsquared), 6),
    }
    with open(ARTIFACT_PATH, "w", encoding="utf-8") as fh:
        json.dump(artifact, fh, indent=2)
    print(f"  saved {ARTIFACT_PATH} (not activated)")

    print("\n5. Re-label the validation half")
    val_raw = raw[raw["entry_date"] > SPLIT].copy()
    v1_check = relabel(val_raw, load_model_artifact("v1"))
    sig = val_raw["category"].isin(SIGNAL)
    mismatch = int((v1_check.loc[sig, "category"] != val_raw.loc[sig, "category"]).sum())
    print(f"  self-check: re-labelling with v1 reproduces run #5's categories ({mismatch} mismatches)")
    if mismatch:
        raise SystemExit("Self-check failed -- the re-labelling does not replicate categorize(); stop.")
    relabelled = relabel(val_raw, artifact)
    n_exec = int((relabelled["category"] == "EXECUTE").sum())
    print(f"  EXECUTE signals in validation: v1 {int((val_raw['category'] == 'EXECUTE').sum())} -> v2_honest {n_exec}")
    relabelled.to_csv(VALIDATION_RELABELLED_PATH, index=False)
    if n_exec == 0:
        print("\nVERDICT: the refit model takes no trades in the validation half -> NO DEMONSTRATED EDGE")
        return

    print("\n6. Pre-registered scorecard, validation half only")
    report = evaluate(VALIDATION_RELABELLED_PATH)
    for key, value in report.items():
        if key != "checks":
            print(f"  {key:32s} {value}")
    print("\n  Pre-registered checks:")
    for name, ok in report["checks"].items():
        print(f"    [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\nVERDICT: {report['verdict']}")


if __name__ == "__main__":
    main()
