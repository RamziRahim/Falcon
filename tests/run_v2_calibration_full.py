"""
Falcon — Phase 4.4 (complete): Refit the v2 Logistic Regression with
RS_Rating + MACD as Real Controls
Run from project root: python tests/run_v2_calibration_full.py

tests/run_v2_calibration.py fit regime + sector + pattern + the 9 v2
consolidation/RS-line features only, explicitly flagging RS_Rating and
MACD signal state as a known gap relative to docs/FALCON_V2_REDESIGN.md
section 5 ("these features + regime + sector + RS + MACD"). That gap is
now closed: tests/backfill_rs_macd.py persisted RS_Rating (via
build_scored_universe_as_of(), the same function the live replay itself
calls) and macd_signal (via
technical_analysis.pattern_system.macd_signal.get_macd_signal()) onto
every fitting-set episode, point-in-time truncated to entry date, same
discipline as everywhere else in this project.

This script re-fits on the now spec-complete feature set: regime +
sector + pattern_used + RS_Rating + macd_signal + the 9 v2 features.
Same tuning/validation split, same standardization discipline (fit on
tuning only), same excluded_insufficient_history exclusion, same
"evaluate once on validation" discipline as the first-pass fit. Outputs
are written to separate files (not overwriting the incomplete model's
own artifacts) so the two can be compared side by side.
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd
import statsmodels.api as sm

EPISODE_LOG_PATH = "data/run3_episodes_with_v2_features.csv"
TUNING_SPLIT_END = "2025-09-21"

NUMERIC_FEATURES = [
    "prior_trend_pct_gain", "prior_trend_slope", "base_depth_pct", "base_length_bars",
    "contraction_slope", "volume_dryup_ratio", "volume_down_up_ratio",
    "pivot_proximity", "breakout_volume_ratio", "dist_52w_high",
    "RS_Rating",
]
CATEGORICAL_FEATURES = ["market_regime_verdict", "sector_health_verdict", "pattern_used", "macd_signal"]
# Baselines dropped so the design matrix isn't rank-deficient (the
# "dummy variable trap"). macd_signal's baseline is NEUTRAL -- the same
# "ordinary/no-signal" logic as the other categoricals' baselines below,
# and matches the fitting set's own composition (BULLISH_ALIGNMENT/
# NEUTRAL only; BEARISH_DIVERGENCE never appears in this fitting set,
# which makes sense for a breakout-buying system).
CATEGORICAL_BASELINES = {
    "market_regime_verdict": "CAUTION",
    "sector_health_verdict": "NEUTRAL",
    "pattern_used": "is_ascending_triangle_breakout",
    "macd_signal": "NEUTRAL",
}


def _build_design_matrix(df: pd.DataFrame, scaler_mean: pd.Series | None, scaler_std: pd.Series | None):
    """Same standardize-then-dummy-encode approach as run_v2_calibration.py's
    own _build_design_matrix() -- see that module's docstring for the full
    rationale. Duplicated rather than imported so each script's design
    matrix is self-contained and independently auditable against its own
    feature list.
    """
    numeric = df[NUMERIC_FEATURES].astype(float)
    rs_bool = df["rs_line_new_high"].astype(int).rename("rs_line_new_high")

    if scaler_mean is None:
        scaler_mean = numeric.mean()
        scaler_std = numeric.std(ddof=0).replace(0, 1.0)
    numeric_std = (numeric - scaler_mean) / scaler_std

    dummies = []
    for col in CATEGORICAL_FEATURES:
        d = pd.get_dummies(df[col], prefix=col, drop_first=False, dtype=float)
        baseline_col = f"{col}_{CATEGORICAL_BASELINES[col]}"
        if baseline_col in d.columns:
            d = d.drop(columns=[baseline_col])
        dummies.append(d)

    X = pd.concat([numeric_std.reset_index(drop=True), rs_bool.reset_index(drop=True)]
                  + [d.reset_index(drop=True) for d in dummies], axis=1)
    X = sm.add_constant(X, has_constant="add")
    return X, scaler_mean, scaler_std


def _calibration_table(y_true: np.ndarray, y_pred_prob: np.ndarray, n_bins: int = 5) -> pd.DataFrame:
    df = pd.DataFrame({"y": y_true, "p": y_pred_prob})
    df["bin"] = pd.qcut(df["p"], q=min(n_bins, df["p"].nunique()), duplicates="drop")
    table = df.groupby("bin", observed=True).agg(
        n=("y", "size"), mean_predicted_p=("p", "mean"), realized_win_rate=("y", "mean"),
    ).reset_index()
    return table


def main():
    log = pd.read_csv(EPISODE_LOG_PATH, low_memory=False)
    log["episode_start_date"] = pd.to_datetime(log["episode_start_date"])

    real = log[log["category"].isin(["EXECUTE", "ALERT_WATCHLIST"])].copy()
    fitting_set = real[~real["excluded_insufficient_history"]].copy()
    print(f"Real episodes: {len(real)}  |  excluded (insufficient history): "
          f"{real['excluded_insufficient_history'].sum()}  |  fitting-set: {len(fitting_set)}")

    missing_rs_macd = fitting_set["RS_Rating"].isna() | fitting_set["macd_signal"].isna()
    if missing_rs_macd.any():
        print(f"WARNING: {missing_rs_macd.sum()} fitting-set rows missing RS_Rating/macd_signal -- dropping "
              f"(should be 0; backfill reported 265/265 coverage).")
        fitting_set = fitting_set[~missing_rs_macd].copy()

    tuning = fitting_set[fitting_set["episode_start_date"] <= TUNING_SPLIT_END].reset_index(drop=True).copy()
    validation = fitting_set[fitting_set["episode_start_date"] > TUNING_SPLIT_END].reset_index(drop=True).copy()
    print(f"Tuning split (fitting): {len(tuning)}  |  Validation split (evaluated once): {len(validation)}")

    tuning["win"] = (tuning["net_return_pct"] > 0).astype(int)
    validation["win"] = (validation["net_return_pct"] > 0).astype(int)

    X_tuning, scaler_mean, scaler_std = _build_design_matrix(tuning, None, None)
    X_validation, _, _ = _build_design_matrix(validation, scaler_mean, scaler_std)
    X_validation = X_validation.reindex(columns=X_tuning.columns, fill_value=0.0)

    model = sm.Logit(tuning["win"], X_tuning.astype(float)).fit(disp=0)

    print("\n" + "=" * 78)
    print("  LOGISTIC REGRESSION -- TUNING SPLIT FIT (spec-complete: + RS_Rating + macd_signal)")
    print(f"  n = {len(tuning)}, {X_tuning.shape[1]} parameters (incl. intercept) "
          f"-- {len(tuning) / X_tuning.shape[1]:.1f} observations per parameter")
    print("=" * 78)
    print(model.summary2().tables[1].to_string())

    predicted_prob = model.predict(X_validation.astype(float))
    calibration = _calibration_table(validation["win"].to_numpy(), predicted_prob.to_numpy())

    print("\n" + "=" * 78)
    print(f"  CALIBRATION -- VALIDATION SPLIT (n={len(validation)}, evaluated once)")
    print("=" * 78)
    print(calibration.to_string(index=False))

    pseudo_r2 = model.prsquared
    print(f"\nMcFadden's pseudo R^2 (tuning fit, complete model): {pseudo_r2:.4f}")
    print("McFadden's pseudo R^2 (tuning fit, incomplete model, for reference): 0.2113")

    base_depth_row = model.summary2().tables[1].loc["base_depth_pct"]
    print(f"\nbase_depth_pct in the complete model: coef={base_depth_row['Coef.']:.4f}, "
          f"p={base_depth_row['P>|z|']:.4f}")

    model.summary2().tables[1].to_csv("data/v2_calibration_full_coefficients.csv")
    calibration.to_csv("data/v2_calibration_full_curve.csv", index=False)
    print("\nSaved -> data/v2_calibration_full_coefficients.csv, data/v2_calibration_full_curve.csv")


if __name__ == "__main__":
    main()
