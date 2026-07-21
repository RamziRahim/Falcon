"""
Tests for scoring/sector_indices.py -- kept lean per spec: confirm the
live-verified sector-name-to-index-name pairs resolve correctly, and
confirm an unmapped sector degrades to a graceful default rather than
crashing.
"""
from __future__ import annotations

import pandas as pd
import pytest

from scoring.sector_indices import SECTOR_INDEX_MAP, get_sector_index_history, get_sector_index_trend


class TestSectorIndexMap:

    @pytest.mark.parametrize("sector,index_name", [
        ("Technology", "NIFTY IT"),
        ("Financial Services", "NIFTY FINANCIAL SERVICES"),
        ("Healthcare", "NIFTY PHARMA"),
        ("Consumer Cyclical", "NIFTY AUTO"),
    ])
    def test_live_verified_pairs_resolve_correctly(self, sector, index_name):
        # These 4 (of the 10 in SECTOR_INDEX_MAP) were the pairs directly
        # confirmed live: sector label against real yfinance output for a
        # known ticker in that sector, index name against a real
        # capital_market.index_data() call.
        assert SECTOR_INDEX_MAP[sector] == index_name


class TestUnmappedSectorDegradesGracefully:

    def test_unmapped_sector_history_returns_none_not_crash(self):
        assert get_sector_index_history("Unknown", from_date="01-01-2024", to_date="01-02-2024") is None

    def test_unmapped_sector_trend_returns_choppy_not_crash(self):
        result = get_sector_index_trend("Unknown", pd.Timestamp("2024-01-01"), history_cache={})
        assert result == "CHOPPY"

    def test_missing_history_cache_entry_returns_choppy_not_crash(self):
        # A mapped sector, but the caller's history_cache simply doesn't
        # have an entry for it (e.g. the fetch failed upstream) --
        # must degrade the same way as a genuinely unmapped sector.
        result = get_sector_index_trend("Technology", pd.Timestamp("2024-01-01"), history_cache={})
        assert result == "CHOPPY"
