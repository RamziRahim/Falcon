"""
Tests for market_data/downloader.py's on_progress callback -- fires after
EACH symbol (success or failure), so a caller can show real per-ticker
progress instead of one static message for the whole batch.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

import pandas as pd

from market_data.downloader import Downloader, cache_manager


class TestOnProgressCallback:

    def test_fires_once_per_symbol_with_running_count_and_total(self):
        provider = MagicMock()
        downloader = Downloader(provider)
        downloader._download_symbol = MagicMock(return_value=None)

        calls = []
        downloader.download(["A.NS", "B.NS", "C.NS"], on_progress=lambda c, t, s: calls.append((c, t, s)))

        assert calls == [(1, 3, "A.NS"), (2, 3, "B.NS"), (3, 3, "C.NS")]

    def test_fires_even_when_a_symbol_fails(self):
        # Progress must still advance on a failed ticker -- otherwise a
        # UI progress bar would silently freeze on any real fetch error.
        provider = MagicMock()
        downloader = Downloader(provider)
        downloader._download_symbol = MagicMock(side_effect=[Exception("boom"), None])

        calls = []
        downloader.download(["BAD.NS", "GOOD.NS"], on_progress=lambda c, t, s: calls.append((c, t, s)))

        assert calls == [(1, 2, "BAD.NS"), (2, 2, "GOOD.NS")]

    def test_on_progress_is_optional(self):
        """Must not crash when no progress callback is supplied."""
        provider = MagicMock()
        downloader = Downloader(provider)
        downloader._download_symbol = MagicMock(return_value=None)

        downloader.download(["A.NS"], on_progress=None)


class TestFreshnessCheckDoesNotSkipTodaysOwnData:
    """Real bug, confirmed live 2026-08-21: a scan run the SAME day the
    cache was last updated to (i.e. one day BEHIND today) never even
    attempted to fetch today's own bar, because the old `start_date >=
    today` check treated start_date == today as "already caught up." A
    same-day evening run (after market close, real EOD data already
    published) silently kept yesterday's cached data with no error, no
    warning -- confirmed live: cached data for GLAXO.NS and other real
    tickers stayed on the 20th despite a scan run the evening of the
    21st, after market close."""

    def test_fetches_when_cache_is_one_day_behind_today(self, monkeypatch):
        real_today = date.today()
        yesterday = real_today - timedelta(days=1)

        provider = MagicMock()
        provider.get_history.return_value = pd.DataFrame(
            {"Date": [pd.Timestamp(real_today)], "Close": [100.0]}
        )
        monkeypatch.setattr(cache_manager, "exists", lambda symbol: True)
        monkeypatch.setattr(cache_manager, "last_date", lambda symbol: pd.Timestamp(yesterday))

        downloader = Downloader(provider)
        result = downloader._download_symbol("TEST.NS")

        # The real fix: get_history WAS called, with start_date == today
        # (not skipped outright), and the (only, genuinely new) row for
        # today survived _filter_new_rows().
        provider.get_history.assert_called_once()
        _, kwargs = provider.get_history.call_args
        assert kwargs["start_date"] == real_today
        assert result is not None
        assert len(result) == 1

    def test_skips_when_cache_already_includes_today(self, monkeypatch):
        """A second same-day run (or a run with nothing new since) must
        still skip cleanly -- the fix narrows the skip condition, it
        doesn't remove it."""
        real_today = date.today()

        provider = MagicMock()
        monkeypatch.setattr(cache_manager, "exists", lambda symbol: True)
        monkeypatch.setattr(cache_manager, "last_date", lambda symbol: pd.Timestamp(real_today))

        downloader = Downloader(provider)
        result = downloader._download_symbol("TEST.NS")

        provider.get_history.assert_not_called()
        assert result is None

    def test_no_prior_cache_at_all_still_fetches_full_history(self, monkeypatch):
        """A brand-new ticker (never cached) must still fetch its full
        DEFAULT_HISTORY_YEARS window -- the fix only changes the
        already-cached comparison, not the cold-start path."""
        real_today = date.today()

        provider = MagicMock()
        provider.get_history.return_value = pd.DataFrame(
            {"Date": [pd.Timestamp(real_today)], "Close": [100.0]}
        )
        monkeypatch.setattr(cache_manager, "exists", lambda symbol: False)

        downloader = Downloader(provider)
        result = downloader._download_symbol("NEW.NS")

        provider.get_history.assert_called_once()
        assert result is not None
