"""
Tests for scoring/consolidation_quality_model.py -- the shared predict-one-
candidate function for the v2 consolidation-quality model.

Two kinds of coverage, deliberately kept separate:
1. Hand-computed unit tests against a small FIXTURE artifact (not the real
   one) -- verifies standardization + dummy-encoding + sigmoid match an
   independently hand-derived expected probability, not just "runs
   without error." Uses math.exp directly rather than re-deriving the
   formula the function itself uses, so a bug shared between the test and
   the implementation can't hide.
2. A round-trip test against the REAL artifact (models/consolidation_quality_v1.json)
   -- proves the frozen artifact actually freezes what Gate 3 validated by
   reproducing a handful of its own recorded validation-split predicted_p
   values from raw feature data, not just re-checking internal consistency.
"""
import sys
sys.path.insert(0, ".")

import math

import pandas as pd
import pytest

from scoring.consolidation_quality_model import load_model_artifact, predict_consolidation_quality


@pytest.fixture
def fixture_artifact():
    return {
        "numeric_features": ["feat_a"],
        "categorical_features": ["regime"],
        "boolean_features": ["flag"],
        "categorical_baselines": {"regime": "BASE"},
        "scaler_mean": {"feat_a": 10.0},
        "scaler_std": {"feat_a": 2.0},
        "coefficients": {
            "const": 0.5,
            "feat_a": 1.0,
            "flag": 0.25,
            "regime_HIGH": -0.75,
        },
    }


class TestHandComputedPredictions:

    def test_non_baseline_category_dummy_fires(self, fixture_artifact):
        candidate = {"feat_a": 14.0, "flag": 1, "regime": "HIGH"}

        result = predict_consolidation_quality(candidate, fixture_artifact)

        # standardized feat_a = (14 - 10) / 2 = 2.0
        # z = 0.5 (const) + 2.0*1.0 (feat_a) + 1*0.25 (flag) + (-0.75) (regime_HIGH) = 2.0
        expected_z = 0.5 + 2.0 * 1.0 + 1 * 0.25 + (-0.75)
        expected = 1.0 / (1.0 + math.exp(-expected_z))
        assert expected == pytest.approx(0.8807970779778823, abs=1e-12)
        assert result == pytest.approx(expected, abs=1e-12)

    def test_baseline_category_contributes_zero(self, fixture_artifact):
        candidate = {"feat_a": 10.0, "flag": 0, "regime": "BASE"}

        result = predict_consolidation_quality(candidate, fixture_artifact)

        # standardized feat_a = (10 - 10) / 2 = 0.0; regime == baseline, no dummy
        expected_z = 0.5 + 0.0 * 1.0 + 0 * 0.25
        expected = 1.0 / (1.0 + math.exp(-expected_z))
        assert expected == pytest.approx(0.6224593312018546, abs=1e-12)
        assert result == pytest.approx(expected, abs=1e-12)

    def test_unseen_category_treated_same_as_baseline(self, fixture_artifact, caplog):
        """A category value with no matching dummy coefficient (never seen
        in the tuning-split fit) contributes 0, same as the real baseline
        -- same behavior as Gate 3's own X_validation.reindex(fill_value=0.0)."""
        baseline_candidate = {"feat_a": 10.0, "flag": 0, "regime": "BASE"}
        unseen_candidate = {"feat_a": 10.0, "flag": 0, "regime": "NEVER_SEEN_IN_TUNING"}

        baseline_result = predict_consolidation_quality(baseline_candidate, fixture_artifact)
        unseen_result = predict_consolidation_quality(unseen_candidate, fixture_artifact)

        assert unseen_result == pytest.approx(baseline_result, abs=1e-12)

    def test_missing_numeric_feature_raises_keyerror(self, fixture_artifact):
        """Fails closed -- a candidate missing a required raw feature value
        should never silently score as if that feature were 0/mean."""
        incomplete_candidate = {"flag": 0, "regime": "BASE"}

        with pytest.raises(KeyError):
            predict_consolidation_quality(incomplete_candidate, fixture_artifact)


class TestRoundTripAgainstGate3:
    """Proves models/consolidation_quality_v1.json actually freezes what
    Gate 3 validated: rebuilds candidate_features from raw feature columns
    for a handful of real validation-split episodes and confirms
    predict_consolidation_quality() reproduces the exact predicted_p
    already recorded in data/v2_threshold_tiers.csv (from
    tests/run_v2_thresholds.py's own model.predict() call) -- not just
    that the function runs, but that it reproduces the SAME numbers to
    floating-point precision."""

    def test_reproduces_gate3_validation_predicted_p(self):
        artifact = load_model_artifact("v1")

        tiers = pd.read_csv("data/v2_threshold_tiers.csv", low_memory=False)
        tiers["episode_start_date"] = pd.to_datetime(tiers["episode_start_date"])
        validation_rows = tiers[tiers["split"] == "validation"].head(10)

        log = pd.read_csv("data/run3_episodes_with_v2_features.csv", low_memory=False)
        log["episode_start_date"] = pd.to_datetime(log["episode_start_date"])

        checked = 0
        for _, tier_row in validation_rows.iterrows():
            match = log[
                (log["ticker"] == tier_row["ticker"])
                & (log["episode_start_date"] == tier_row["episode_start_date"])
            ]
            assert len(match) >= 1, f"No episode-log row for {tier_row['ticker']} / {tier_row['episode_start_date']}"
            episode = match.iloc[0]

            candidate_features = {feature: episode[feature] for feature in artifact["numeric_features"]}
            candidate_features["rs_line_new_high"] = int(bool(episode["rs_line_new_high"]))
            for feature in artifact["categorical_features"]:
                candidate_features[feature] = episode[feature]

            predicted_p = predict_consolidation_quality(candidate_features, artifact)

            assert predicted_p == pytest.approx(tier_row["predicted_p"], abs=1e-9), (
                f"{tier_row['ticker']} / {tier_row['episode_start_date'].date()}: "
                f"artifact predicts {predicted_p}, Gate 3 recorded {tier_row['predicted_p']}"
            )
            checked += 1

        assert checked == 10  # sanity: the loop actually ran, not silently skipped
