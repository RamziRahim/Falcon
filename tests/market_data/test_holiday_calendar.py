"""
Tests for market_data/holiday_calendar.py -- NSE equity holiday calendar,
cache-then-check-staleness (mirroring scoring/sector_map.py's pattern).

_parse_holiday_response()'s expected input shape was confirmed via a real,
live call to nselib.trading_holiday_calendar() (not guessed): a DataFrame
with 'Product' and 'tradingDate' columns, tradingDate formatted like
"26-Jan-2026". Fixtures below mirror that confirmed shape.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

import market_data.holiday_calendar as holiday_calendar
from market_data.holiday_calendar import _parse_holiday_response, get_nse_holidays


def _real_shape_response() -> pd.DataFrame:
    """Mirrors the real nselib.trading_holiday_calendar() shape confirmed
    via a live call: multiple market segments in one frame, each with its
    own holiday list."""
    return pd.DataFrame({
        "Product": ["Equities", "Equities", "Equity Derivatives", "Corporate Bonds"],
        "tradingDate": ["26-Jan-2026", "25-Dec-2026", "26-Jan-2026", "01-Jan-2026"],
        "weekDay": ["Monday", "Friday", "Monday", "Thursday"],
        "description": ["Republic Day", "Christmas", "Republic Day", "New Year"],
        "Sr_no": [1, 2, 1, 1],
    })


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    """Points the module's cache path at a temp file instead of the real
    data/nse_holidays_cache.json."""
    monkeypatch.setattr(holiday_calendar, "CACHE_PATH", tmp_path / "nse_holidays_test_cache.json")
    return tmp_path


class TestParseHolidayResponse:

    def test_filters_to_equities_segment_only(self):
        holidays = _parse_holiday_response(_real_shape_response())
        # Only 2 "Equities" rows -- Equity Derivatives / Corporate Bonds excluded
        assert holidays == {date(2026, 1, 26), date(2026, 12, 25)}

    def test_other_segments_do_not_leak_in(self):
        holidays = _parse_holiday_response(_real_shape_response())
        assert date(2026, 1, 1) not in holidays, (
            "01-Jan-2026 only appears under 'Corporate Bonds' in the "
            "fixture -- it must not leak into the equity holiday set."
        )


class TestCachingBehavior:

    def test_repeated_calls_within_refresh_window_do_not_refetch(self, isolated_cache):
        with patch.object(holiday_calendar, "trading_holiday_calendar") as mock_fetch:
            mock_fetch.return_value = _real_shape_response()

            get_nse_holidays()
            get_nse_holidays()
            get_nse_holidays()

            assert mock_fetch.call_count == 1, (
                f"Expected 1 live fetch across 3 calls within the refresh "
                f"window (cached after the first), got {mock_fetch.call_count}."
            )

    def test_stale_cache_triggers_refetch(self, isolated_cache):
        with patch.object(holiday_calendar, "trading_holiday_calendar") as mock_fetch:
            mock_fetch.return_value = _real_shape_response()

            get_nse_holidays()

            # Simulate the cache aging past REFRESH_INTERVAL_DAYS
            import json
            with open(holiday_calendar.CACHE_PATH, "r", encoding="utf-8") as fh:
                cached = json.load(fh)
            cached["fetched_at"] = (
                datetime.now() - timedelta(days=holiday_calendar.REFRESH_INTERVAL_DAYS + 1)
            ).isoformat()
            with open(holiday_calendar.CACHE_PATH, "w", encoding="utf-8") as fh:
                json.dump(cached, fh)

            get_nse_holidays()

            assert mock_fetch.call_count == 2

    def test_cached_holidays_match_original_fetch(self, isolated_cache):
        with patch.object(holiday_calendar, "trading_holiday_calendar") as mock_fetch:
            mock_fetch.return_value = _real_shape_response()

            first = get_nse_holidays()
            second = get_nse_holidays()

            assert first == second == {date(2026, 1, 26), date(2026, 12, 25)}


class TestFallbackNeverCrashes:
    """The most important tests: the live response shape was unconfirmed
    when this was designed. The fallback path is what protects production
    from that uncertainty."""

    def test_fetch_exception_falls_back_to_empty_set(self, isolated_cache):
        with patch.object(holiday_calendar, "trading_holiday_calendar") as mock_fetch:
            mock_fetch.side_effect = Exception("simulated network failure")

            holidays = get_nse_holidays()

            assert holidays == set()

    def test_unexpected_shape_falls_back_to_empty_set_not_crash(self, isolated_cache):
        with patch.object(holiday_calendar, "trading_holiday_calendar") as mock_fetch:
            # No 'Product'/'tradingDate' columns at all -- e.g. nselib
            # changes its return type entirely in some future version.
            mock_fetch.return_value = pd.DataFrame({"unexpected": [1, 2, 3]})

            holidays = get_nse_holidays()

            assert holidays == set()

    def test_empty_dataframe_falls_back_to_empty_set(self, isolated_cache):
        with patch.object(holiday_calendar, "trading_holiday_calendar") as mock_fetch:
            mock_fetch.return_value = pd.DataFrame(columns=["Product", "tradingDate"])

            holidays = get_nse_holidays()

            assert holidays == set()
