"""
Tests for fundamental_analysis/corporate_engine.py -- net margin trend
(QoQ + YoY), added alongside the existing revenue/net-income growth
calculations. Reuses the same quarterly_financials data already extracted
for those -- no new yfinance call.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from fundamental_analysis.corporate_engine import CorporateEngine


def _quarterly_financials(revenues: list[float], net_incomes: list[float]) -> pd.DataFrame:
    """
    Real yfinance quarterly_financials shape: columns are quarter-end
    Timestamps (most recent first, matching .iloc[0] == latest quarter),
    index rows are financial statement line items.
    """
    n = len(revenues)
    columns = pd.date_range("2026-01-01", periods=n, freq="-3ME")[:n]
    return pd.DataFrame(
        {columns[i]: {"Total Revenue": revenues[i], "Net Income": net_incomes[i]} for i in range(n)}
    )


def _mock_stock(quarterly_financials: pd.DataFrame) -> MagicMock:
    stock = MagicMock()
    stock.quarterly_financials = quarterly_financials
    stock.calendar = None
    return stock


@pytest.fixture
def engine() -> CorporateEngine:
    return CorporateEngine()


class TestMarginCalculation:

    def test_expanding_margin_qoq_and_yoy(self, engine):
        # Q0=15% margin, Q1..Q4=10% margin -- expanding both QoQ and YoY
        qf = _quarterly_financials(
            revenues=[1000, 950, 900, 850, 800],
            net_incomes=[150, 95, 90, 85, 80],
        )
        with patch("fundamental_analysis.corporate_engine.yf.Ticker", return_value=_mock_stock(qf)):
            result = engine.get_comprehensive_fundamentals("DEMO.NS")

        assert result["net_margin_pct"] == "15.00%"
        assert result["margin_trend_qoq"] == "EXPANDING"
        assert result["margin_trend_yoy"] == "EXPANDING"

    def test_contracting_margin_qoq(self, engine):
        # Q0=5% margin, Q1=10% margin -- contracting QoQ
        qf = _quarterly_financials(
            revenues=[1000, 1000],
            net_incomes=[50, 100],
        )
        with patch("fundamental_analysis.corporate_engine.yf.Ticker", return_value=_mock_stock(qf)):
            result = engine.get_comprehensive_fundamentals("DEMO.NS")

        assert result["net_margin_pct"] == "5.00%"
        assert result["margin_trend_qoq"] == "CONTRACTING"

    def test_flat_margin_across_different_absolute_values(self, engine):
        """The easiest branch to accidentally miss: FLAT must compare the
        *ratio*, not the raw revenue/net-income values (which differ here
        even though the margin itself doesn't)."""
        qf = _quarterly_financials(
            revenues=[1000, 500],
            net_incomes=[100, 50],  # both exactly 10% margin
        )
        with patch("fundamental_analysis.corporate_engine.yf.Ticker", return_value=_mock_stock(qf)):
            result = engine.get_comprehensive_fundamentals("DEMO.NS")

        assert result["margin_trend_qoq"] == "FLAT"


class TestInsufficientHistoryForYoY:

    def test_fewer_than_5_quarters_yoy_is_data_gap(self, engine):
        qf = _quarterly_financials(
            revenues=[1000, 950, 900, 850],  # only 4 quarters
            net_incomes=[150, 95, 90, 85],
        )
        with patch("fundamental_analysis.corporate_engine.yf.Ticker", return_value=_mock_stock(qf)):
            result = engine.get_comprehensive_fundamentals("DEMO.NS")

        assert result["margin_trend_yoy"] == "DATA_GAP"
        # QoQ must still compute fine -- only YoY needs the 5th quarter
        assert result["margin_trend_qoq"] == "EXPANDING"
        assert result["net_margin_pct"] == "15.00%"


class TestZeroOrNegativeRevenueDoesNotCrash:

    def test_zero_revenue_latest_quarter_falls_back_to_data_gap(self, engine):
        qf = _quarterly_financials(
            revenues=[0, 950, 900, 850, 800],
            net_incomes=[150, 95, 90, 85, 80],
        )
        with patch("fundamental_analysis.corporate_engine.yf.Ticker", return_value=_mock_stock(qf)):
            result = engine.get_comprehensive_fundamentals("DEMO.NS")

        assert result["net_margin_pct"] == "DATA_GAP"
        assert result["margin_trend_qoq"] == "DATA_GAP"
        assert result["margin_trend_yoy"] == "DATA_GAP"

    def test_negative_revenue_falls_back_to_data_gap_not_a_flipped_sign(self, engine):
        qf = _quarterly_financials(
            revenues=[-1000, 950, 900, 850, 800],
            net_incomes=[150, 95, 90, 85, 80],
        )
        with patch("fundamental_analysis.corporate_engine.yf.Ticker", return_value=_mock_stock(qf)):
            result = engine.get_comprehensive_fundamentals("DEMO.NS")

        assert result["net_margin_pct"] == "DATA_GAP"
        assert result["margin_trend_qoq"] == "DATA_GAP"

    def test_zero_revenue_in_yoy_comparison_quarter_only(self, engine):
        """Latest quarter is fine, but the 4-quarters-ago comparison
        quarter has zero revenue -- QoQ must still work, only YoY should
        degrade."""
        qf = _quarterly_financials(
            revenues=[1000, 950, 900, 850, 0],
            net_incomes=[150, 95, 90, 85, 80],
        )
        with patch("fundamental_analysis.corporate_engine.yf.Ticker", return_value=_mock_stock(qf)):
            result = engine.get_comprehensive_fundamentals("DEMO.NS")

        assert result["margin_trend_qoq"] == "EXPANDING"
        assert result["margin_trend_yoy"] == "DATA_GAP"


class TestFallbackPacketIncludesMarginKeys:

    def test_fallback_packet_has_margin_keys_when_no_financials(self, engine):
        stock = MagicMock()
        stock.quarterly_financials = pd.DataFrame()
        with patch("fundamental_analysis.corporate_engine.yf.Ticker", return_value=stock):
            result = engine.get_comprehensive_fundamentals("DEMO.NS")

        assert result["net_margin_pct"] == "DATA_GAP"
        assert result["margin_trend_qoq"] == "DATA_GAP"
        assert result["margin_trend_yoy"] == "DATA_GAP"
