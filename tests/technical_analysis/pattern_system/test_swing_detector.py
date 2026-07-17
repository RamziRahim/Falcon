"""
Tests for technical_analysis/pattern_system/swing_detector.py -- fractal
swing-point detection, the O(n) refactor of the prior-pivot lookup (#4b),
and the boundary tie-break consistency fix.
"""
from __future__ import annotations

import pandas as pd
import pytest

from technical_analysis.pattern_system.swing_detector import SwingDetector


@pytest.fixture
def detector() -> SwingDetector:
    return SwingDetector(window=2)


class TestKnownPivotShape:

    def test_finds_pivots_at_exact_expected_indices(self, detector, synthetic_swing_points_df):
        pivots = detector.detect_swings(synthetic_swing_points_df)
        assert [p.index for p in pivots] == [3, 6, 9]
        assert [p.type for p in pivots] == ["LOW", "HIGH", "LOW"]

    def test_pivot_prices_match_expected_values(self, detector, synthetic_swing_points_df):
        pivots = detector.detect_swings(synthetic_swing_points_df)
        assert pivots[0].price == pytest.approx(79.92)
        assert pivots[1].price == pytest.approx(95.095)
        assert pivots[2].price == pytest.approx(69.93)

    def test_is_higher_relative_to_prior_same_type_pivot(self, detector, synthetic_swing_points_df):
        pivots = detector.detect_swings(synthetic_swing_points_df)
        low1, high1, low2 = pivots
        assert low1.is_higher == True, "First LOW ever seen defaults to is_higher=True."
        assert high1.is_higher == True, "First HIGH ever seen defaults to is_higher=True."
        assert low2.is_higher == False, (
            f"Second LOW ({low2.price}) is below the first LOW ({low1.price}) -- "
            "is_higher must be False."
        )


class TestBoundaryTieBreak:
    """A tied high/low at adjacent bars must be handled consistently on both
    sides of the fractal window -- not accept a tie on the right while
    rejecting the identical tie on the left. The chosen rule (strict '>'/'<'
    on both sides) treats a tie as not disqualifying either bar, so both
    members of a tied pair are valid pivots -- previously only the first
    was (the left side's old '>=' rejected the second bar's tie, the right
    side's '>' let the first bar's tie through)."""

    def test_tied_adjacent_highs_are_both_accepted(self, detector, synthetic_tied_high_df):
        pivots = detector.detect_swings(synthetic_tied_high_df)
        highs = [p for p in pivots if p.type == "HIGH"]
        assert [p.index for p in highs] == [4, 5], (
            "Both bars tied at the peak (100, 100) should be flagged as HIGH "
            "pivots under a consistent strict '>' rule on both sides."
        )

    def test_second_tied_high_is_not_is_higher(self, detector, synthetic_tied_high_df):
        pivots = detector.detect_swings(synthetic_tied_high_df)
        highs = [p for p in pivots if p.type == "HIGH"]
        assert highs[0].is_higher == True, "First HIGH ever seen defaults to is_higher=True."
        assert highs[1].is_higher == False, (
            "A tie (100 vs prior HIGH of 100) is not strictly higher -- "
            "is_higher must be False, not True."
        )


class TestEdgeCases:

    def test_too_little_data_returns_empty_not_crash(self, detector, synthetic_too_short_df):
        assert detector.detect_swings(synthetic_too_short_df) == []


class TestPerformanceRefactorPreservesBehavior:
    """#4b: replacing the O(n^2) prev_highs/prev_lows list rescans with
    running last_high_price/last_low_price variables must not change which
    bars get flagged as pivots, on an untied (unambiguous) fixture."""

    def test_macro_pivots_unchanged_on_representative_uptrend_fixture(self):
        from tests.technical_analysis.pattern_system.conftest import zigzag_df

        df = zigzag_df([50, 90, 72, 93, 81.84, 96, 90.24, 100], bars_between=6)
        pivots = SwingDetector(window=5).detect_swings(df)

        assert [p.index for p in pivots] == [6, 12, 18, 24, 30, 36]
        assert [p.type for p in pivots] == ["HIGH", "LOW", "HIGH", "LOW", "HIGH", "LOW"]
        assert [round(p.price, 3) for p in pivots] == [
            90.09, 71.928, 93.093, 81.758, 96.096, 90.15,
        ]
        assert [bool(p.is_higher) for p in pivots] == [True, True, True, True, True, True]
