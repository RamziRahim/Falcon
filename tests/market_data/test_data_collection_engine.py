"""
Tests for market_data/data_collection_engine.py's on_download_progress
threading -- must reach downloader.download() unchanged, not get dropped
or renamed along the way.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from market_data.data_collection_engine import DataCollectionEngine


class TestOnDownloadProgressThreading:

    def test_callback_forwarded_to_downloader_download(self):
        engine = DataCollectionEngine()
        callback = MagicMock()

        with patch("market_data.data_collection_engine.cache_synchronizer") as mock_sync, \
             patch("market_data.data_collection_engine.downloader") as mock_downloader:

            mock_sync.synchronize.return_value = MagicMock(added=[], retained=["A.NS"], added_count=0, retained_count=1, removed_count=0)
            mock_downloader.download.return_value = {}

            engine.run(symbols=["A.NS"], on_download_progress=callback)

            mock_downloader.download.assert_called_once_with(["A.NS"], on_progress=callback)

    def test_omitting_the_callback_still_works(self):
        engine = DataCollectionEngine()

        with patch("market_data.data_collection_engine.cache_synchronizer") as mock_sync, \
             patch("market_data.data_collection_engine.downloader") as mock_downloader:

            mock_sync.synchronize.return_value = MagicMock(added=[], retained=["A.NS"], added_count=0, retained_count=1, removed_count=0)
            mock_downloader.download.return_value = {}

            engine.run(symbols=["A.NS"])

            mock_downloader.download.assert_called_once_with(["A.NS"], on_progress=None)
