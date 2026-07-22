"""
Tests for technical_analysis/liquidity_sweep.py -- the 5 cases that
actually matter: clear SSL sweep, clear BSL sweep, no sweep (clean trend
day), breakout that closes beyond the level (must NOT register as a
sweep -- the one place this could easily be gotten backwards), and
insufficient history.
"""
from __future__ import annotations

import pandas as pd
import pytest

from technical_analysis.liquidity_sweep import detect_liquidity_sweep

LOOKBACK = 20


def _df(final_close: float, final_low: float, final_high: float) -> pd.DataFrame:
    """20 flat prior bars (Low=90, High=100, Close=95) + one final bar
    whose Low/High/Close are under test."""
    dates = pd.date_range("2024-01-01", periods=LOOKBACK + 1, freq="D")
    closes = [95.0] * LOOKBACK + [final_close]
    lows = [90.0] * LOOKBACK + [final_low]
    highs = [100.0] * LOOKBACK + [final_high]
    return pd.DataFrame({"Date": dates, "Close": closes, "Low": lows, "High": highs})


class TestSSLSweep:

    def test_wick_below_prior_low_closing_back_inside_registers_as_ssl(self):
        # Wicks to 85 (below the prior 90 low) but closes back at 92 (inside).
        result = detect_liquidity_sweep(_df(final_close=92.0, final_low=85.0, final_high=93.0), lookback=LOOKBACK)

        assert result["swept"] == True
        assert result["direction"] == "SSL"
        assert result["swing_level"] == pytest.approx(90.0)
        assert result["sweep_bar_low"] == pytest.approx(85.0)


class TestBSLSweep:

    def test_wick_above_prior_high_closing_back_inside_registers_as_bsl(self):
        # Wicks to 105 (above the prior 100 high) but closes back at 98 (inside).
        result = detect_liquidity_sweep(_df(final_close=98.0, final_low=96.0, final_high=105.0), lookback=LOOKBACK)

        assert result["swept"] == True
        assert result["direction"] == "BSL"
        assert result["swing_level"] == pytest.approx(100.0)
        assert result["sweep_bar_high"] == pytest.approx(105.0)


class TestNoSweepOnCleanTrendDay:

    def test_bar_entirely_inside_prior_range_is_not_a_sweep(self):
        result = detect_liquidity_sweep(_df(final_close=96.0, final_low=95.5, final_high=97.0), lookback=LOOKBACK)

        assert result["swept"] == False
        assert result["direction"] is None


class TestBreakoutIsNotASweep:

    def test_closing_beyond_the_swept_level_does_not_register_as_a_sweep(self):
        # High of 105 clears the prior 100 high, AND closes at 104 --
        # beyond the level, not back inside it. A genuine breakout, not a
        # sweep-and-reject -- the one case most likely to be gotten
        # backwards.
        result = detect_liquidity_sweep(_df(final_close=104.0, final_low=99.0, final_high=105.0), lookback=LOOKBACK)

        assert result["swept"] == False, "A breakout that closes beyond the level must not register as a sweep"


class TestInsufficientHistory:

    def test_fewer_than_lookback_plus_one_rows_returns_no_sweep_not_a_crash(self):
        short_df = _df(final_close=92.0, final_low=85.0, final_high=93.0).iloc[:10]
        result = detect_liquidity_sweep(short_df, lookback=LOOKBACK)

        assert result["swept"] == False
