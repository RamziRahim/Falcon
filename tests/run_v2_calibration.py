"""
Falcon — Phase 4.4: Fit the v2 Consolidation-Quality Logistic Regression
Run from project root: python tests/run_v2_calibration.py

Fits docs/FALCON_V2_REDESIGN.md section 5's logistic regression -- the
9 v2 consolidation/RS-line features plus regime/sector/pattern context --
on run #3's real (EXECUTE/ALERT_WATCHLIST) episodes, tuning split only,
evaluated once on the validation split. Target: did the episode win
(net_return_pct > 0), matching this codebase's own win-rate convention
(backtesting/backtest_runner.py's _group_stats()).

-------------------------------------------------------------------------
Known gap, flagged rather than silently worked around: RS_Rating and
MACD signal state are NOT included
-------------------------------------------------------------------------
The spec (section 5) calls for "these features + regime + sector + RS +
MACD". Checked directly before assuming otherwise: neither RS_Rating nor
a MACD signal state was ever persisted as its own column in
backtest_runner.py's trade_records schema (a Phase 2 design choice, made
before this v2 spec existed) -- only market_regime_verdict and
sector_health_verdict exist as ready-to-use categoricals. confidence_score
exists but is a composite that already bakes in RS_Rating's own
contribution alongside pattern points, FVG, liquidity sweep, delivery
conviction, etc. (leadership_decision_engine.compute_score()) --
including it here would reintroduce exactly the entangled-signal problem
the v2 redesign exists to move away from, not add a clean RS proxy. This
fit therefore covers regime + sector + pattern_used + the 9 v2 features
only. A proper RS_Rating/MACD backfill (mirroring Phase 4.3's own
point-in-time-truncated approach) is a real, separate follow-up -- not
done here, not silently faked with confidence_score as a substitute.

-------------------------------------------------------------------------
Exclusion discipline
-------------------------------------------------------------------------
The 13 episodes flagged insufficient-history (Phase 4.3's own finding)
are dropped from the fitting population in BOTH splits, not imputed --
excluded_insufficient_history is written back onto
data/run3_episodes_with_v2_features.csv as an explicit, auditable column
covering every episode in the log (not just the real/traded ones), so
this exclusion is never silent. This ONLY affects which rows the
regression is fit/evaluated on -- it does not touch, recompute, or
remove those 13 episodes from the actual backtest results (run #3's
raw CSV, the episode log's own return/drawdown/Calmar figures) at all.
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
]
CATEGORICAL_FEATURES = ["market_regime_verdict", "sector_health_verdict", "pattern_used"]
# Baselines dropped so the design matrix isn't rank-deficient (the
# "dummy variable trap") -- chosen as the most-common/most-neutral level
# per category, so every reported coefficient reads as "relative to the
# ordinary/base case."
CATEGORICAL_BASELINES = {
    "market_regime_verdict": "CAUTION",
    "sector_health_verdict": "NEUTRAL",
    "pattern_used": "is_ascending_triangle_breakout",
}


def _build_design_matrix(df: pd.DataFrame, scaler_mean: pd.Series | None, scaler_std: pd.Series | None):
    """Standardizes the numeric features (z-score) so coefficients are
    comparable in effect-size terms across wildly different natural
    scales (prior_trend_pct_gain in the tens, contraction_slope ~1e-4) --
    raw unstandardized coefficients would just reflect scale, not
    importance. scaler_mean/std are None when fitting on the tuning
    split itself (fit the scaler here); passed in when transforming the
    validation split, so validation never leaks into what "standardized"
    means -- same tuning/validation discipline as everywhere else in this
    project.
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
    # qcut, not cut: deciles need EQUAL-COUNT bins to be meaningful on a
    # tiny validation set, not equal-width probability bins that could
    # leave several empty.
    df["bin"] = pd.qcut(df["p"], q=min(n_bins, df["p"].nunique()), duplicates="drop")
    table = df.groupby("bin", observed=True).agg(
        n=("y", "size"), mean_predicted_p=("p", "mean"), realized_win_rate=("y", "mean"),
    ).reset_index()
    return table


def main():
    log = pd.read_csv(EPISODE_LOG_PATH, low_memory=False)
    log["episode_start_date"] = pd.to_datetime(log["episode_start_date"])

    # ---- Auditable exclusion flag, written onto the FULL episode log ----
    log["excluded_insufficient_history"] = (
        (log["dist_52w_high_invalidated_reason"] == "INSUFFICIENT_HISTORY")
        | (log["rs_line_invalidated_reason"] == "INSUFFICIENT_HISTORY")
    )
    log.to_csv(EPISODE_LOG_PATH, index=False)
    print(f"excluded_insufficient_history flag written to {EPISODE_LOG_PATH} "
          f"({log['excluded_insufficient_history'].sum()} of {len(log)} episodes flagged, all categories)")

    real = log[log["category"].isin(["EXECUTE", "ALERT_WATCHLIST"])].copy()
    fitting_set = real[~real["excluded_insufficient_history"]].copy()
    print(f"\nReal episodes: {len(real)}  |  excluded (insufficient history): "
          f"{real['excluded_insufficient_history'].sum()}  |  fitting-set: {len(fitting_set)}")

    tuning = fitting_set[fitting_set["episode_start_date"] <= TUNING_SPLIT_END].reset_index(drop=True).copy()
    validation = fitting_set[fitting_set["episode_start_date"] > TUNING_SPLIT_END].reset_index(drop=True).copy()
    print(f"Tuning split (fitting): {len(tuning)}  |  Validation split (evaluated once): {len(validation)}")

    tuning["win"] = (tuning["net_return_pct"] > 0).astype(int)
    validation["win"] = (validation["net_return_pct"] > 0).astype(int)

    X_tuning, scaler_mean, scaler_std = _build_design_matrix(tuning, None, None)
    X_validation, _, _ = _build_design_matrix(validation, scaler_mean, scaler_std)
    # Validation's own categorical dummies must align to the exact same
    # columns the model was fit on (a category level present in tuning
    # but absent in validation, or vice versa, would otherwise silently
    # misalign the design matrix).
    X_validation = X_validation.reindex(columns=X_tuning.columns, fill_value=0.0)

    model = sm.Logit(tuning["win"], X_tuning.astype(float)).fit(disp=0)

    print("\n" + "=" * 78)
    print("  LOGISTIC REGRESSION -- TUNING SPLIT FIT")
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
    print(f"\nMcFadden's pseudo R^2 (tuning fit): {pseudo_r2:.4f}")

    model.summary2().tables[1].to_csv("data/v2_calibration_coefficients.csv")
    calibration.to_csv("data/v2_calibration_curve.csv", index=False)
    print("\nSaved -> data/v2_calibration_coefficients.csv, data/v2_calibration_curve.csv")


if __name__ == "__main__":
    main()
