"""
Tests for backtesting/shadow_log.py (Gate 1 decision #2).
"""
from __future__ import annotations

import pandas as pd
import pytest

from backtesting.shadow_log import shadow_log_unfavorable_capped


def _episode(category="ALERT_WATCHLIST", confidence_score=70.0, market_regime_verdict="UNFAVORABLE",
             net_return_pct=3.0):
    return {
        "category": category, "confidence_score": confidence_score,
        "market_regime_verdict": market_regime_verdict, "net_return_pct": net_return_pct,
    }


class TestShadowLogUnfavorableCapped:

    def test_filters_to_unfavorable_capped_population_only(self):
        episodes = pd.DataFrame([
            _episode(),  # matches: ALERT_WATCHLIST, score>=65, UNFAVORABLE
            _episode(category="EXECUTE"),  # excluded: not ALERT_WATCHLIST
            _episode(confidence_score=50.0),  # excluded: genuine, not capped
            _episode(market_regime_verdict="CAUTION"),  # excluded: not UNFAVORABLE
        ])

        result = shadow_log_unfavorable_capped(episodes)

        assert len(result["episodes"]) == 1
        assert result["stats"]["sample_size"] == 1

    def test_stats_use_the_same_expectancy_math_as_the_rest_of_the_codebase(self):
        episodes = pd.DataFrame([
            _episode(net_return_pct=10.0),
            _episode(net_return_pct=-5.0),
        ])

        result = shadow_log_unfavorable_capped(episodes)

        assert result["stats"]["sample_size"] == 2
        assert result["stats"]["win_rate_pct"] == pytest.approx(50.0)

    def test_empty_population_returns_zeroed_stats_not_a_crash(self):
        episodes = pd.DataFrame([_episode(market_regime_verdict="CAUTION")])

        result = shadow_log_unfavorable_capped(episodes)

        assert result["stats"]["sample_size"] == 0
        assert result["episodes"].empty

    def test_internal_grouping_column_is_not_leaked_into_returned_episodes(self):
        episodes = pd.DataFrame([_episode()])

        result = shadow_log_unfavorable_capped(episodes)

        assert "_shadow_group" not in result["episodes"].columns
