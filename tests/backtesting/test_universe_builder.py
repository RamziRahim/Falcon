"""
Tests for backtesting/universe_builder.py -- kept lean per this codebase's
own convention: network calls (nselib.capital_market, libutil.nse_urlfetch)
are mocked, never hit live, so these run offline and deterministically.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from backtesting.universe_builder import (
    build_moderate_backtest_universe,
    build_wide_backtest_universe,
)


def _csv_response(symbols: list[str]) -> MagicMock:
    csv_bytes = pd.DataFrame({"Symbol": symbols}).to_csv(index=False).encode()
    response = MagicMock()
    response.status_code = 200
    response.content = csv_bytes
    return response


class TestBuildModerateBacktestUniverse:

    def test_combines_nifty50_and_trimmed_midcap_with_ns_suffix(self):
        nifty50_df = pd.DataFrame({"Symbol": ["RELIANCE", "TCS"]})

        with patch("backtesting.universe_builder.capital_market") as mock_capital_market, \
             patch("backtesting.universe_builder.libutil") as mock_libutil:
            mock_capital_market.nifty50_equity_list.return_value = nifty50_df
            mock_libutil.nse_urlfetch.return_value = _csv_response(["360ONE", "3MINDIA", "ACC"])

            universe = build_moderate_backtest_universe(midcap_trim_count=2)

        assert universe == ["RELIANCE.NS", "TCS.NS", "360ONE.NS", "3MINDIA.NS"]

    def test_deduplicates_symbol_present_in_both_lists(self):
        nifty50_df = pd.DataFrame({"Symbol": ["RELIANCE"]})

        with patch("backtesting.universe_builder.capital_market") as mock_capital_market, \
             patch("backtesting.universe_builder.libutil") as mock_libutil:
            mock_capital_market.nifty50_equity_list.return_value = nifty50_df
            mock_libutil.nse_urlfetch.return_value = _csv_response(["RELIANCE", "TCS"])

            universe = build_moderate_backtest_universe(midcap_trim_count=2)

        assert universe == ["RELIANCE.NS", "TCS.NS"]

    def test_midcap_fetch_failure_raises_connection_error(self):
        nifty50_df = pd.DataFrame({"Symbol": ["RELIANCE"]})

        with patch("backtesting.universe_builder.capital_market") as mock_capital_market, \
             patch("backtesting.universe_builder.libutil") as mock_libutil:
            mock_capital_market.nifty50_equity_list.return_value = nifty50_df
            failed_response = MagicMock()
            failed_response.status_code = 503
            mock_libutil.nse_urlfetch.return_value = failed_response

            with pytest.raises(ConnectionError):
                build_moderate_backtest_universe()


class TestBuildWideBacktestUniverse:

    def test_returns_ns_suffixed_deduplicated_symbols(self):
        with patch("backtesting.universe_builder.libutil") as mock_libutil:
            mock_libutil.nse_urlfetch.return_value = _csv_response(
                ["360ONE", "3MINDIA", "ABB", "360ONE"]  # deliberate duplicate
            )

            universe = build_wide_backtest_universe()

        assert universe == ["360ONE.NS", "3MINDIA.NS", "ABB.NS"]

    def test_fetch_failure_raises_connection_error(self):
        with patch("backtesting.universe_builder.libutil") as mock_libutil:
            failed_response = MagicMock()
            failed_response.status_code = 404
            mock_libutil.nse_urlfetch.return_value = failed_response

            with pytest.raises(ConnectionError):
                build_wide_backtest_universe()

    def test_does_not_call_nifty50_equity_list(self):
        # The wide universe is the Nifty 500 list alone, not layered on
        # top of a separate Nifty 50 fetch the way the moderate universe is.
        with patch("backtesting.universe_builder.capital_market") as mock_capital_market, \
             patch("backtesting.universe_builder.libutil") as mock_libutil:
            mock_libutil.nse_urlfetch.return_value = _csv_response(["RELIANCE"])

            build_wide_backtest_universe()

            mock_capital_market.nifty50_equity_list.assert_not_called()
