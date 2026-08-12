"""
Falcon — Freeze the v2 Consolidation-Quality Model into a Versioned Artifact
Run from project root: python tests/build_consolidation_quality_artifact.py

Generates models/consolidation_quality_v1.json from the EXISTING,
already-validated tuning-split fit -- not a refit. This script imports
tests/run_v2_calibration_full.py's own _build_design_matrix() and reads
the identical source file (data/run3_episodes_with_v2_features.csv) with
the identical TUNING_SPLIT_END filter that script and Gate 3 both used.
Logistic regression via IRLS is deterministic given identical data and
covariates, so re-running the fit here reproduces the exact same
coefficients Gate 3 evaluated -- byte-identical, not approximately
similar -- rather than deriving a new fit from new data. The round-trip
test (tests/scoring/test_consolidation_quality_model.py) proves this by
reproducing Gate 3's own recorded predicted_p values from the artifact
this script produces.

The artifact also freezes Reading A's EXECUTE cutoff (0.6526920989878143,
tests/run_v2_thresholds.py) -- versioned together with the coefficients
it was derived from, rather than left as a separate hardcoded constant
that could silently drift out of sync with which model version is active.
"""
import sys
sys.path.insert(0, ".")

import json
from datetime import date

import pandas as pd
import statsmodels.api as sm

from tests.run_v2_calibration_full import (
    CATEGORICAL_BASELINES,
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    TUNING_SPLIT_END,
    _build_design_matrix,
)

EPISODE_LOG_PATH = "data/run3_episodes_with_v2_features.csv"
EXECUTE_CUTOFF = 0.6526920989878143  # Reading A, tests/run_v2_thresholds.py
ARTIFACT_PATH = "models/consolidation_quality_v1.json"
VERSION = "v1"


def main():
    log = pd.read_csv(EPISODE_LOG_PATH, low_memory=False)
    log["episode_start_date"] = pd.to_datetime(log["episode_start_date"])

    real = log[log["category"].isin(["EXECUTE", "ALERT_WATCHLIST"])].copy()
    fitting_set = real[~real["excluded_insufficient_history"]].copy()
    tuning = fitting_set[fitting_set["episode_start_date"] <= TUNING_SPLIT_END].reset_index(drop=True).copy()
    tuning["win"] = (tuning["net_return_pct"] > 0).astype(int)

    X_tuning, scaler_mean, scaler_std = _build_design_matrix(tuning, None, None)
    model = sm.Logit(tuning["win"], X_tuning.astype(float)).fit(disp=0)

    print(f"Refit on {len(tuning)} tuning-split rows ({tuning['episode_start_date'].min().date()} -> "
          f"{tuning['episode_start_date'].max().date()}), {X_tuning.shape[1]} parameters.")
    print(f"McFadden's pseudo R^2: {model.prsquared:.4f}")

    artifact = {
        "version": VERSION,
        "generated_date": date.today().isoformat(),
        "source": {
            "episode_log": EPISODE_LOG_PATH,
            "tuning_split_end": TUNING_SPLIT_END,
            "n_tuning_rows": len(tuning),
            "tuning_date_range": [tuning["episode_start_date"].min().date().isoformat(),
                                   tuning["episode_start_date"].max().date().isoformat()],
        },
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "categorical_baselines": CATEGORICAL_BASELINES,
        "boolean_features": ["rs_line_new_high"],
        "scaler_mean": scaler_mean.to_dict(),
        "scaler_std": scaler_std.to_dict(),
        "coefficients": model.params.to_dict(),
        "execute_cutoff": EXECUTE_CUTOFF,
        "mcfadden_pseudo_r2": round(model.prsquared, 6),
    }

    import os
    os.makedirs("models", exist_ok=True)
    with open(ARTIFACT_PATH, "w", encoding="utf-8") as fh:
        json.dump(artifact, fh, indent=2)

    print(f"\nSaved -> {ARTIFACT_PATH}")
    print(f"Coefficient columns: {list(model.params.index)}")


if __name__ == "__main__":
    main()
