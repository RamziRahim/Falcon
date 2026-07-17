"""
Tests for ui/scan_warnings.py -- confirms per-category warnings render when
non-empty and stay silent when everything succeeded (no false "0 tickers
skipped" noise).
"""
from __future__ import annotations

from unittest.mock import patch

import ui.scan_warnings as scan_warnings
from market_data.data_collection_engine import DataCollectionResult
from technical_analysis.indicator_engine import IndicatorEngineResult


class TestNoWarningsOnSuccess:

    def test_renders_nothing_when_everything_succeeded(self):
        with patch.object(scan_warnings, "st") as mock_st:
            scan_warnings.render(
                DataCollectionResult(failed=0),
                IndicatorEngineResult(skipped_list=[], failed_list=[]),
            )
            mock_st.warning.assert_not_called()


class TestWarningsRenderWhenNonEmpty:

    def test_collection_failures_render(self):
        with patch.object(scan_warnings, "st") as mock_st:
            scan_warnings.render(
                DataCollectionResult(failed=2),
                IndicatorEngineResult(),
            )
            assert mock_st.warning.call_count == 1
            assert "2" in mock_st.warning.call_args[0][0]

    def test_skipped_list_renders_with_ticker_names(self):
        with patch.object(scan_warnings, "st") as mock_st:
            scan_warnings.render(
                DataCollectionResult(),
                IndicatorEngineResult(skipped_list=["NEWLIST.NS", "THIN.NS"]),
            )
            assert mock_st.warning.call_count == 1
            message = mock_st.warning.call_args[0][0]
            assert "NEWLIST.NS" in message
            assert "THIN.NS" in message
            assert "200" in message, "Should explain *why* -- insufficient history threshold."

    def test_failed_list_renders_with_ticker_names(self):
        with patch.object(scan_warnings, "st") as mock_st:
            scan_warnings.render(
                DataCollectionResult(),
                IndicatorEngineResult(failed_list=["BROKEN.NS"]),
            )
            assert mock_st.warning.call_count == 1
            assert "BROKEN.NS" in mock_st.warning.call_args[0][0]

    def test_all_three_categories_render_independently(self):
        with patch.object(scan_warnings, "st") as mock_st:
            scan_warnings.render(
                DataCollectionResult(failed=1),
                IndicatorEngineResult(skipped_list=["A.NS"], failed_list=["B.NS"]),
            )
            assert mock_st.warning.call_count == 3
