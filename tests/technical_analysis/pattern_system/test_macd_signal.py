"""
Tests for technical_analysis/pattern_system/macd_signal.py -- kept lean
per spec: three synthetic MACD_Hist series with known properties (clearly
bullish, clearly diverging, ambiguous), confirming each returns the
expected signal and that NEUTRAL fires on the ambiguous case rather than
forcing a classification.
"""
from __future__ import annotations

import pandas as pd

from technical_analysis.pattern_system.macd_signal import get_macd_signal


class TestBullishAlignment:

    def test_positive_and_rising_histogram_is_bullish(self):
        df = pd.DataFrame({
            "Close": [100, 101, 102, 103, 104, 105, 106, 107, 108, 110],
            "MACD_Hist": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.2],
        })
        assert get_macd_signal(df) == "BULLISH_ALIGNMENT"


class TestBearishDivergence:

    def test_new_price_high_with_fading_histogram_is_bearish_divergence(self):
        # Price steadily makes new highs; MACD_Hist peaked mid-window and
        # has been fading for several bars since -- momentum not
        # confirming the still-rising price.
        df = pd.DataFrame({
            "Close": [100, 102, 104, 106, 108, 109, 110, 111, 112, 113],
            "MACD_Hist": [0.2, 0.5, 0.9, 1.3, 1.6, 1.4, 1.1, 0.8, 0.5, 0.3],
        })
        assert get_macd_signal(df) == "BEARISH_DIVERGENCE"


class TestAmbiguousCaseStaysNeutral:

    def test_flat_price_and_oscillating_histogram_is_neutral(self):
        # Not a real trend either way -- histogram flips sign every bar,
        # price barely moves. Must not be forced into either
        # classification just because SOME bar-to-bar comparison is true.
        df = pd.DataFrame({
            "Close": [100, 100.5, 100.2, 100.6, 100.3, 100.5, 100.4, 100.5, 100.3, 100.4],
            "MACD_Hist": [0.05, -0.03, 0.02, -0.05, 0.03, -0.02, 0.04, -0.03, 0.02, -0.01],
        })
        assert get_macd_signal(df) == "NEUTRAL"


class TestGracefulDegradation:

    def test_missing_macd_hist_column_returns_neutral_not_crash(self):
        df = pd.DataFrame({"Close": [100, 101, 102]})
        assert get_macd_signal(df) == "NEUTRAL"

    def test_all_nan_macd_hist_returns_neutral_not_crash(self):
        df = pd.DataFrame({"Close": [100, 101, 102], "MACD_Hist": [None, None, None]})
        assert get_macd_signal(df) == "NEUTRAL"

    def test_insufficient_rows_returns_neutral_not_crash(self):
        df = pd.DataFrame({"Close": [100], "MACD_Hist": [0.5]})
        assert get_macd_signal(df) == "NEUTRAL"
