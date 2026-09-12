"""
Tests for market_data/market_hours.py -- the backend (Streamlit-free)
market-hours check used by same-day-only live features. Mirrors
tests/ui/test_header.py's coverage for get_market_status(), since this
module intentionally duplicates that check's logic for a different layer.
"""
from __future__ import annotations

from datetime import date, datetime
from unittest.mock import patch

import market_data.market_hours as market_hours
from market_data.market_hours import IST, is_live_market_hours


class TestIsLiveMarketHours:

    def test_weekday_during_trading_hours_is_open(self):
        with patch.object(market_hours, "get_nse_holidays", return_value=set()):
            monday_10am = IST.localize(datetime(2026, 7, 20, 10, 0))
            assert is_live_market_hours(monday_10am) is True

    def test_weekday_before_open_is_closed(self):
        with patch.object(market_hours, "get_nse_holidays", return_value=set()):
            monday_8am = IST.localize(datetime(2026, 7, 20, 8, 0))
            assert is_live_market_hours(monday_8am) is False

    def test_weekday_after_close_is_closed(self):
        with patch.object(market_hours, "get_nse_holidays", return_value=set()):
            monday_5pm = IST.localize(datetime(2026, 7, 20, 17, 0))
            assert is_live_market_hours(monday_5pm) is False

    def test_weekend_is_closed(self):
        with patch.object(market_hours, "get_nse_holidays", return_value=set()):
            saturday_noon = IST.localize(datetime(2026, 7, 25, 12, 0))
            assert is_live_market_hours(saturday_noon) is False

    def test_known_holiday_during_trading_hours_is_closed(self):
        holiday_date = date(2026, 7, 20)  # a Monday in this fixture
        with patch.object(market_hours, "get_nse_holidays", return_value={holiday_date}):
            monday_10am = IST.localize(datetime(2026, 7, 20, 10, 0))
            assert is_live_market_hours(monday_10am) is False

    def test_naive_now_treated_as_already_ist(self):
        with patch.object(market_hours, "get_nse_holidays", return_value=set()):
            naive_monday_10am = datetime(2026, 7, 20, 10, 0)
            assert is_live_market_hours(naive_monday_10am) is True
