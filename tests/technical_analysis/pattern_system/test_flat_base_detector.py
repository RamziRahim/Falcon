"""
Tests for technical_analysis/pattern_system/flat_base_detector.py -- kept
lean per spec: one qualifying fixture, one that should clearly not qualify.

Also regression-guards a real bug caught during development: the base
window must exclude the current/breakout bar. Including it (a naive
df.tail(N)) self-referentially inflates base_high with today's own High
(always >= today's Close by OHLC construction), making a genuine breakout
fail both the depth check and the price-cross check.
"""
from __future__ import annotations

import pandas as pd
import pytest

from technical_analysis.pattern_system.flat_base_detector import FlatBaseDetector


def _df(highs, lows, closes, volumes, volume_sma=None):
    n = len(highs)
    return pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=n, freq="D"),
        "Open": closes, "High": highs, "Low": lows, "Close": closes,
        "Volume": volumes,
        "Volume_SMA_20": volume_sma if volume_sma is not None else [100_000] * n,
    })


@pytest.fixture
def detector() -> FlatBaseDetector:
    return FlatBaseDetector()


class TestQualifyingFlatBase:

    def test_shallow_base_with_confirmed_breakout_qualifies(self, detector):
        # 25-bar base (High=100, Low=90 -> 10% depth), then a real breakout
        # bar (Close=105, High=106, volume spike) -- base excludes this bar.
        highs = [100.0] * 25 + [106.0]
        lows = [90.0] * 25 + [104.0]
        closes = [95.0] * 25 + [105.0]
        volumes = [100_000] * 25 + [200_000]

        result = detector.analyze_flat_base(_df(highs, lows, closes, volumes), [], "UPTREND")

        assert result["is_flat_base_setup"] == True
        assert result["base_depth_pct"] == pytest.approx(10.0)
        assert result["pivot_level"] == pytest.approx(100.0), (
            "pivot_level must be the base's own resistance (100), not "
            "inflated by including the breakout bar's own high (106)."
        )
        assert result["price_crossed_pivot"] == True
        assert result["is_breakout_confirmed"] == True


class TestBaseTooDeep:

    def test_base_deeper_than_15_percent_does_not_qualify(self, detector):
        # Flat range but depth = 20% (100 vs 80), well past MAX_DEPTH_PCT=15%
        highs = [100.0] * 26
        lows = [80.0] * 26
        closes = [90.0] * 26
        volumes = [100_000] * 26

        result = detector.analyze_flat_base(_df(highs, lows, closes, volumes), [], "UPTREND")

        assert result["is_flat_base_setup"] == False
        assert result["invalidated_reason"] == "BASE_TOO_DEEP"
        assert result["base_depth_pct"] == pytest.approx(20.0)
