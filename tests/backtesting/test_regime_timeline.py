"""
Tests for backtesting/regime_timeline.py (A-2).
"""
from __future__ import annotations

import pandas as pd
import pytest

from backtesting.regime_timeline import (
    _cause,
    attribute_episodes_to_periods,
    build_regime_timeline,
    find_contiguous_periods,
    summarize_regime_timeline,
)


class TestCause:

    def test_downtrend_wins_regardless_of_distribution_days(self):
        assert _cause("DOWNTREND", distribution_days=0) == "DOWNTREND"

    def test_choppy_alone(self):
        assert _cause("CHOPPY", distribution_days=0) == "CHOPPY trend"

    def test_distribution_days_alone_on_an_uptrend(self):
        assert _cause("UPTREND", distribution_days=4) == "distribution_days=4>=3"

    def test_both_choppy_and_distribution_days(self):
        assert _cause("CHOPPY", distribution_days=5) == "CHOPPY trend + distribution_days=5>=3"

    def test_favorable_case(self):
        assert _cause("UPTREND", distribution_days=1) == "UPTREND, distribution_days<3"


class TestBuildRegimeTimeline:

    def test_iterates_every_date_in_window_and_uses_the_real_helpers(self, monkeypatch):
        import backtesting.regime_timeline as regime_timeline

        monkeypatch.setattr(regime_timeline, "_trend_state_of_truncated", lambda df: "CHOPPY")
        monkeypatch.setattr(regime_timeline, "count_distribution_days", lambda df: 4)

        benchmark_history = pd.DataFrame({
            "Date": pd.date_range("2024-01-01", periods=10, freq="D"),
            "Close": range(10),
        })

        timeline = build_regime_timeline(
            benchmark_history, pd.Timestamp("2024-01-03"), pd.Timestamp("2024-01-06")
        )

        assert len(timeline) == 4
        assert set(timeline["market_regime_verdict"]) == {"CAUTION"}
        assert set(timeline["cause"]) == {"CHOPPY trend + distribution_days=4>=3"}

    def test_unknown_trend_state_falls_back_to_unfavorable(self, monkeypatch):
        import backtesting.regime_timeline as regime_timeline

        monkeypatch.setattr(regime_timeline, "_trend_state_of_truncated", lambda df: "UNKNOWN")
        monkeypatch.setattr(regime_timeline, "count_distribution_days", lambda df: None)

        benchmark_history = pd.DataFrame({
            "Date": pd.date_range("2024-01-01", periods=3, freq="D"),
            "Close": range(3),
        })

        timeline = build_regime_timeline(
            benchmark_history, pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-03")
        )

        assert (timeline["market_regime_verdict"] == "UNFAVORABLE").all()
        assert (timeline["cause"] == "insufficient benchmark history").all()


class TestSummarizeRegimeTimeline:

    def test_percentages_sum_to_one_hundred(self):
        timeline = pd.DataFrame([
            {"market_regime_verdict": "CAUTION", "cause": "CHOPPY trend"},
            {"market_regime_verdict": "CAUTION", "cause": "CHOPPY trend"},
            {"market_regime_verdict": "UNFAVORABLE", "cause": "DOWNTREND"},
            {"market_regime_verdict": "FAVORABLE", "cause": "UPTREND, distribution_days<3"},
        ])

        summary = summarize_regime_timeline(timeline)

        assert summary["total_days"] == 4
        assert summary["by_verdict"]["pct_of_window"].sum() == pytest.approx(100.0)
        caution_row = summary["by_verdict"][summary["by_verdict"]["verdict"] == "CAUTION"].iloc[0]
        assert caution_row["n_days"] == 2
        assert caution_row["pct_of_window"] == pytest.approx(50.0)


class TestFindContiguousPeriods:

    def test_single_contiguous_run(self):
        timeline = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "market_regime_verdict": ["CAUTION", "UNFAVORABLE", "UNFAVORABLE", "UNFAVORABLE", "CAUTION"],
        })

        periods = find_contiguous_periods(timeline, "UNFAVORABLE")

        assert len(periods) == 1
        assert periods[0]["n_days"] == 3
        assert periods[0]["start_date"] == pd.Timestamp("2024-01-02")
        assert periods[0]["end_date"] == pd.Timestamp("2024-01-04")

    def test_two_separate_runs_are_not_merged(self):
        timeline = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=6, freq="D"),
            "market_regime_verdict": ["UNFAVORABLE", "UNFAVORABLE", "CAUTION", "CAUTION", "UNFAVORABLE", "UNFAVORABLE"],
        })

        periods = find_contiguous_periods(timeline, "UNFAVORABLE")

        assert len(periods) == 2
        assert periods[0]["n_days"] == 2
        assert periods[1]["n_days"] == 2

    def test_verdict_never_present_returns_empty_list(self):
        timeline = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=3, freq="D"),
            "market_regime_verdict": ["CAUTION", "CAUTION", "CAUTION"],
        })

        assert find_contiguous_periods(timeline, "UNFAVORABLE") == []

    def test_run_extending_to_the_end_of_the_timeline_is_closed_out(self):
        timeline = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=3, freq="D"),
            "market_regime_verdict": ["CAUTION", "UNFAVORABLE", "UNFAVORABLE"],
        })

        periods = find_contiguous_periods(timeline, "UNFAVORABLE")

        assert len(periods) == 1
        assert periods[0]["n_days"] == 2


class TestAttributeEpisodesToPeriods:

    def test_episodes_clustered_in_one_period_report_as_one_row(self):
        periods = [
            {"start_date": pd.Timestamp("2024-01-01"), "end_date": pd.Timestamp("2024-01-10"), "n_days": 10},
            {"start_date": pd.Timestamp("2024-02-01"), "end_date": pd.Timestamp("2024-02-10"), "n_days": 10},
        ]
        episodes = pd.DataFrame({
            "episode_start_date": [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-05"), pd.Timestamp("2024-01-08")],
        })

        result = attribute_episodes_to_periods(episodes, periods)

        assert len(result) == 1
        assert result.iloc[0]["n_episodes"] == 3
        assert result.iloc[0]["period_index"] == 0

    def test_episodes_spread_across_periods_report_as_separate_rows(self):
        periods = [
            {"start_date": pd.Timestamp("2024-01-01"), "end_date": pd.Timestamp("2024-01-10"), "n_days": 10},
            {"start_date": pd.Timestamp("2024-02-01"), "end_date": pd.Timestamp("2024-02-10"), "n_days": 10},
        ]
        episodes = pd.DataFrame({
            "episode_start_date": [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-02-05")],
        })

        result = attribute_episodes_to_periods(episodes, periods)

        assert len(result) == 2
        assert set(result["n_episodes"]) == {1, 1}

    def test_empty_episodes_returns_empty_frame(self):
        result = attribute_episodes_to_periods(pd.DataFrame(), [{"start_date": 1, "end_date": 2, "n_days": 1}])

        assert result.empty
