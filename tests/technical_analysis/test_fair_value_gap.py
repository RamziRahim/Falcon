"""
Tests for technical_analysis/fair_value_gap.py -- the 6 cases that
actually matter: clear bullish FVG, clear bearish FVG, no gap (overlapping
candles), partially filled gap, fully filled gap, insufficient history.
"""
from __future__ import annotations

import pandas as pd
import pytest

from technical_analysis.fair_value_gap import detect_fvg


def _df(highs: list[float], lows: list[float], closes: list[float]) -> pd.DataFrame:
    n = len(highs)
    return pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=n, freq="D"),
        "Open": closes, "High": highs, "Low": lows, "Close": closes,
    })


class TestBullishFVG:

    def test_clear_bullish_gap_detected_with_correct_top_and_bottom(self):
        # A (idx0): High=95. B (idx1): irrelevant middle candle. C (idx2): Low=100.
        # Gap sits [95, 100]. Latest close (105) sits above gap_top -- untouched.
        df = _df(highs=[95.0, 98.0, 103.0], lows=[88.0, 94.0, 100.0], closes=[92.0, 97.0, 105.0])

        result = detect_fvg(df, as_of_index=2)

        assert result["has_fvg"] == True
        assert result["direction"] == "bullish"
        assert result["gap_bottom"] == pytest.approx(95.0)
        assert result["gap_top"] == pytest.approx(100.0)
        assert result["gap_filled_pct"] == pytest.approx(0.0)


class TestBearishFVG:

    def test_clear_bearish_gap_detected_with_correct_top_and_bottom(self):
        # A (idx0): Low=100. B (idx1): irrelevant middle candle. C (idx2): High=95.
        # Gap sits [95, 100]. Latest close (92) sits below gap_bottom -- untouched.
        df = _df(highs=[108.0, 101.0, 95.0], lows=[100.0, 97.0, 88.0], closes=[102.0, 98.0, 92.0])

        result = detect_fvg(df, as_of_index=2)

        assert result["has_fvg"] == True
        assert result["direction"] == "bearish"
        assert result["gap_bottom"] == pytest.approx(95.0)
        assert result["gap_top"] == pytest.approx(100.0)
        assert result["gap_filled_pct"] == pytest.approx(0.0)


class TestNoGapOnOverlappingCandles:

    def test_overlapping_ranges_do_not_register_as_a_gap(self):
        df = _df(highs=[95.0, 96.0, 97.0], lows=[88.0, 89.0, 90.0], closes=[93.0, 94.0, 95.0])

        result = detect_fvg(df, as_of_index=2)

        assert result["has_fvg"] == False
        assert result["direction"] is None


class TestPartiallyFilledGap:

    def test_gap_filled_pct_reflects_a_close_halfway_into_the_bullish_gap(self):
        # Same bullish gap [95, 100] as above, but with a 4th bar whose
        # close (97.5) sits exactly halfway back into the gap.
        df = _df(
            highs=[95.0, 98.0, 103.0, 103.0],
            lows=[88.0, 94.0, 100.0, 97.0],
            closes=[92.0, 97.0, 102.0, 97.5],
        )

        result = detect_fvg(df, as_of_index=2)

        assert result["has_fvg"] == True
        assert result["gap_filled_pct"] == pytest.approx(50.0)


class TestFullyFilledGap:

    def test_gap_filled_pct_clamps_to_100_once_price_trades_through(self):
        # Same bullish gap, 4th bar's close (90) has traded all the way
        # through to below gap_bottom -- fully filled, clamped at 100,
        # not allowed to exceed it.
        df = _df(
            highs=[95.0, 98.0, 103.0, 103.0],
            lows=[88.0, 94.0, 100.0, 89.0],
            closes=[92.0, 97.0, 102.0, 90.0],
        )

        result = detect_fvg(df, as_of_index=2)

        assert result["has_fvg"] == True
        assert result["gap_filled_pct"] == pytest.approx(100.0)


class TestInsufficientHistory:

    def test_fewer_than_3_candles_returns_no_fvg_not_a_crash(self):
        df = _df(highs=[95.0, 98.0], lows=[88.0, 94.0], closes=[92.0, 97.0])

        result = detect_fvg(df, as_of_index=1)

        assert result["has_fvg"] == False

    def test_out_of_bounds_index_returns_no_fvg_not_a_crash(self):
        df = _df(highs=[95.0, 98.0, 103.0], lows=[88.0, 94.0, 100.0], closes=[92.0, 97.0, 102.0])

        result = detect_fvg(df, as_of_index=10)

        assert result["has_fvg"] == False
