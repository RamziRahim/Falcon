"""
Tests for ui/header.py's live index feed — get_market_status() and
get_index_quotes() (Falcon spec: real data replacing hardcoded header values).
"""
from __future__ import annotations

from datetime import date, datetime
from unittest.mock import patch

import pytest

import ui.header as header
from ui.header import IST, get_index_quotes, get_market_status


@pytest.fixture(autouse=True)
def _clear_quote_cache():
    get_index_quotes.clear()
    yield
    get_index_quotes.clear()


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

    def test_failed_fetch_yields_none_not_fabricated_value(self):
        with patch.object(header, "market_provider") as mock_provider:
            mock_provider.get_quote.side_effect = Exception("simulated API failure")
            quotes = get_index_quotes()
            assert quotes["NIFTY 50"] is None
