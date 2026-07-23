"""
Tests for backtesting/component_diagnostics.py (I-7).
"""
from __future__ import annotations

import pandas as pd
import pytest

from backtesting.component_diagnostics import (
    UNAVAILABLE_IN_RUN_1,
    _monotonicity_verdict,
    bucket_by_absorption_count,
    bucket_by_confidence_decile,
    bucket_by_ordered_column,
    run_component_diagnostics,
)


def _episode(category="ALERT_WATCHLIST", confidence_score=50.0, pattern_used=None,
             market_regime_verdict="CAUTION", sector_health_verdict="NEUTRAL",
             n_signals_absorbed=1, net_return_pct=1.0):
    return {
        "category": category, "confidence_score": confidence_score, "pattern_used": pattern_used,
        "market_regime_verdict": market_regime_verdict, "sector_health_verdict": sector_health_verdict,
        "n_signals_absorbed": n_signals_absorbed, "net_return_pct": net_return_pct,
    }


class TestMonotonicityVerdict:

    def test_strictly_increasing_sequence(self):
        assert _monotonicity_verdict([1.0, 2.0, 3.0]) == "monotonically increasing"

    def test_strictly_decreasing_sequence(self):
        assert _monotonicity_verdict([3.0, 2.0, 1.0]) == "monotonically decreasing"

    def test_flat_sequence(self):
        assert _monotonicity_verdict([2.0, 2.0, 2.0]) == "flat (no variation)"

    def test_inversion_is_not_monotonic(self):
        assert _monotonicity_verdict([1.0, 3.0, 2.0]) == "NOT monotonic (inversion present)"

    def test_fewer_than_two_points_is_not_applicable(self):
        assert _monotonicity_verdict([1.0]) == "N/A (fewer than 2 buckets present)"


class TestBucketByOrderedColumn:

    def test_monotonicity_checked_only_against_labels_actually_present(self):
        # AVOID is in a hypothetical order but never appears in the data --
        # must not count as a break in monotonicity.
        episodes = pd.DataFrame([
            _episode(category="ALERT_WATCHLIST", net_return_pct=1.0),
            _episode(category="EXECUTE", net_return_pct=3.0),
        ])

        result = bucket_by_ordered_column(episodes, "category", ["AVOID", "ALERT_WATCHLIST", "EXECUTE"])

        assert result["order_checked"] == ["ALERT_WATCHLIST", "EXECUTE"]
        assert result["monotonicity"] == "monotonically increasing"

    def test_nan_pattern_used_is_a_real_group_not_silently_dropped(self):
        # 622 of 797 real episodes have no pattern at all (pattern_used is
        # NaN) -- these must show up as their own bucket, not vanish.
        episodes = pd.DataFrame([
            _episode(pattern_used="is_vcp_breakout", net_return_pct=5.0),
            _episode(pattern_used=None, net_return_pct=1.0),
            _episode(pattern_used=None, net_return_pct=1.0),
        ])

        from backtesting.component_diagnostics import NO_PATTERN_LABEL, PATTERN_ORDER

        result = bucket_by_ordered_column(episodes, "pattern_used", PATTERN_ORDER)

        assert NO_PATTERN_LABEL in set(result["table"]["group"])
        no_pattern_row = result["table"][result["table"]["group"] == NO_PATTERN_LABEL].iloc[0]
        assert no_pattern_row["sample_size"] == 2

    def test_detects_a_real_inversion(self):
        episodes = pd.DataFrame([
            _episode(sector_health_verdict="WEAK", net_return_pct=5.0),
            _episode(sector_health_verdict="NEUTRAL", net_return_pct=1.0),
            _episode(sector_health_verdict="STRONG", net_return_pct=0.5),
        ])

        result = bucket_by_ordered_column(episodes, "sector_health_verdict", ["WEAK", "NEUTRAL", "STRONG"])

        assert result["monotonicity"] == "monotonically decreasing"


class TestBucketByConfidenceDecile:

    def test_low_confidence_bucket_before_high_confidence_bucket(self):
        rows = [_episode(confidence_score=s, net_return_pct=s / 10) for s in range(40, 100, 2)]
        episodes = pd.DataFrame(rows)

        result = bucket_by_confidence_decile(episodes, n_bins=5)

        assert result["monotonicity"] == "monotonically increasing"

    def test_duplicate_score_clusters_do_not_crash_binning(self):
        # run #1 has a real cluster of scores clamped at exactly 100.0 --
        # qcut must handle duplicate bin edges rather than raising.
        episodes = pd.DataFrame(
            [_episode(confidence_score=100.0, net_return_pct=5.0) for _ in range(20)]
            + [_episode(confidence_score=s, net_return_pct=s / 10) for s in range(40, 60, 2)]
        )

        result = bucket_by_confidence_decile(episodes, n_bins=10)

        assert not result["table"].empty


class TestBucketByAbsorptionCount:

    def test_three_or_more_collapses_into_one_bucket(self):
        episodes = pd.DataFrame([
            _episode(n_signals_absorbed=1),
            _episode(n_signals_absorbed=3),
            _episode(n_signals_absorbed=4),
        ])

        result = bucket_by_absorption_count(episodes)

        assert set(result["table"]["group"]) == {"1", "3+"}


class TestRunComponentDiagnostics:

    def test_reports_unavailable_fields_explicitly(self):
        episodes = pd.DataFrame([_episode()])

        result = run_component_diagnostics(episodes)

        assert result["unavailable_in_run_1"] == UNAVAILABLE_IN_RUN_1
        assert "RS Rating quintile" in result["unavailable_in_run_1"]
