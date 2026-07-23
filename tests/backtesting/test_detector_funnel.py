"""
Tests for backtesting/detector_funnel.py (A-4).
"""
from __future__ import annotations

from collections import Counter

from backtesting.detector_funnel import (
    build_detector_funnel,
    classify_funnel_stage,
    funnel_counts_to_dataframe,
    tally_funnel,
)


class TestClassifyFunnelStage:

    def test_invalidated_reason_wins_when_structurally_invalid(self):
        result = {"invalidated_reason": "NOT_IN_UPTREND", "is_breakout_confirmed": False}

        assert classify_funnel_stage(result) == "NOT_IN_UPTREND"

    def test_setup_valid_but_no_breakout(self):
        result = {"invalidated_reason": None, "is_breakout_confirmed": False}

        assert classify_funnel_stage(result) == "SETUP_VALID_NO_BREAKOUT"

    def test_breakout_confirmed_but_stale(self):
        result = {
            "invalidated_reason": None, "is_breakout_confirmed": True,
            "breakout_within_last_k_bars": False,
        }

        assert classify_funnel_stage(result) == "BREAKOUT_CONFIRMED_STALE"

    def test_breakout_confirmed_and_fresh(self):
        result = {
            "invalidated_reason": None, "is_breakout_confirmed": True,
            "breakout_within_last_k_bars": True,
        }

        assert classify_funnel_stage(result) == "BREAKOUT_CONFIRMED_FRESH"


class TestBuildDetectorFunnel:

    def test_builds_one_stage_label_per_detector(self):
        analysis = {
            "vcp": {"invalidated_reason": "NOT_IN_UPTREND"},
            "flat_base": {"invalidated_reason": None, "is_breakout_confirmed": False},
            "cup_handle": {"invalidated_reason": None, "is_breakout_confirmed": True, "breakout_within_last_k_bars": True},
            "triangle": {"invalidated_reason": None, "is_breakout_confirmed": True, "breakout_within_last_k_bars": False},
            "bull_flag": {"invalidated_reason": "INSUFFICIENT_HISTORY"},
        }

        funnel = build_detector_funnel(analysis)

        assert funnel == {
            "vcp": "NOT_IN_UPTREND",
            "flat_base": "SETUP_VALID_NO_BREAKOUT",
            "cup_handle": "BREAKOUT_CONFIRMED_FRESH",
            "triangle": "BREAKOUT_CONFIRMED_STALE",
            "bull_flag": "INSUFFICIENT_HISTORY",
        }


class TestTallyFunnel:

    def test_accumulates_counts_across_multiple_calls(self):
        funnel_counts: dict = {}

        tally_funnel(funnel_counts, {"vcp": "NOT_IN_UPTREND", "flat_base": "SETUP_VALID_NO_BREAKOUT"})
        tally_funnel(funnel_counts, {"vcp": "NOT_IN_UPTREND", "flat_base": "BREAKOUT_CONFIRMED_FRESH"})

        assert funnel_counts["vcp"] == Counter({"NOT_IN_UPTREND": 2})
        assert funnel_counts["flat_base"] == Counter({"SETUP_VALID_NO_BREAKOUT": 1, "BREAKOUT_CONFIRMED_FRESH": 1})

    def test_none_detector_funnel_is_a_no_op(self):
        funnel_counts: dict = {}

        tally_funnel(funnel_counts, None)

        assert funnel_counts == {}


class TestFunnelCountsToDataFrame:

    def test_percentages_computed_per_detector_not_globally(self):
        funnel_counts = {
            "vcp": Counter({"BREAKOUT_CONFIRMED_FRESH": 1, "NOT_IN_UPTREND": 3}),
        }

        table = funnel_counts_to_dataframe(funnel_counts)

        assert set(table["detector"]) == {"VCP"}
        fresh_row = table[table["stage"] == "BREAKOUT_CONFIRMED_FRESH"].iloc[0]
        assert fresh_row["pct_of_total"] == 25.0

    def test_empty_funnel_counts_returns_empty_frame_with_expected_columns(self):
        table = funnel_counts_to_dataframe({})

        assert table.empty
        assert list(table.columns) == ["detector", "stage", "count", "pct_of_total"]
