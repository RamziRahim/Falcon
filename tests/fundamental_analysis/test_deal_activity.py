"""
Tests for fundamental_analysis/deal_activity.py -- bulk/block deal BUY-side
detection. Buy/Sell value format ("BUY"/"SELL", plain uppercase strings,
not "B"/"S" or mixed case) and column names both confirmed via a live call
to nselib's capital_market.bulk_deal_data()/block_deals_data().
"""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

import fundamental_analysis.deal_activity as deal_activity
from fundamental_analysis.deal_activity import get_recent_institutional_activity


def _deals_df(rows: list[dict]) -> pd.DataFrame:
    """Real column shape confirmed live: Date "DD-MON-YYYY", QuantityTraded
    Indian-comma-formatted (e.g. "1,71,14,604")."""
    return pd.DataFrame(rows)


def _row(symbol="DEMO", date="15-JUL-2026", side="BUY", qty="1,00,000"):
    return {
        "Date": date, "Symbol": symbol, "SecurityName": "Demo Ltd",
        "ClientName": "Some Fund", "Buy/Sell": side, "QuantityTraded": qty,
        "TradePrice/Wght.Avg.Price": "100.00", "Remarks": "-",
    }


@pytest.fixture
def no_deals():
    return pd.DataFrame(columns=[
        "Date", "Symbol", "SecurityName", "ClientName", "Buy/Sell",
        "QuantityTraded", "TradePrice/Wght.Avg.Price", "Remarks",
    ])


class TestDirectionDistinguishing:

    def test_buy_and_sell_for_same_ticker_only_buy_counts(self, no_deals):
        """A ticker with both a BUY and a SELL entry -- must report the
        BUY, not be confused by the SELL row also matching the symbol."""
        bulk = _deals_df([
            _row(side="SELL", qty="5,00,000", date="10-JUL-2026"),
            _row(side="BUY", qty="2,00,000", date="12-JUL-2026"),
        ])
        with patch.object(deal_activity.capital_market, "bulk_deal_data", return_value=bulk), \
             patch.object(deal_activity.capital_market, "block_deals_data", return_value=no_deals):
            result = get_recent_institutional_activity("DEMO.NS", lookback_days=30)

        assert result["has_buy_activity"] is True
        assert result["latest_buy_quantity"] == 200_000.0
        assert result["source"] == "bulk"

    def test_sell_only_reports_no_buy_activity(self, no_deals):
        bulk = _deals_df([_row(side="SELL", qty="5,00,000")])
        with patch.object(deal_activity.capital_market, "bulk_deal_data", return_value=bulk), \
             patch.object(deal_activity.capital_market, "block_deals_data", return_value=no_deals):
            result = get_recent_institutional_activity("DEMO.NS", lookback_days=30)

        assert result["has_buy_activity"] is False
        assert result["latest_buy_date"] is None
        assert result["latest_buy_quantity"] is None

    def test_most_recent_buy_wins_across_bulk_and_block(self, no_deals):
        bulk = _deals_df([_row(side="BUY", qty="1,00,000", date="01-JUL-2026")])
        block = _deals_df([_row(side="BUY", qty="9,00,000", date="15-JUL-2026")])
        with patch.object(deal_activity.capital_market, "bulk_deal_data", return_value=bulk), \
             patch.object(deal_activity.capital_market, "block_deals_data", return_value=block):
            result = get_recent_institutional_activity("DEMO.NS", lookback_days=30)

        assert result["latest_buy_quantity"] == 900_000.0
        assert result["source"] == "block"


class TestNoActivity:

    def test_no_deals_in_window_returns_clear_no_activity(self, no_deals):
        with patch.object(deal_activity.capital_market, "bulk_deal_data", return_value=no_deals), \
             patch.object(deal_activity.capital_market, "block_deals_data", return_value=no_deals):
            result = get_recent_institutional_activity("NODEALS.NS", lookback_days=30)

        assert result == {
            "has_buy_activity": False,
            "latest_buy_date": None,
            "latest_buy_quantity": None,
            "source": None,
        }

    def test_ticker_not_present_in_deals_at_all(self, no_deals):
        bulk = _deals_df([_row(symbol="OTHERTICKER", side="BUY")])
        with patch.object(deal_activity.capital_market, "bulk_deal_data", return_value=bulk), \
             patch.object(deal_activity.capital_market, "block_deals_data", return_value=no_deals):
            result = get_recent_institutional_activity("DEMO.NS", lookback_days=30)

        assert result["has_buy_activity"] is False


class TestGracefulFallback:

    def test_fetch_exception_returns_no_activity_not_crash(self):
        with patch.object(deal_activity.capital_market, "bulk_deal_data", side_effect=Exception("network error")), \
             patch.object(deal_activity.capital_market, "block_deals_data", side_effect=Exception("network error")):
            result = get_recent_institutional_activity("DEMO.NS", lookback_days=30)

        assert result["has_buy_activity"] is False

    def test_symbol_suffix_normalized(self, no_deals):
        """.NS suffix must be stripped before matching against NSE's raw
        Symbol column."""
        bulk = _deals_df([_row(symbol="DEMO", side="BUY")])
        with patch.object(deal_activity.capital_market, "bulk_deal_data", return_value=bulk) as mock_bulk, \
             patch.object(deal_activity.capital_market, "block_deals_data", return_value=no_deals):
            result = get_recent_institutional_activity("DEMO.NS", lookback_days=30)

        assert result["has_buy_activity"] is True
        mock_bulk.assert_called_once()
