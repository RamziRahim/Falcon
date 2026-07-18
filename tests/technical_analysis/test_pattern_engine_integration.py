"""
Integration test for pattern_engine.py's cross-pattern aggregation --
confirms that when two independent detectors (Flat Base and Ascending
Triangle) both genuinely confirm a breakout on the same underlying data,
Multiple_Patterns_Confirmed and Pattern_Type reflect BOTH, not just one.

Scoping note: the originating spec's test description also asked to
confirm "the score reflects both the base +30 and the +5 confluence
bonus." No Tier 1/2 deterministic scoring/decision-layer module exists
anywhere in this codebase (confirmed via a full-repo search before
writing this test) -- ai/synthesis_engine.py is an LLM-prompted engine,
not a point-scoring one, and strategies/Reversal is a scaffolded-but-
unbuilt placeholder. Consistent with every prior deferred item this
session (promoter pledge, institutional flow, etc.), this test verifies
only what's actually built: the Pattern_Type / Any_Breakout_Confirmed /
Multiple_Patterns_Confirmed aggregation itself.
"""
from __future__ import annotations

import pandas as pd
import pytest

from technical_analysis.pattern_engine import aggregate_confirmed_patterns
from technical_analysis.pattern_system.flat_base_detector import flat_base_detector
from technical_analysis.pattern_system.ascending_triangle_detector import ascending_triangle_detector
from technical_analysis.pattern_system.models import SwingPoint


def _shared_breakout_df() -> pd.DataFrame:
    """25-bar flat base (10% depth, well under the 15% cap) followed by a
    single breakout bar. Flat_Base reads its pivot straight off this df's
    trailing window; Ascending_Triangle's resistance_level instead comes
    from the hand-built pivots below -- both are set to the same ~100
    level so the one breakout bar (Close=105) clears both simultaneously.
    """
    n_base = 25
    highs = [100.0] * n_base + [106.0]
    lows = [90.0] * n_base + [104.0]
    closes = [95.0] * n_base + [105.0]
    n = n_base + 1
    return pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=n, freq="D"),
        "Open": closes, "High": highs, "Low": lows, "Close": closes,
        "Volume": [100_000] * n_base + [200_000],
        "Volume_SMA_20": [100_000] * n,
    })


def _shared_pivots() -> list[SwingPoint]:
    """Flat highs ~100 (within Ascending Triangle's 3% tolerance), rising
    lows 90->95 -- independent of the df above, since the detector takes
    its own pivot list rather than deriving one from raw price."""
    return [
        SwingPoint(index=0, date="d", price=90.0, type="LOW", is_higher=True),
        SwingPoint(index=1, date="d", price=100.0, type="HIGH", is_higher=True),
        SwingPoint(index=2, date="d", price=95.0, type="LOW", is_higher=True),
        SwingPoint(index=3, date="d", price=101.0, type="HIGH", is_higher=True),
    ]


class TestSimultaneousPatternConfirmation:

    def test_flat_base_and_ascending_triangle_both_confirming_sets_multiple_patterns_confirmed(self):
        df = _shared_breakout_df()
        pivots = _shared_pivots()

        flat_base = flat_base_detector.analyze_flat_base(df, macro_pivots=[], trend_state="UPTREND")
        triangle = ascending_triangle_detector.analyze_ascending_triangle(df, pivots, "UPTREND")

        # Sanity: both detectors must have genuinely confirmed on their own
        # terms before the aggregation logic can be meaningfully tested.
        assert flat_base["is_breakout_confirmed"] == True
        assert triangle["is_breakout_confirmed"] == True

        pattern_results = [("Flat_Base", flat_base), ("Ascending_Triangle", triangle)]
        aggregated = aggregate_confirmed_patterns(pattern_results)

        assert aggregated["any_breakout_confirmed"] == True
        assert aggregated["multiple_patterns_confirmed"] == True
        assert "Flat_Base" in aggregated["pattern_type"]
        assert "Ascending_Triangle" in aggregated["pattern_type"]

    def test_single_confirming_pattern_does_not_set_multiple_patterns_confirmed(self):
        # Control case: only one of the two detectors confirms -- guards
        # against a bug where multiple_patterns_confirmed is always True.
        df = _shared_breakout_df()

        flat_base = flat_base_detector.analyze_flat_base(df, macro_pivots=[], trend_state="UPTREND")
        assert flat_base["is_breakout_confirmed"] == True

        not_confirmed = {"is_breakout_confirmed": False}
        pattern_results = [("Flat_Base", flat_base), ("Ascending_Triangle", not_confirmed)]
        aggregated = aggregate_confirmed_patterns(pattern_results)

        assert aggregated["any_breakout_confirmed"] == True
        assert aggregated["multiple_patterns_confirmed"] == False
        assert aggregated["pattern_type"] == "Flat_Base"
