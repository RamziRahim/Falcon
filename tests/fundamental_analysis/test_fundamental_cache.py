"""
Tests for fundamental_analysis/fundamental_cache.py — cache-then-check-staleness
wrapper around fundamental_engine.get_complete_data_packet(), mirroring
scoring/sector_map.py's test pattern.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest


def _packet(rev_yoy="+18.40%", d_e="42.50%"):
    return {
        "ticker_identity": "DUMMY.NS",
        "quarterly_financials": {"revenue_yoy_quarterly_growth": rev_yoy},
        "balance_sheet_vitals": {"debt_to_equity": d_e},
        "shareholding_distribution": {},
        "recent_catalysts": [],
    }


class TestCaching:

    def test_repeated_calls_hit_cache_not_api(self, isolated_fundamental_cache):
        with patch("fundamental_analysis.fundamental_cache.fundamental_engine") as mock_engine, \
             patch("fundamental_analysis.fundamental_cache.metrics_engine") as mock_metrics:
            mock_engine.get_complete_data_packet.return_value = _packet()
            mock_metrics.get_roce.return_value = "12.50%"

            isolated_fundamental_cache.get_fundamentals("DUMMY.NS")
            isolated_fundamental_cache.get_fundamentals("DUMMY.NS")
            isolated_fundamental_cache.get_fundamentals("DUMMY.NS")

            assert mock_engine.get_complete_data_packet.call_count == 1, (
                f"Expected 1 real fetch across 3 lookups of the same ticker "
                f"(cached after the first), got {mock_engine.get_complete_data_packet.call_count}."
            )

    def test_stale_entry_triggers_refetch(self, isolated_fundamental_cache):
        with patch("fundamental_analysis.fundamental_cache.fundamental_engine") as mock_engine, \
             patch("fundamental_analysis.fundamental_cache.metrics_engine") as mock_metrics:
            mock_engine.get_complete_data_packet.return_value = _packet()
            mock_metrics.get_roce.return_value = "12.50%"

            isolated_fundamental_cache.get_fundamentals("STALE.NS")

            isolated_fundamental_cache._cache["STALE.NS"]["fetched_at"] = (
                datetime.now() - timedelta(days=8)
            ).isoformat()

            isolated_fundamental_cache.get_fundamentals("STALE.NS")

            assert mock_engine.get_complete_data_packet.call_count == 2


class TestFetchFailureFallback:

    def test_failure_serves_stale_cache_rather_than_fabricating(self, isolated_fundamental_cache):
        with patch("fundamental_analysis.fundamental_cache.fundamental_engine") as mock_engine, \
             patch("fundamental_analysis.fundamental_cache.metrics_engine") as mock_metrics:
            mock_engine.get_complete_data_packet.return_value = _packet(rev_yoy="+9.00%")
            mock_metrics.get_roce.return_value = "8.00%"
            isolated_fundamental_cache.get_fundamentals("FLAKY.NS", force_refresh=True)

            mock_engine.get_complete_data_packet.side_effect = Exception("rate limited")
            result = isolated_fundamental_cache.get_fundamentals("FLAKY.NS", force_refresh=True)

            assert result["revenue_yoy_quarterly_growth"] == "+9.00%", (
                "Expected stale cache to be served on fetch failure, not a fabricated value."
            )

    def test_failure_with_no_cache_returns_na_packet(self, isolated_fundamental_cache):
        with patch("fundamental_analysis.fundamental_cache.fundamental_engine") as mock_engine:
            mock_engine.get_complete_data_packet.side_effect = Exception("network down")

            result = isolated_fundamental_cache.get_fundamentals("NEVER_SEEN.NS")

            assert result["roce"] == "N/A"
            assert result["debt_to_equity"] == "N/A"


@pytest.mark.integration
class TestRealYahooIntegration:
    """Hits the real yfinance API. Run explicitly with: pytest -m integration"""

    def test_known_large_cap_returns_data(self, isolated_fundamental_cache):
        result = isolated_fundamental_cache.get_fundamentals("RELIANCE.NS")
        assert result["debt_to_equity"] != "N/A" or result["roce"] != "N/A"
