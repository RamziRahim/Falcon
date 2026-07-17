"""
Tests for technical_analysis/pattern_system/market_structure.py -- trend
classification, break-of-structure, and volume-filtered liquidity sweeps.
No behavior change is spec'd for this module; these tests pin down its
existing correct behavior as a regression net.
"""
from __future__ import annotations

import pandas as pd
import pytest

from technical_analysis.pattern_system.market_structure import MarketStructureEngine


@pytest.fixture
def engine() -> MarketStructureEngine:
    return MarketStructureEngine(lookback_window=10, volume_multiplier=1.5)


class TestTrendClassification:

    def test_higher_high_and_higher_low_is_uptrend(
        self, engine, synthetic_uptrend_structure_pivots, synthetic_structure_support_df
    ):
        result = engine.analyze_structure(synthetic_structure_support_df, synthetic_uptrend_structure_pivots)
        assert result["trend_state"] == "UPTREND"

    def test_lower_high_and_lower_low_is_downtrend(
        self, engine, synthetic_downtrend_structure_pivots, synthetic_structure_support_df
    ):
        result = engine.analyze_structure(synthetic_structure_support_df, synthetic_downtrend_structure_pivots)
        assert result["trend_state"] == "DOWNTREND"

    def test_mixed_pivot_sequence_is_choppy(
        self, engine, synthetic_choppy_structure_pivots, synthetic_structure_support_df
    ):
        result = engine.analyze_structure(synthetic_structure_support_df, synthetic_choppy_structure_pivots)
        assert result["trend_state"] == "CHOPPY"


class TestLiquiditySweep:

    def test_sellside_sweep_detected(
        self, engine, synthetic_liquidity_sweep_sellside_df, synthetic_sweep_macro_pivots
    ):
        result = engine.analyze_structure(synthetic_liquidity_sweep_sellside_df, synthetic_sweep_macro_pivots)
        assert result["is_liquidity_sweep"] is True
        assert result["sweep_type"] == "SELLSIDE"

    def test_buyside_sweep_detected(
        self, engine, synthetic_liquidity_sweep_buyside_df, synthetic_sweep_macro_pivots
    ):
        result = engine.analyze_structure(synthetic_liquidity_sweep_buyside_df, synthetic_sweep_macro_pivots)
        assert result["is_liquidity_sweep"] is True
        assert result["sweep_type"] == "BUYSIDE"

    def test_no_sweep_on_boring_data(
        self, engine, synthetic_structure_support_df, synthetic_sweep_macro_pivots
    ):
        result = engine.analyze_structure(synthetic_structure_support_df, synthetic_sweep_macro_pivots)
        assert result["is_liquidity_sweep"] is False
        assert result["sweep_type"] is None


class TestEdgeCases:

    def test_no_macro_pivots_returns_default_not_crash(self, engine, synthetic_structure_support_df):
        result = engine.analyze_structure(synthetic_structure_support_df, [])
        assert result["trend_state"] == "CHOPPY"
        assert result["is_liquidity_sweep"] is False

    def test_too_little_data_returns_default_not_crash(self, engine, synthetic_uptrend_structure_pivots):
        tiny_df = pd.DataFrame({
            "Date": pd.date_range("2024-01-01", periods=3, freq="D"),
            "Open": [100, 101, 102], "High": [100, 101, 102], "Low": [100, 101, 102],
            "Close": [100, 101, 102], "Volume": [100_000] * 3,
        })
        result = engine.analyze_structure(tiny_df, synthetic_uptrend_structure_pivots)
        assert result["trend_state"] == "CHOPPY"

    def test_missing_volume_sma_20_column_is_computed_inline(self, engine, synthetic_sweep_macro_pivots):
        df = pd.DataFrame({
            "Date": pd.date_range("2024-01-01", periods=15, freq="D"),
            "Open": [100.0] * 15, "High": [100.0] * 15, "Low": [100.0] * 15, "Close": [100.0] * 15,
            "Volume": [100_000] * 15,
        })
        assert "Volume_SMA_20" not in df.columns
        result = engine.analyze_structure(df, synthetic_sweep_macro_pivots)
        assert result["trend_state"] in ("UPTREND", "DOWNTREND", "CHOPPY")
