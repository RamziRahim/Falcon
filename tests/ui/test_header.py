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
from ui.header import (
    IST,
    compute_category_breakdown,
    format_category_breakdown_label,
    format_last_scan_label,
    format_tickers_screened_label,
    get_index_quotes,
    get_market_status,
    get_market_regime_snapshot,
)


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


class TestLastScanLabels:
    """format_last_scan_label() / format_tickers_screened_label() -- pure
    formatting logic pulled out of render() specifically so it's directly
    testable (this module's existing convention: only pure functions get
    unit tests here, not render()'s own widget-drawing)."""

    def test_never_scanned_shows_honest_never_state(self):
        assert format_last_scan_label(None) == "Last scan: never"

    def test_completed_timestamp_is_formatted_with_ist_suffix(self):
        completed_at = IST.localize(datetime(2026, 8, 18, 0, 15))
        assert format_last_scan_label(completed_at) == "Last scan: 18 Aug, 00:15 IST"

    def test_no_ticker_count_yet_returns_none_not_a_string(self):
        # None (never scanned) must stay distinguishable from "0 tickers
        # screened" (scanned, found nothing) -- both are real, different
        # states.
        assert format_tickers_screened_label(None) is None

    def test_ticker_count_is_included_in_the_label(self):
        assert format_tickers_screened_label(50) == "50 tickers screened from Leadership query"

    def test_zero_tickers_screened_is_a_real_distinct_state(self):
        assert format_tickers_screened_label(0) == "0 tickers screened from Leadership query"


class TestCategoryBreakdown:
    """compute_category_breakdown() / format_category_breakdown_label() --
    the full EXECUTE/WATCHLIST/MONITOR/AVOID funnel, shown regardless of
    how many candidates actually reached EXECUTE/WATCHLIST (same fix
    already applied to the sector rotation panel)."""

    def test_counts_sum_to_total_screened(self):
        records_df = pd.DataFrame({
            "category": [
                "EXECUTE", "EXECUTE",
                "ALERT_WATCHLIST", "ALERT_WATCHLIST", "ALERT_WATCHLIST", "ALERT_WATCHLIST", "ALERT_WATCHLIST",
                *(["MONITOR"] * 12),
                *(["AVOID"] * 31),
            ],
        })
        counts = compute_category_breakdown(records_df)

        assert counts == {"EXECUTE": 2, "ALERT_WATCHLIST": 5, "MONITOR": 12, "AVOID": 31}
        assert sum(counts.values()) == len(records_df) == 50

    def test_empty_records_df_gives_all_zero_counts_not_a_crash(self):
        assert compute_category_breakdown(pd.DataFrame()) == {
            "EXECUTE": 0, "ALERT_WATCHLIST": 0, "MONITOR": 0, "AVOID": 0,
        }

    def test_missing_category_column_gives_all_zero_counts_not_a_crash(self):
        """Defensive: records_df before score_live_candidates() has run
        yet (no "category" column) shouldn't raise a KeyError."""
        assert compute_category_breakdown(pd.DataFrame({"Symbol": ["ABC.NS"]})) == {
            "EXECUTE": 0, "ALERT_WATCHLIST": 0, "MONITOR": 0, "AVOID": 0,
        }

    def test_label_is_none_before_the_first_scan_ever_runs(self):
        assert format_category_breakdown_label(None, None) is None

    def test_label_renders_even_when_execute_and_watchlist_are_both_zero(self):
        """The exact regression this pins: a quiet-market scan (0 EXECUTE,
        0 WATCHLIST) must still show its real MONITOR/AVOID counts, not
        disappear the way a candidate-tier-gated line would."""
        counts = {"EXECUTE": 0, "ALERT_WATCHLIST": 0, "MONITOR": 12, "AVOID": 38}

        label = format_category_breakdown_label(counts, last_scan_ticker_count=50)

        assert label == "50 screened → 0 EXECUTE · 0 WATCHLIST · 12 MONITOR · 38 AVOID"

    def test_label_uses_watchlist_not_alert_watchlist_display_name(self):
        counts = {"EXECUTE": 2, "ALERT_WATCHLIST": 5, "MONITOR": 12, "AVOID": 31}

        label = format_category_breakdown_label(counts, last_scan_ticker_count=50)

        assert "ALERT_WATCHLIST" not in label
        assert "5 WATCHLIST" in label

    def test_zero_screened_scan_still_renders_a_real_all_zero_line(self):
        counts = compute_category_breakdown(pd.DataFrame())

        label = format_category_breakdown_label(counts, last_scan_ticker_count=0)

        assert label == "0 screened → 0 EXECUTE · 0 WATCHLIST · 0 MONITOR · 0 AVOID"


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
