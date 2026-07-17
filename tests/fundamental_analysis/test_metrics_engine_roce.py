"""
Tests for fundamental_analysis/metrics_engine.py's get_roce() — synthetic
statements with known-correct answers. No real network calls in the default
suite, mirroring scoring/sector_map.py's test pattern.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from fundamental_analysis.metrics_engine import MetricsEngine


def _statement(period_values: dict) -> pd.DataFrame:
    """Builds a yfinance-shaped statement: index=row labels, columns=periods."""
    return pd.DataFrame(period_values)


@pytest.fixture
def engine() -> MetricsEngine:
    return MetricsEngine()


class TestRoceKnownGoodCalculation:

    def test_matches_hand_computed_answer(self, engine):
        # EBIT=100, Total Assets=1000, Current Liabilities=200 -> 100/800 = 12.5%
        financials = _statement({
            pd.Timestamp("2026-03-31"): {"Operating Income": 100.0},
            pd.Timestamp("2025-03-31"): {"Operating Income": 90.0},
        })
        balance_sheet = _statement({
            pd.Timestamp("2026-03-31"): {"Total Assets": 1000.0, "Current Liabilities": 200.0},
            pd.Timestamp("2025-03-31"): {"Total Assets": 900.0, "Current Liabilities": 180.0},
        })

        mock_stock = MagicMock()
        mock_stock.financials = financials
        mock_stock.balance_sheet = balance_sheet

        with patch("fundamental_analysis.metrics_engine.yf.Ticker", return_value=mock_stock):
            result = engine.get_roce("SYNTHETIC.NS")

        assert result == "12.50%"

    def test_excludes_non_current_liabilities_row(self, engine):
        financials = _statement({
            pd.Timestamp("2026-03-31"): {"Operating Income": 100.0},
        })
        balance_sheet = _statement({
            pd.Timestamp("2026-03-31"): {
                "Total Assets": 1000.0,
                "Current Liabilities": 200.0,
                "Total Non Current Liabilities Net Minority Interest": 700.0,
            },
        })

        mock_stock = MagicMock()
        mock_stock.financials = financials
        mock_stock.balance_sheet = balance_sheet

        with patch("fundamental_analysis.metrics_engine.yf.Ticker", return_value=mock_stock):
            result = engine.get_roce("SYNTHETIC.NS")

        # Would be 100/(1000-700)=33.33% if the non-current row were matched by mistake
        assert result == "12.50%"


class TestRoceMissingDataFallback:

    def test_missing_operating_income_row_returns_na_not_crash(self, engine):
        financials = _statement({
            pd.Timestamp("2026-03-31"): {"Total Revenue": 500.0},
        })
        balance_sheet = _statement({
            pd.Timestamp("2026-03-31"): {"Total Assets": 1000.0, "Current Liabilities": 200.0},
        })

        mock_stock = MagicMock()
        mock_stock.financials = financials
        mock_stock.balance_sheet = balance_sheet
        mock_stock.quarterly_financials = pd.DataFrame()
        mock_stock.quarterly_balance_sheet = pd.DataFrame()

        with patch("fundamental_analysis.metrics_engine.yf.Ticker", return_value=mock_stock):
            result = engine.get_roce("SYNTHETIC.NS")

        assert result == "N/A"

    def test_falls_back_to_quarterly_when_annual_missing(self, engine):
        quarterly_financials = _statement({
            pd.Timestamp("2026-06-30"): {"Operating Income": 100.0},
        })
        quarterly_balance_sheet = _statement({
            pd.Timestamp("2026-06-30"): {"Total Assets": 1000.0, "Current Liabilities": 200.0},
        })

        mock_stock = MagicMock()
        mock_stock.financials = pd.DataFrame()
        mock_stock.balance_sheet = pd.DataFrame()
        mock_stock.quarterly_financials = quarterly_financials
        mock_stock.quarterly_balance_sheet = quarterly_balance_sheet

        with patch("fundamental_analysis.metrics_engine.yf.Ticker", return_value=mock_stock):
            result = engine.get_roce("SYNTHETIC.NS")

        assert result == "12.50%"

    def test_yfinance_exception_returns_na_not_crash(self, engine):
        with patch(
            "fundamental_analysis.metrics_engine.yf.Ticker",
            side_effect=Exception("rate limited"),
        ):
            result = engine.get_roce("BROKEN.NS")

        assert result == "N/A"


@pytest.mark.integration
class TestRealYahooIntegration:
    """Hits the real yfinance API. Run explicitly with: pytest -m integration"""

    def test_known_large_cap_returns_a_number_or_na(self, engine):
        result = engine.get_roce("RELIANCE.NS")
        assert result == "N/A" or result.endswith("%")
