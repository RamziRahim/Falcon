"""
Tests for ui/header.py's live index feed — get_market_status() and
get_index_quotes() (Falcon spec: real data replacing hardcoded header values).
"""
from __future__ import annotations

from datetime import date, datetime
from unittest.mock import patch

import pandas as pd
import pytest

import ui.header as header
from ui.header import IST, get_index_quotes, get_market_status, get_market_regime_snapshot


@pytest.fixture(autouse=True)
def _clear_quote_cache():
    get_index_quotes.clear()
    get_market_regime_snapshot.clear()
    yield
    get_index_quotes.clear()
    get_market_regime_snapshot.clear()


@pytest.fixture(autouse=True)
def _no_holidays_by_default():
    """
    get_market_status() now checks get_nse_holidays() too. Default it to
    an empty set so the plain weekday+hours tests below stay isolated from
    real network/cache state -- holiday-specific behavior gets its own
    tests below with an explicit mock.
    """
    with patch.object(header, "get_nse_holidays", return_value=set()):
        yield


class TestMarketStatus:

    def test_weekday_during_trading_hours_is_open(self):
        monday_10am = IST.localize(datetime(2026, 7, 20, 10, 0))
        assert get_market_status(monday_10am) == "🟢 OPEN"

    def test_weekday_before_open_is_closed(self):
        monday_8am = IST.localize(datetime(2026, 7, 20, 8, 0))
        assert get_market_status(monday_8am) == "🔴 CLOSED"

    def test_weekday_after_close_is_closed(self):
        monday_5pm = IST.localize(datetime(2026, 7, 20, 17, 0))
        assert get_market_status(monday_5pm) == "🔴 CLOSED"

    def test_weekend_is_closed(self):
        saturday_noon = IST.localize(datetime(2026, 7, 25, 12, 0))
        assert get_market_status(saturday_noon) == "🔴 CLOSED"


class TestHolidayDetection:

    def test_known_holiday_during_trading_hours_is_closed(self):
        holiday_date = date(2026, 7, 20)  # a Monday in this fixture
        with patch.object(header, "get_nse_holidays", return_value={holiday_date}):
            monday_10am = IST.localize(datetime(2026, 7, 20, 10, 0))
            assert get_market_status(monday_10am) == "🔴 CLOSED", (
                "A weekday during normal trading hours must still show "
                "CLOSED if it's a known NSE holiday."
            )

    def test_non_holiday_weekday_unaffected_by_unrelated_holidays(self):
        unrelated_holiday = date(2026, 12, 25)
        with patch.object(header, "get_nse_holidays", return_value={unrelated_holiday}):
            monday_10am = IST.localize(datetime(2026, 7, 20, 10, 0))
            assert get_market_status(monday_10am) == "🟢 OPEN"

    def test_empty_holiday_set_falls_back_to_weekday_hours_check(self):
        """The most important case: get_nse_holidays() promises to never
        raise and to return an empty set on any fetch/parse failure --
        confirms that degraded state doesn't break normal status checks."""
        with patch.object(header, "get_nse_holidays", return_value=set()):
            monday_10am = IST.localize(datetime(2026, 7, 20, 10, 0))
            assert get_market_status(monday_10am) == "🟢 OPEN"


class TestIndexQuotes:

    def test_returns_quote_per_label(self):
        with patch.object(header, "market_provider") as mock_provider:
            mock_provider.get_quote.return_value = {
                "last_price": 100.0,
                "previous_close": 95.0,
                "change_pct": 5.26,
            }
            quotes = get_index_quotes()
            assert set(quotes.keys()) == {
                "NIFTY 50", "NIFTY MIDCAP 150", "NIFTY SMALLCAP 250",
            }
            assert quotes["NIFTY 50"]["last_price"] == 100.0


def _benchmark_history(n: int = 30) -> pd.DataFrame:
    closes = [100.0 + i for i in range(n)]
    return pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=n, freq="D"),
        "Open": closes, "High": [c * 1.001 for c in closes],
        "Low": [c * 0.999 for c in closes], "Close": closes,
        "Volume": [100_000] * n,
    })


class TestMarketRegimeSnapshot:
    """get_market_regime_snapshot() -- the real NIFTY trend regime state
    (same signal decision_engine.live_scorer scores every live candidate
    against), replacing what used to be no regime info in the header at
    all."""

    def test_returns_trend_state_and_verdict(self):
        with patch.object(header, "get_benchmark_history", return_value=_benchmark_history()), \
             patch.object(header, "get_market_trend_state", return_value="UPTREND"), \
             patch.object(header, "count_distribution_days", return_value=3), \
             patch.object(header, "get_market_regime_verdict", return_value="FAVORABLE"):

            snapshot = get_market_regime_snapshot()

            assert snapshot == {"trend_state": "UPTREND", "verdict": "FAVORABLE", "distribution_days": 3}

    def test_returns_none_on_fetch_failure(self):
        with patch.object(header, "get_benchmark_history", side_effect=ConnectionError("no network")):
            assert get_market_regime_snapshot() is None

    def test_returns_none_when_distribution_days_unresolvable(self):
        with patch.object(header, "get_benchmark_history", return_value=_benchmark_history()), \
             patch.object(header, "count_distribution_days", return_value=None):
            assert get_market_regime_snapshot() is None

    def test_failed_fetch_yields_none_not_fabricated_value(self):
        with patch.object(header, "market_provider") as mock_provider:
            mock_provider.get_quote.side_effect = Exception("simulated API failure")
            quotes = get_index_quotes()
            assert quotes["NIFTY 50"] is None
