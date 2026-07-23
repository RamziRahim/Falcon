"""
Tests for backtesting/episode_builder.py (I-1).
"""
from __future__ import annotations

import pandas as pd
import pytest

from backtesting.episode_builder import EPISODE_COLUMNS, build_episodes
from config import ROUND_TRIP_COST_PCT


def _row(ticker, entry_date, exit_date, category="ALERT_WATCHLIST", return_pct=10.0,
         stop_pct=5.0, exit_reason="TARGET_HIT", days_held=7, confidence_score=50.0,
         pattern_used=None, market_regime_verdict="FAVORABLE", sector_health_verdict="NEUTRAL"):
    return {
        "ticker": ticker, "entry_date": entry_date, "entry_price": 100.0,
        "category": category, "pattern_used": pattern_used,
        "market_regime_verdict": market_regime_verdict,
        "sector_health_verdict": sector_health_verdict,
        "exit_date": exit_date, "exit_price": 110.0, "exit_reason": exit_reason,
        "return_pct": return_pct, "days_held": days_held,
        "target_pct": 10.0, "stop_pct": stop_pct,
        "confidence_score": confidence_score, "caps_applied": float("nan"),
    }


class TestNoOverlapProducesOneEpisodePerSignal:

    def test_disjoint_windows_all_survive_as_separate_episodes(self):
        trades = pd.DataFrame([
            _row("AAA.NS", "2024-01-01", "2024-01-10"),
            _row("AAA.NS", "2024-01-15", "2024-01-20"),
            _row("AAA.NS", "2024-01-25", "2024-01-30"),
        ])

        episodes = build_episodes(trades)

        assert len(episodes) == 3
        assert (episodes["n_signals_absorbed"] == 1).all()


class TestOverlappingSignalsAreAbsorbed:

    def test_entry_strictly_before_founder_exit_is_absorbed_not_a_new_episode(self):
        trades = pd.DataFrame([
            _row("AAA.NS", "2024-01-01", "2024-01-31", category="ALERT_WATCHLIST"),
            _row("AAA.NS", "2024-01-15", "2024-01-20", category="ALERT_WATCHLIST"),  # inside founder's window
        ])

        episodes = build_episodes(trades)

        assert len(episodes) == 1
        assert episodes.iloc[0]["n_signals_absorbed"] == 2
        # Episode's own outcome is always the FOUNDER's, never the absorbed signal's
        assert episodes.iloc[0]["episode_end_date"] == pd.Timestamp("2024-01-31")

    def test_entry_equal_to_founder_exit_starts_a_new_episode(self):
        trades = pd.DataFrame([
            _row("AAA.NS", "2024-01-01", "2024-01-10"),
            _row("AAA.NS", "2024-01-10", "2024-01-20"),  # entry == prior exit -- already flat
        ])

        episodes = build_episodes(trades)

        assert len(episodes) == 2
        assert (episodes["n_signals_absorbed"] == 1).all()

    def test_category_changes_records_every_distinct_category_seen(self):
        trades = pd.DataFrame([
            _row("AAA.NS", "2024-01-01", "2024-01-31", category="ALERT_WATCHLIST"),
            _row("AAA.NS", "2024-01-10", "2024-01-15", category="EXECUTE"),
        ])

        episodes = build_episodes(trades)

        assert episodes.iloc[0]["category"] == "ALERT_WATCHLIST"  # founder's category wins
        assert set(episodes.iloc[0]["category_changes"].split(",")) == {"ALERT_WATCHLIST", "EXECUTE"}

    def test_absorption_does_not_extend_the_open_window(self):
        # Founder's window is 01-01 -> 01-10. A signal at 01-12 is NOT absorbed
        # (it's past the founder's own window) even though an earlier absorbed
        # signal's own exit_date might be later -- the window never re-opens.
        trades = pd.DataFrame([
            _row("AAA.NS", "2024-01-01", "2024-01-10"),
            _row("AAA.NS", "2024-01-05", "2024-01-25"),  # absorbed, but its own exit_date is later
            _row("AAA.NS", "2024-01-12", "2024-01-20"),  # after founder's exit -- new episode
        ])

        episodes = build_episodes(trades)

        assert len(episodes) == 2
        assert episodes.iloc[0]["n_signals_absorbed"] == 2
        assert episodes.iloc[1]["n_signals_absorbed"] == 1


class TestMultipleTickersAreIndependent:

    def test_tickers_never_absorb_across_each_other(self):
        trades = pd.DataFrame([
            _row("AAA.NS", "2024-01-01", "2024-01-31"),
            _row("BBB.NS", "2024-01-05", "2024-01-10"),  # overlaps AAA's window in time, different ticker
        ])

        episodes = build_episodes(trades)

        assert len(episodes) == 2
        assert set(episodes["ticker"]) == {"AAA.NS", "BBB.NS"}


class TestGrossNetAndRMultiple:

    def test_net_return_is_gross_minus_round_trip_cost(self):
        trades = pd.DataFrame([_row("AAA.NS", "2024-01-01", "2024-01-10", return_pct=10.0)])

        episodes = build_episodes(trades)

        assert episodes.iloc[0]["gross_return_pct"] == pytest.approx(10.0)
        assert episodes.iloc[0]["net_return_pct"] == pytest.approx(10.0 - ROUND_TRIP_COST_PCT * 100)

    def test_r_multiple_is_net_return_over_planned_stop_distance(self):
        trades = pd.DataFrame([_row("AAA.NS", "2024-01-01", "2024-01-10", return_pct=10.0, stop_pct=5.0)])

        episodes = build_episodes(trades)

        expected_net = 10.0 - ROUND_TRIP_COST_PCT * 100
        assert episodes.iloc[0]["r_multiple"] == pytest.approx(expected_net / 5.0)

    def test_r_multiple_is_nan_when_stop_pct_is_zero(self):
        trades = pd.DataFrame([_row("AAA.NS", "2024-01-01", "2024-01-10", stop_pct=0.0)])

        episodes = build_episodes(trades)

        assert pd.isna(episodes.iloc[0]["r_multiple"])


class TestEmptyInput:

    def test_empty_trades_returns_empty_frame_with_expected_columns(self):
        episodes = build_episodes(pd.DataFrame())

        assert episodes.empty
        assert list(episodes.columns) == EPISODE_COLUMNS
