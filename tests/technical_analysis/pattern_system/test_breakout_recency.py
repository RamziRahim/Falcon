"""
Tests for technical_analysis/pattern_system/breakout_recency.py (A-5).
"""
from __future__ import annotations

import pandas as pd

from technical_analysis.pattern_system.breakout_recency import compute_breakout_recency


def _df(closes, volumes):
    dates = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    return pd.DataFrame({"Date": dates, "Close": closes, "Volume": volumes})


class TestNotCurrentlyABreakout:

    def test_latest_bar_below_pivot_returns_none_and_false(self):
        df = _df([90.0, 91.0, 92.0], [100, 100, 100])

        result = compute_breakout_recency(df, pivot_level=100.0, volume_baseline=50.0)

        assert result["bars_since_breakout"] is None
        assert result["breakout_within_last_k_bars"] is False

    def test_latest_bar_above_pivot_but_volume_too_low_returns_none(self):
        df = _df([101.0], [60])  # need >= 50*1.5=75

        result = compute_breakout_recency(df, pivot_level=100.0, volume_baseline=50.0)

        assert result["bars_since_breakout"] is None

    def test_missing_pivot_or_baseline_returns_none_not_a_crash(self):
        df = _df([101.0], [100])

        assert compute_breakout_recency(df, pivot_level=None, volume_baseline=50.0)["bars_since_breakout"] is None
        assert compute_breakout_recency(df, pivot_level=100.0, volume_baseline=None)["bars_since_breakout"] is None
        assert compute_breakout_recency(df, pivot_level=100.0, volume_baseline=0.0)["bars_since_breakout"] is None


class TestFreshBreakout:

    def test_first_day_of_breakout_is_zero_bars_since(self):
        # Below pivot for 2 days, then crosses today with volume.
        df = _df([90.0, 95.0, 101.0], [100, 100, 100])

        result = compute_breakout_recency(df, pivot_level=100.0, volume_baseline=50.0, k=5)

        assert result["bars_since_breakout"] == 0
        assert result["breakout_within_last_k_bars"] is True


class TestStaleBreakout:

    def test_breakout_held_for_many_days_reports_the_full_streak_length(self):
        # Crossed 10 days ago and has stayed above the pivot with volume
        # every day since -- streak is 11 bars long (today + 10 more).
        closes = [90.0] * 3 + [101.0] * 11
        volumes = [100] * 3 + [100] * 11
        df = _df(closes, volumes)

        result = compute_breakout_recency(df, pivot_level=100.0, volume_baseline=50.0, k=5)

        assert result["bars_since_breakout"] == 10
        assert result["breakout_within_last_k_bars"] is False

    def test_breakout_within_k_bars_boundary_is_inclusive(self):
        # Streak of exactly 6 bars (today + 5 more) -- bars_since_breakout=5, k=5 -> True
        closes = [90.0] + [101.0] * 6
        volumes = [100] + [100] * 6
        df = _df(closes, volumes)

        result = compute_breakout_recency(df, pivot_level=100.0, volume_baseline=50.0, k=5)

        assert result["bars_since_breakout"] == 5
        assert result["breakout_within_last_k_bars"] is True

    def test_streak_interrupted_by_a_day_below_pivot_resets_the_count(self):
        # Broke out, fell back below pivot for a day, broke out again --
        # only the CURRENT unbroken streak counts, not the earlier one.
        closes = [90.0, 101.0, 101.0, 99.0, 101.0]  # dip below pivot at index 3
        volumes = [100] * 5
        df = _df(closes, volumes)

        result = compute_breakout_recency(df, pivot_level=100.0, volume_baseline=50.0, k=5)

        assert result["bars_since_breakout"] == 0


class TestMaxLookbackCap:

    def test_a_streak_longer_than_max_lookback_is_capped_not_uncounted(self):
        closes = [101.0] * 80  # breakout held the entire available history
        volumes = [100] * 80
        df = _df(closes, volumes)

        result = compute_breakout_recency(df, pivot_level=100.0, volume_baseline=50.0, max_lookback=60)

        # Loop examines at most max_lookback bars total -> streak capped at
        # 60 -> bars_since_breakout capped at 59 (0-indexed distance).
        assert result["bars_since_breakout"] == 59
