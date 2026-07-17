"""
Tests for market_data/providers/yahoo_provider.py get_quote() — a lightweight
fast_info-based quote snapshot for the header's live index feed (Falcon spec).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from market_data.exceptions import MarketDataError
from market_data.providers.yahoo_provider import YahooProvider


def _mock_ticker(fast_info: dict) -> MagicMock:
    ticker = MagicMock()
    ticker.fast_info = fast_info
    return ticker


class TestGetQuoteMath:

    def test_change_pct_known_answer(self):
        with patch("market_data.providers.yahoo_provider.yf.Ticker") as mock_ticker_cls:
            mock_ticker_cls.return_value = _mock_ticker(
                {"last_price": 105, "previous_close": 100}
            )
            result = YahooProvider().get_quote("^NSEI")
            assert result["last_price"] == 105
            assert result["previous_close"] == 100
            assert result["change_pct"] == pytest.approx(5.00)


class TestGetQuoteMissingData:

    def test_missing_last_price_raises(self):
        with patch("market_data.providers.yahoo_provider.yf.Ticker") as mock_ticker_cls:
            mock_ticker_cls.return_value = _mock_ticker({"previous_close": 100})
            with pytest.raises(MarketDataError):
                YahooProvider().get_quote("^NSEI")

    def test_missing_previous_close_raises(self):
        with patch("market_data.providers.yahoo_provider.yf.Ticker") as mock_ticker_cls:
            mock_ticker_cls.return_value = _mock_ticker({"last_price": 105})
            with pytest.raises(MarketDataError):
                YahooProvider().get_quote("^NSEI")

    def test_zero_previous_close_raises_not_divides(self):
        with patch("market_data.providers.yahoo_provider.yf.Ticker") as mock_ticker_cls:
            mock_ticker_cls.return_value = _mock_ticker(
                {"last_price": 105, "previous_close": 0}
            )
            with pytest.raises(MarketDataError):
                YahooProvider().get_quote("^NSEI")


@pytest.mark.integration
class TestRealYahooIntegration:
    """Hits the real yfinance API. Run explicitly with: pytest -m integration"""

    def test_known_index_returns_quote(self):
        result = YahooProvider().get_quote("^NSEI")
        assert result["last_price"] > 0
