"""
Tests for market_data/downloader.py's on_progress callback -- fires after
EACH symbol (success or failure), so a caller can show real per-ticker
progress instead of one static message for the whole batch.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from market_data.downloader import Downloader


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
