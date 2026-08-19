"""
Tests for fundamental_analysis/corporate_engine.py -- net margin trend
QoQ (still real, Yahoo-computed) plus revenue/net-income growth. As of
docs/known_data_issues.md item #4, margin_trend_yoy itself is no longer
computed here at all -- it's a pass-through from the Screener
fundamentals store (fundamental_analysis/screener_fundamentals_store.py),
sourced independently of whether the Yahoo quarterly_financials fetch
below succeeds. Every margin_trend_yoy assertion below mocks the store
function explicitly and checks pass-through, rather than asserting on a
Yahoo-derived value this file no longer computes.
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


@pytest.fixture(autouse=True)
def _stub_margin_trend_yoy_store(monkeypatch):
    """margin_trend_yoy is sourced independently of everything else in
    this file (see corporate_engine.py's own docstring) -- stubbed to a
    fixed, obviously-not-Yahoo-derived value by default so every test
    below that doesn't care about it specifically isn't coupled to
    whatever's in the real data/screener_fundamentals_store.json.
    Tests that DO care override this explicitly."""
    monkeypatch.setattr(
        "fundamental_analysis.corporate_engine.get_margin_trend_yoy",
        lambda ticker: "STUBBED_TREND",
    )


class TestMarginCalculationQoQ:
    """QoQ margin trend/net_margin_pct are still real, unchanged Yahoo
    computations -- only the YoY variant moved to the Screener store."""

    def test_expanding_margin_qoq(self, engine):
        # Q0=15% margin, Q1=10% margin -- expanding QoQ
        qf = _quarterly_financials(
            revenues=[1000, 950, 900, 850, 800],
            net_incomes=[150, 95, 90, 85, 80],
        )
        with patch("fundamental_analysis.corporate_engine.yf.Ticker", return_value=_mock_stock(qf)):
            result = engine.get_comprehensive_fundamentals("DEMO.NS")

        assert result["net_margin_pct"] == "15.00%"
        assert result["margin_trend_qoq"] == "EXPANDING"

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

    def test_negative_revenue_falls_back_to_data_gap_not_a_flipped_sign(self, engine):
        qf = _quarterly_financials(
            revenues=[-1000, 950, 900, 850, 800],
            net_incomes=[150, 95, 90, 85, 80],
        )
        with patch("fundamental_analysis.corporate_engine.yf.Ticker", return_value=_mock_stock(qf)):
            result = engine.get_comprehensive_fundamentals("DEMO.NS")

        assert result["net_margin_pct"] == "DATA_GAP"
        assert result["margin_trend_qoq"] == "DATA_GAP"


class TestRevenueRowExcludesCostOfRevenue:
    """Regression test using HAPPYFORGE.NS's real yfinance figures (pulled
    live and hand-verified 2026-08-17) -- the exact case that caught this
    bug while spot-checking the fundamentals behind a live EXECUTE signal.
    yfinance's own quarterly_financials index contains BOTH 'Total
    Revenue' and 'Cost Of Revenue'/'Reconciled Cost Of Revenue' -- all
    three contain the substring "Revenue", and the Cost-of-Revenue rows
    sort BEFORE 'Total Revenue' in yfinance's own column order. The
    unguarded `"Revenue" in x` match picked rev_label[0] == a Cost-of-
    Revenue row, computing net_margin_pct as net_income/COGS (51.76%)
    instead of net_income/real_revenue (20.35%) -- confirmed independently
    against yfinance's own info['revenueGrowth'] (0.27, close to the real
    +27.69% YoY growth, not the wrong +21.41% the bug produced)."""

    def test_excludes_cost_of_revenue_row(self, engine):
        # Row order matters, not just presence -- real yfinance data has
        # "Reconciled Cost Of Revenue" / "Cost Of Revenue" BEFORE "Total
        # Revenue" in the index, which is why the unguarded match picked
        # them (a dict literal alone wouldn't reproduce this).
        qf = pd.DataFrame(
            {
                pd.Timestamp("2026-06-30"): [1_766_924_000.0, 1_766_924_000.0, 914_613_000.0, 4_494_223_000.0],
                pd.Timestamp("2026-03-31"): [1_722_878_000.0, 1_722_878_000.0, 835_538_000.0, 4_238_397_000.0],
            },
            index=["Reconciled Cost Of Revenue", "Cost Of Revenue", "Net Income", "Total Revenue"],
        )
        with patch("fundamental_analysis.corporate_engine.yf.Ticker", return_value=_mock_stock(qf)):
            result = engine.get_comprehensive_fundamentals("HAPPYFORGE.NS")

        # Real: 914,613,000 / 4,494,223,000 = 20.35%.
        # Before the fix: rev_label[0] picked a Cost-of-Revenue row ->
        # 914,613,000 / 1,766,924,000 = 51.76%.
        assert result["net_margin_pct"] == "20.35%"


class TestFallbackPacketIncludesMarginKeys:

    def test_fallback_packet_has_margin_keys_when_no_financials(self, engine):
        stock = MagicMock()
        stock.quarterly_financials = pd.DataFrame()
        with patch("fundamental_analysis.corporate_engine.yf.Ticker", return_value=stock):
            result = engine.get_comprehensive_fundamentals("DEMO.NS")

        assert result["net_margin_pct"] == "DATA_GAP"
        assert result["margin_trend_qoq"] == "DATA_GAP"


class TestMarginTrendYoySourcedFromScreenerStore:
    """margin_trend_yoy (docs/known_data_issues.md item #4): no longer
    computed from Yahoo quarterly_financials at all -- a pure pass-through
    from the Screener fundamentals store, sourced BEFORE the Yahoo fetch
    even runs and independent of whether that fetch succeeds."""

    def test_pass_through_value_on_successful_yahoo_fetch(self, engine, monkeypatch):
        monkeypatch.setattr(
            "fundamental_analysis.corporate_engine.get_margin_trend_yoy",
            lambda ticker: "EXPANDING",
        )
        qf = _quarterly_financials(
            revenues=[1000, 950, 900, 850, 800],
            net_incomes=[150, 95, 90, 85, 80],
        )
        with patch("fundamental_analysis.corporate_engine.yf.Ticker", return_value=_mock_stock(qf)):
            result = engine.get_comprehensive_fundamentals("DEMO.NS")

        assert result["margin_trend_yoy"] == "EXPANDING"

    def test_pass_through_value_even_when_yahoo_fetch_fails_entirely(self, engine, monkeypatch):
        """The old fallback_packet hardcoded margin_trend_yoy to
        "DATA_GAP" -- now it must still reflect the store's real value
        (or None) even when the rest of the Yahoo fetch has nothing."""
        monkeypatch.setattr(
            "fundamental_analysis.corporate_engine.get_margin_trend_yoy",
            lambda ticker: "CONTRACTING",
        )
        stock = MagicMock()
        stock.quarterly_financials = pd.DataFrame()
        with patch("fundamental_analysis.corporate_engine.yf.Ticker", return_value=stock):
            result = engine.get_comprehensive_fundamentals("DEMO.NS")

        assert result["margin_trend_yoy"] == "CONTRACTING"
        # Everything else on this path is still an honest gap.
        assert result["net_margin_pct"] == "DATA_GAP"

    def test_none_from_store_passes_through_as_none_not_a_fabricated_value(self, engine, monkeypatch):
        monkeypatch.setattr(
            "fundamental_analysis.corporate_engine.get_margin_trend_yoy",
            lambda ticker: None,
        )
        qf = _quarterly_financials(
            revenues=[1000, 950, 900, 850, 800],
            net_incomes=[150, 95, 90, 85, 80],
        )
        with patch("fundamental_analysis.corporate_engine.yf.Ticker", return_value=_mock_stock(qf)):
            result = engine.get_comprehensive_fundamentals("DEMO.NS")

        assert result["margin_trend_yoy"] is None
