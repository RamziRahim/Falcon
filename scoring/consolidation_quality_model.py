"""
===============================================================================
Falcon AI Swing Trading Platform — Consolidation-Quality Model Inference
===============================================================================
Script      : consolidation_quality_model.py
Package     : Scoring

The single shared "predict one candidate" function for the v2
consolidation-quality logistic regression (docs/FALCON_V2_REDESIGN.md
section 5), called identically from both
decision_engine/leadership_decision_engine.py's live path and
backtesting/replay_engine.py's replay path -- one implementation, not two,
so live/backtest parity for this piece is structural, not a discipline to
remember.

Reproduces, standalone-from-statsmodels, exactly what
tests/run_v2_calibration_full.py's _build_design_matrix() +
sm.Logit.predict() did at fit time: z-score the numeric features against
the artifact's own frozen scaler_mean/scaler_std, dummy-encode the
categorical features against the artifact's own frozen
categorical_baselines, take the dot product with the artifact's frozen
coefficients, and pass through the logistic sigmoid. No statsmodels
dependency at inference time -- this module only needs the frozen JSON
artifact.

A category value never seen in the tuning-split fit (e.g. macd_signal's
BEARISH_DIVERGENCE, which never appeared in the 169-row tuning
population) has no coefficient in the artifact for its own dummy column.
Treated as contributing 0 beyond the baseline -- the same behavior
Gate 3's own X_validation.reindex(columns=X_tuning.columns,
fill_value=0.0) already used when scoring the validation split, not a
new decision introduced here. Logged at INFO (not silently), since it's
worth knowing when it happens even though it's expected behavior.
===============================================================================
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from common.logger import get_logger
from config import ACTIVE_MODEL_VERSION, MODEL_ARTIFACT_DIR

logger = get_logger(__name__)


def load_model_artifact(version: str | None = None) -> dict:
    """Loads models/consolidation_quality_{version}.json. version defaults
    to config.ACTIVE_MODEL_VERSION -- the one, explicit place that decides
    which frozen model is live. Promoting a new model version means
    changing that constant in a reviewed, committed change; this function
    never picks "the newest file in the directory" or otherwise infers a
    version on its own.

    Raises FileNotFoundError (not a graceful None) if the pinned version's
    artifact is missing -- an active model version that doesn't resolve to
    a real file is a deployment error, not a "make a scoring decision
    without a model" case."""
    version = version or ACTIVE_MODEL_VERSION
    path = Path(MODEL_ARTIFACT_DIR) / f"consolidation_quality_{version}.json"

    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def predict_consolidation_quality(candidate_features: dict, artifact: dict) -> float:
    """
    Returns the model's predicted win probability for one candidate.

    Parameters
    ----------
    candidate_features : dict
        Must contain a raw (unstandardized) value for every name in
        artifact["numeric_features"] and artifact["boolean_features"], and
        a string value for every name in artifact["categorical_features"]
        (one of that feature's real category labels -- market_regime_verdict/
        sector_health_verdict/pattern_used/macd_signal). Missing numeric/
        boolean keys raise KeyError (fail closed -- a candidate this
        function can't actually score shouldn't silently get a probability
        computed from an implicit zero). Missing categorical keys are
        treated as the baseline for that category (contributes 0), same as
        a candidate genuinely at the baseline level.
    artifact : dict
        As produced by tests/build_consolidation_quality_artifact.py /
        loaded via load_model_artifact().

    Returns
    -------
    float
        Predicted probability in (0, 1).
    """
    coefficients = artifact["coefficients"]
    scaler_mean = artifact["scaler_mean"]
    scaler_std = artifact["scaler_std"]
    categorical_baselines = artifact["categorical_baselines"]

    z = coefficients["const"]

    for feature in artifact["numeric_features"]:
        raw_value = candidate_features[feature]
        standardized = (raw_value - scaler_mean[feature]) / scaler_std[feature]
        z += standardized * coefficients.get(feature, 0.0)

    for feature in artifact["boolean_features"]:
        z += float(candidate_features[feature]) * coefficients.get(feature, 0.0)

    for feature in artifact["categorical_features"]:
        value = candidate_features[feature]
        baseline = categorical_baselines[feature]

        if value == baseline:
            continue

        dummy_column = f"{feature}_{value}"

        if dummy_column not in coefficients:
            logger.info(
                "predict_consolidation_quality: %s=%r never appeared in the tuning-split fit -- "
                "treated as contributing 0 beyond the %s baseline (same as X_validation's own "
                "reindex(fill_value=0.0) behavior at Gate 3).",
                feature, value, feature,
            )
            continue

        z += coefficients[dummy_column]

    return 1.0 / (1.0 + math.exp(-z))
