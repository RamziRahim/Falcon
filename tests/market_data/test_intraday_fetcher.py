"""
Tests for market_data/intraday_fetcher.py -- the thin yfinance IO shim
feeding technical_analysis/vwap_reclaim.py. Only checks its own contract
(shape of the returned DataFrame, fail-closed-to-empty on any error) --
the actual VWAP math is tested against synthetic fixtures in
tests/technical_analysis/test_vwap_reclaim.py.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from market_data.intraday_fetcher import fetch_todays_intraday_bars


def _mock_ticker(history_df: pd.DataFrame) -> MagicMock:
    ticker = MagicMock()
    ticker.history.return_value = history_df
    return ticker


class TestFetchTodaysIntradayBars:

    def test_returns_dataframe_with_datetime_column(self):
        idx = pd.date_range("2026-09-04 09:15", periods=3, freq="min", name="Datetime")
        raw = pd.DataFrame(
            {"Open": [1.0, 2.0, 3.0], "High": [1.0, 2.0, 3.0], "Low": [1.0, 2.0, 3.0],
             "Close": [1.0, 2.0, 3.0], "Volume": [10, 20, 30]},
            index=idx,
        )
        with patch("market_data.intraday_fetcher.yf.Ticker", return_value=_mock_ticker(raw)):
            result = fetch_todays_intraday_bars("DEMO.NS")

        assert "Datetime" in result.columns
        assert len(result) == 3

    def test_requests_1m_interval_and_1d_period(self):
        idx = pd.date_range("2026-09-04 09:15", periods=1, freq="min", name="Datetime")
        raw = pd.DataFrame({"Open": [1.0], "High": [1.0], "Low": [1.0], "Close": [1.0], "Volume": [10]}, index=idx)
        mock_ticker = _mock_ticker(raw)
        with patch("market_data.intraday_fetcher.yf.Ticker", return_value=mock_ticker):
            fetch_todays_intraday_bars("DEMO.NS")

        mock_ticker.history.assert_called_once_with(period="1d", interval="1m")

    def test_empty_history_returns_empty_dataframe(self):
        with patch("market_data.intraday_fetcher.yf.Ticker", return_value=_mock_ticker(pd.DataFrame())):
            result = fetch_todays_intraday_bars("DEMO.NS")

        assert result.empty

    def test_exception_returns_empty_dataframe_not_a_crash(self):
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = Exception("network error")
        with patch("market_data.intraday_fetcher.yf.Ticker", return_value=mock_ticker):
            result = fetch_todays_intraday_bars("DEMO.NS")

        assert isinstance(result, pd.DataFrame)
        assert result.empty
