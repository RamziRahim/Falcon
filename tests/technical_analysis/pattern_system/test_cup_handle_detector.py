"""
Tests for technical_analysis/pattern_system/cup_handle_detector.py -- kept
lean per spec: one qualifying fixture, one that should clearly not
qualify (the "roundness" heuristic's blind spot specifically -- a low
positioned at the very start of the window, not centered).

Also regression-guards the same self-reference bug found in
flat_base_detector.py: the handle window must exclude the current/
breakout bar, or a genuine breakout fails price_crossed_pivot because its
own High inflates handle_high.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from technical_analysis.pattern_system.cup_handle_detector import CupHandleDetector

WINDOW_DAYS = 65 * 5  # MAX_CUP_WEEKS * 5


def _low_at_start_df(cup_low, handle_low=95.0, breakout_close=105.0) -> pd.DataFrame:
    """
    A quick decline in the first 20 bars followed by a long slow climb --
    puts the window's true minimum at ~6% position (not roughly centered
    at 25-75%), unlike a real cup.
    """
    decline_len = 20
    seg_decline = np.linspace(100, cup_low, decline_len)
    seg_recover = np.linspace(cup_low, 100, WINDOW_DAYS - decline_len - 15)
    seg_handle = np.linspace(100, handle_low, 15)

    closes = np.concatenate([seg_decline, seg_recover, seg_handle])
    closes = np.concatenate([closes, [breakout_close]])

    n = len(closes)
    return pd.DataFrame({
        "Date": pd.date_range("2020-01-01", periods=n, freq="D"),
        "Open": closes, "High": closes * 1.002, "Low": closes * 0.998, "Close": closes,
        "Volume": [100_000] * (n - 1) + [200_000],
        "Volume_SMA_20": [100_000] * n,
    })


def _rounded_cup_df() -> pd.DataFrame:
    """A real cup: low sits near the window's midpoint (~centered), depth
    and handle both within valid ranges."""
    third = WINDOW_DAYS // 3
    seg_a = np.linspace(85, 100, third)             # rises from 85 -- avoids tying with cup_low=70
    seg_b = np.linspace(100, 70, third // 2)         # decline into the true low
    seg_c = np.linspace(70, 100, WINDOW_DAYS - third - (third // 2) - 15)
    seg_handle = np.linspace(100, 95, 15)

    closes = np.concatenate([seg_a, seg_b, seg_c, seg_handle])
    closes = np.concatenate([closes, [105.0]])

    n = len(closes)
    return pd.DataFrame({
        "Date": pd.date_range("2020-01-01", periods=n, freq="D"),
        "Open": closes, "High": closes * 1.002, "Low": closes * 0.998, "Close": closes,
        "Volume": [100_000] * (n - 1) + [200_000],
        "Volume_SMA_20": [100_000] * n,
    })


@pytest.fixture
def detector() -> CupHandleDetector:
    return CupHandleDetector()


class TestQualifyingCupHandle:

    def test_rounded_cup_with_confirmed_breakout_qualifies(self, detector):
        result = detector.analyze_cup_handle(_rounded_cup_df(), "UPTREND")

        assert result["is_cup_handle_setup"] == True
        assert result["price_crossed_pivot"] == True, (
            "The breakout bar's own high must not be part of the handle "
            "window used to compute pivot_level -- otherwise a genuine "
            "breakout can never cross its own inflated pivot."
        )
        assert result["is_breakout_confirmed"] == True


class TestCupNotRounded:

    def test_low_at_window_start_does_not_qualify(self, detector):
        """The one place the roundness heuristic could silently accept a
        shape that isn't a real cup: the low sits at ~6% of the window
        (a quick early dip followed by a long slow climb), not roughly
        centered (25-75%)."""
        df = _low_at_start_df(cup_low=70)

        result = detector.analyze_cup_handle(df, "UPTREND")

        assert result["is_cup_handle_setup"] == False
        assert result["invalidated_reason"] == "CUP_NOT_ROUNDED"
