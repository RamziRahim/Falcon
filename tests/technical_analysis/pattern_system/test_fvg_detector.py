"""
Tests for technical_analysis/pattern_system/fvg_detector.py -- Fair Value
Gap detection and mitigation. No behavior change is spec'd for this module
beyond an optional, low-priority O(n^2) fix (#4b), which must not change
what gets detected -- these tests pin down its existing correct behavior.
"""
from __future__ import annotations

import pandas as pd

from technical_analysis.pattern_system.fvg_detector import FVGDetector


class TestGapDetection:

    def test_active_unmitigated_gap_matches_exact_expected_values(self, synthetic_fvg_gap_up_df):
        result = FVGDetector().detect_fvgs(synthetic_fvg_gap_up_df)
        assert result["has_active_fvg"] is True
        assert result["fvg_top"] == 105.0
        assert result["fvg_bottom"] == 100.0

    def test_mitigated_gap_is_excluded(self, synthetic_fvg_mitigated_df):
        result = FVGDetector().detect_fvgs(synthetic_fvg_mitigated_df)
        assert result["has_active_fvg"] is False
        assert result["fvg_top"] is None
        assert result["fvg_bottom"] is None

    def test_price_resting_inside_gap_is_flagged(self):
        rows = [
            {"High": 100, "Low": 95, "Close": 98},
            {"High": 102, "Low": 99, "Close": 101},
            {"High": 108, "Low": 105, "Close": 102},  # close inside [100, 105]
        ]
        df = pd.DataFrame(rows)
        df["Date"] = pd.date_range("2024-01-01", periods=len(df), freq="D")
        df["Open"] = df["Close"]
        df["Volume"] = 100_000
        result = FVGDetector().detect_fvgs(df)
        assert result["has_active_fvg"] is True
        assert result["is_price_in_fvg"] is True


class TestEdgeCases:

    def test_too_little_data_returns_default_not_crash(self):
        df = pd.DataFrame({
            "Date": pd.date_range("2024-01-01", periods=2, freq="D"),
            "Open": [100, 101], "High": [100, 101], "Low": [100, 101],
            "Close": [100, 101], "Volume": [100_000, 100_000],
        })
        result = FVGDetector().detect_fvgs(df)
        assert result["has_active_fvg"] is False
        assert result["fvg_top"] is None

    def test_no_gap_present_returns_default(self):
        closes = [100.0, 100.5, 101.0, 101.5, 102.0]
        df = pd.DataFrame({
            "Date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "Open": closes, "High": [c + 0.5 for c in closes], "Low": [c - 0.5 for c in closes],
            "Close": closes, "Volume": [100_000] * 5,
        })
        result = FVGDetector().detect_fvgs(df)
        assert result["has_active_fvg"] is False
