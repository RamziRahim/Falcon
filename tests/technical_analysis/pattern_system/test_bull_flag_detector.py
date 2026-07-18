"""
Tests for technical_analysis/pattern_system/bull_flag_detector.py -- kept
lean: one qualifying fixture, one that should clearly not qualify (a
flagpole gain below the 15% minimum -- no real flagpole, no bull flag).

Regression-guards the same self-reference bug found in
flat_base_detector.py / cup_handle_detector.py: the flag window must
exclude the current/breakout bar, or a genuine breakout fails
price_crossed_pivot because its own High inflates flag_high.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from technical_analysis.pattern_system.bull_flag_detector import BullFlagDetector


def _df(pole_gain_pct: float, flag_range: float, breakout_close: float, breakout_volume: float) -> pd.DataFrame:
    pole = np.linspace(100, 100 * (1 + pole_gain_pct / 100), 10)
    flag_high = pole[-1] + flag_range / 2
    flag_low = pole[-1] - flag_range / 2
    flag = np.linspace(flag_high, flag_low, 10)

    closes = np.concatenate([pole, flag, [breakout_close]])
    n = len(closes)
    return pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=n, freq="D"),
        "Open": closes, "High": closes * 1.002, "Low": closes * 0.998, "Close": closes,
        "Volume": [100_000] * (n - 1) + [breakout_volume],
        "Volume_SMA_20": [100_000] * n,
    })


@pytest.fixture
def detector() -> BullFlagDetector:
    return BullFlagDetector()


class TestQualifyingBullFlag:

    def test_strong_flagpole_with_shallow_flag_and_confirmed_breakout_qualifies(self, detector):
        # 20% flagpole gain (>=15% min), shallow flag retrace, confirmed breakout
        result = detector.analyze_bull_flag(
            _df(pole_gain_pct=20.0, flag_range=3.0, breakout_close=125.0, breakout_volume=200_000),
            "UPTREND",
        )

        assert result["is_bull_flag_setup"] == True
        assert result["flagpole_gain_pct"] == pytest.approx(20.0)
        assert result["price_crossed_pivot"] == True, (
            "The breakout bar's own high must not be part of the flag "
            "window used to compute pivot_level."
        )
        assert result["is_breakout_confirmed"] == True


class TestWeakFlagpoleRejected:

    def test_flagpole_gain_below_minimum_does_not_qualify(self, detector):
        # Only a 5% pole gain -- well under MIN_FLAGPOLE_GAIN_PCT=15%
        result = detector.analyze_bull_flag(
            _df(pole_gain_pct=5.0, flag_range=1.0, breakout_close=106.0, breakout_volume=100_000),
            "UPTREND",
        )

        assert result["is_bull_flag_setup"] == False
        assert result["invalidated_reason"] == "FLAGPOLE_TOO_WEAK"
