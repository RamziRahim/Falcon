"""
Tests for backtesting/portfolio_simulator.py (I-5).
"""
from __future__ import annotations

import pandas as pd
import pytest

from backtesting.portfolio_simulator import (
    NAMED_POLICIES,
    compare_policies,
    policy_caution_half_unfavorable_blocked,
    policy_caution_half_unfavorable_quarter,
    policy_hard_cap,
    policy_sector_aware_caution,
    simulate_portfolio,
)


def _episode(category="EXECUTE", confidence_score=80.0, market_regime_verdict="FAVORABLE",
             sector_health_verdict="STRONG", episode_start_date="2024-01-01",
             episode_end_date="2024-01-10", r_multiple=1.0):
    return {
        "category": category, "confidence_score": confidence_score,
        "market_regime_verdict": market_regime_verdict, "sector_health_verdict": sector_health_verdict,
        "episode_start_date": episode_start_date, "episode_end_date": episode_end_date,
        "r_multiple": r_multiple,
    }


class TestPolicies:

    def test_hard_cap_only_takes_execute(self):
        assert policy_hard_cap(pd.Series(_episode(category="EXECUTE"))) == 1.0
        assert policy_hard_cap(pd.Series(_episode(category="ALERT_WATCHLIST", confidence_score=90.0))) == 0.0

    def test_caution_half_takes_capped_caution_at_half_size(self):
        row = pd.Series(_episode(category="ALERT_WATCHLIST", confidence_score=70.0, market_regime_verdict="CAUTION"))
        assert policy_caution_half_unfavorable_blocked(row) == 0.5

    def test_caution_half_blocks_capped_unfavorable(self):
        row = pd.Series(_episode(category="ALERT_WATCHLIST", confidence_score=70.0, market_regime_verdict="UNFAVORABLE"))
        assert policy_caution_half_unfavorable_blocked(row) == 0.0

    def test_caution_half_blocks_genuine_low_score(self):
        row = pd.Series(_episode(category="ALERT_WATCHLIST", confidence_score=50.0, market_regime_verdict="CAUTION"))
        assert policy_caution_half_unfavorable_blocked(row) == 0.0

    def test_quarter_variant_allows_capped_unfavorable_at_quarter_size(self):
        row = pd.Series(_episode(category="ALERT_WATCHLIST", confidence_score=70.0, market_regime_verdict="UNFAVORABLE"))
        assert policy_caution_half_unfavorable_quarter(row) == 0.25

    def test_sector_aware_scales_weak_sector_down_to_quarter(self):
        row = pd.Series(_episode(
            category="ALERT_WATCHLIST", confidence_score=70.0,
            market_regime_verdict="CAUTION", sector_health_verdict="WEAK",
        ))
        assert policy_sector_aware_caution(row) == 0.25

    def test_sector_aware_keeps_neutral_sector_at_half(self):
        row = pd.Series(_episode(
            category="ALERT_WATCHLIST", confidence_score=70.0,
            market_regime_verdict="CAUTION", sector_health_verdict="NEUTRAL",
        ))
        assert policy_sector_aware_caution(row) == 0.5


class TestSlotContention:

    def test_more_candidates_than_slots_causes_misses(self):
        # 3 overlapping full-size EXECUTE episodes, only 2 slots
        episodes = pd.DataFrame([
            _episode(episode_start_date="2024-01-01", episode_end_date="2024-01-20"),
            _episode(episode_start_date="2024-01-02", episode_end_date="2024-01-20"),
            _episode(episode_start_date="2024-01-03", episode_end_date="2024-01-20"),
        ])

        result = simulate_portfolio(episodes, policy_hard_cap, n_slots=2)

        assert result["n_taken"] == 2
        assert result["n_missed_due_to_slots"] == 1

    def test_non_overlapping_episodes_all_taken_even_with_one_slot(self):
        episodes = pd.DataFrame([
            _episode(episode_start_date="2024-01-01", episode_end_date="2024-01-05"),
            _episode(episode_start_date="2024-01-10", episode_end_date="2024-01-15"),
            _episode(episode_start_date="2024-01-20", episode_end_date="2024-01-25"),
        ])

        result = simulate_portfolio(episodes, policy_hard_cap, n_slots=1)

        assert result["n_taken"] == 3
        assert result["n_missed_due_to_slots"] == 0

    def test_entry_equal_to_prior_exit_frees_the_slot(self):
        # Mirrors episode_builder.py's own absorption convention: entry ==
        # prior exit means the earlier position is already flat.
        episodes = pd.DataFrame([
            _episode(episode_start_date="2024-01-01", episode_end_date="2024-01-10"),
            _episode(episode_start_date="2024-01-10", episode_end_date="2024-01-20"),
        ])

        result = simulate_portfolio(episodes, policy_hard_cap, n_slots=1)

        assert result["n_taken"] == 2
        assert result["n_missed_due_to_slots"] == 0


class TestSizingAndEquityCurve:

    def test_full_size_trade_applies_full_risk_times_r_multiple(self):
        episodes = pd.DataFrame([_episode(r_multiple=2.0)])

        result = simulate_portfolio(episodes, policy_hard_cap, base_risk_pct=1.0, starting_equity=100.0)

        # 1% risk x r_multiple 2.0 = 2% gain -> 102.0
        assert result["final_equity"] == pytest.approx(102.0)

    def test_half_size_trade_applies_half_the_contribution(self):
        episodes = pd.DataFrame([_episode(
            category="ALERT_WATCHLIST", confidence_score=70.0,
            market_regime_verdict="CAUTION", r_multiple=2.0,
        )])

        result = simulate_portfolio(episodes, policy_caution_half_unfavorable_blocked, base_risk_pct=1.0)

        # 0.5 risk_fraction x 1% x r_multiple 2.0 = 1% gain -> 101.0
        assert result["final_equity"] == pytest.approx(101.0)

    def test_nan_r_multiple_is_excluded_not_treated_as_zero_risk(self):
        episodes = pd.DataFrame([
            _episode(r_multiple=float("nan")),
            _episode(episode_start_date="2024-02-01", episode_end_date="2024-02-10", r_multiple=1.0),
        ])

        result = simulate_portfolio(episodes, policy_hard_cap)

        assert result["n_taken"] == 1

    def test_max_drawdown_is_negative_when_equity_dips_below_a_prior_peak(self):
        episodes = pd.DataFrame([
            _episode(episode_start_date="2024-01-01", episode_end_date="2024-01-05", r_multiple=2.0),
            _episode(episode_start_date="2024-01-10", episode_end_date="2024-01-15", r_multiple=-3.0),
        ])

        result = simulate_portfolio(episodes, policy_hard_cap, n_slots=1)

        assert result["max_drawdown_pct"] < 0


class TestSlotUtilization:

    def test_utilization_is_taken_over_taken_plus_missed(self):
        episodes = pd.DataFrame([
            _episode(episode_start_date="2024-01-01", episode_end_date="2024-01-20"),
            _episode(episode_start_date="2024-01-02", episode_end_date="2024-01-20"),
        ])

        result = simulate_portfolio(episodes, policy_hard_cap, n_slots=1)

        assert result["n_taken"] == 1
        assert result["n_missed_due_to_slots"] == 1
        assert result["slot_utilization_pct"] == pytest.approx(50.0)


class TestEmptyInput:

    def test_no_episodes_selected_returns_flat_result_not_a_crash(self):
        episodes = pd.DataFrame([_episode(category="ALERT_WATCHLIST", confidence_score=50.0)])

        result = simulate_portfolio(episodes, policy_hard_cap)

        assert result["n_taken"] == 0
        assert result["final_equity"] == 100.0
        assert result["max_drawdown_pct"] == 0.0


class TestComparePolicies:

    def test_returns_one_row_per_named_policy(self):
        episodes = pd.DataFrame([_episode()])

        table = compare_policies(episodes)

        assert set(table["policy"]) == set(NAMED_POLICIES.keys())
        assert "equity_curve" not in table.columns
