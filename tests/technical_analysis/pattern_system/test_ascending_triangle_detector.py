"""
Tests for technical_analysis/pattern_system/ascending_triangle_detector.py
-- kept lean per spec: one qualifying fixture, one that should clearly
not qualify (rising lows with ALSO-rising highs -- confirms the detector
is actually checking for a flat ceiling, not just any upward structure).

Unlike flat_base_detector.py / bull_flag_detector.py, this detector uses
confirmed swing pivots (not a raw tail window) for its resistance level,
so there's no self-reference risk between the breakout bar and its own
pivot level -- verified directly rather than assumed.
"""
from __future__ import annotations

import pandas as pd
import pytest

from technical_analysis.pattern_system.ascending_triangle_detector import AscendingTriangleDetector
from technical_analysis.pattern_system.models import SwingPoint


def _df(breakout_close: float, breakout_volume: float) -> pd.DataFrame:
    n = 30
    closes = [95.0] * (n - 1) + [breakout_close]
    volumes = [100_000] * (n - 1) + [breakout_volume]
    return pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=n, freq="D"),
        "Open": closes, "High": closes, "Low": closes, "Close": closes,
        "Volume": volumes, "Volume_SMA_20": [100_000] * n,
    })


@pytest.fixture
def detector() -> AscendingTriangleDetector:
    return AscendingTriangleDetector()


class TestQualifyingAscendingTriangle:

    def test_flat_highs_with_rising_lows_and_confirmed_breakout_qualifies(self, detector):
        # Highs ~100/101 (flat, within 3% tolerance), lows 90->95 (rising)
        pivots = [
            SwingPoint(index=0, date="d", price=90.0, type="LOW", is_higher=True),
            SwingPoint(index=1, date="d", price=100.0, type="HIGH", is_higher=True),
            SwingPoint(index=2, date="d", price=95.0, type="LOW", is_higher=True),
            SwingPoint(index=3, date="d", price=101.0, type="HIGH", is_higher=True),
        ]

        result = detector.analyze_ascending_triangle(
            _df(breakout_close=105.0, breakout_volume=200_000), pivots, "UPTREND"
        )

        assert result["is_ascending_triangle_setup"] == True
        assert result["is_breakout_confirmed"] == True


class TestRisingHighsRejected:

    def test_rising_lows_with_also_rising_highs_does_not_qualify(self, detector):
        """The one place this must actually check for a FLAT ceiling, not
        just any upward structure: lows rising 90->95 AND highs also
        rising 95->105 -- an ascending channel, not a triangle."""
        pivots = [
            SwingPoint(index=0, date="d", price=90.0, type="LOW", is_higher=True),
            SwingPoint(index=1, date="d", price=95.0, type="HIGH", is_higher=True),
            SwingPoint(index=2, date="d", price=95.0, type="LOW", is_higher=True),
            SwingPoint(index=3, date="d", price=105.0, type="HIGH", is_higher=True),
        ]

        result = detector.analyze_ascending_triangle(
            _df(breakout_close=95.0, breakout_volume=100_000), pivots, "UPTREND"
        )

        assert result["is_ascending_triangle_setup"] == False
        assert result["invalidated_reason"] == "RESISTANCE_NOT_FLAT"
