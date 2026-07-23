"""
Tests for scoring/sector_map.py — matches the real class-based SectorMap
implementation (not the flat-function interface assumed pre-implementation).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


class TestManualOverridePrecedence:

    def test_override_wins_even_when_yahoo_has_different_data(self, isolated_sector_map):
        with patch("scoring.sector_map.market_provider") as mock_provider:
            mock_provider.get_company_info.return_value = {
                "sector": "Technology", "industry": "Software"
            }
            result = isolated_sector_map.get_sector("OVERRIDDEN.NS")
            assert result == "Defence", (
                f"Expected manual override to win, got '{result}'. Yahoo should "
                f"not have been consulted for a ticker present in the override file."
            )
            mock_provider.get_company_info.assert_not_called()

    def test_ticker_not_in_overrides_falls_through_to_yahoo(self, isolated_sector_map):
        with patch("scoring.sector_map.market_provider") as mock_provider:
            mock_provider.get_company_info.return_value = {
                "sector": "Healthcare", "industry": "Pharmaceuticals"
            }
            result = isolated_sector_map.get_sector("NOT_IN_OVERRIDES.NS")
            assert result == "Healthcare"
            mock_provider.get_company_info.assert_called_once()


class TestUnknownSectorFallback:

    def test_yahoo_failure_returns_unknown_not_crash(self, isolated_sector_map):
        with patch("scoring.sector_map.market_provider") as mock_provider:
            mock_provider.get_company_info.side_effect = Exception("simulated API failure")
            result = isolated_sector_map.get_sector("BROKEN_TICKER.NS")
            assert result == "Unknown"

    def test_yahoo_empty_response_handled(self, isolated_sector_map):
        with patch("scoring.sector_map.market_provider") as mock_provider:
            mock_provider.get_company_info.return_value = {}
            result = isolated_sector_map.get_sector("EMPTY_RESPONSE.NS")
            assert result == "Unknown"


class TestCaching:

    def test_repeated_calls_hit_cache_not_api(self, isolated_sector_map):
        with patch("scoring.sector_map.market_provider") as mock_provider:
            mock_provider.get_company_info.return_value = {
                "sector": "Energy", "industry": "Oil & Gas"
            }
            isolated_sector_map.get_sector("REPEATED_TICKER.NS")
            isolated_sector_map.get_sector("REPEATED_TICKER.NS")
            isolated_sector_map.get_sector("REPEATED_TICKER.NS")
            assert mock_provider.get_company_info.call_count == 1, (
                f"Expected 1 real API call across 3 lookups of the same ticker "
                f"(cached after the first), got {mock_provider.get_company_info.call_count}."
            )


class TestKnownWrongSectorFixesArePresent:
    """0.6: LTIM.NS and MCDOWELL-N.NS both resolved to 'Unknown' via Yahoo
    (confirmed against the real data/sector_map.json cache before this fix
    landed) -- reads the real repo override file directly, not the
    isolated_sector_map fixture's temp copy, so this actually regresses
    against the shipped scoring/sector_overrides.csv."""

    def test_ltim_and_mcdowell_n_have_manual_overrides(self):
        import pandas as pd

        from scoring.sector_map import OVERRIDES_PATH

        df = pd.read_csv(OVERRIDES_PATH)
        overrides = dict(zip(df["Symbol"], df["Sector"]))

        assert overrides.get("LTIM.NS") == "Technology"
        assert overrides.get("MCDOWELL-N.NS") == "Consumer Defensive"


@pytest.mark.integration
class TestRealYahooIntegration:
    """Hits the real yfinance API. Run explicitly with: pytest -m integration"""

    def test_known_large_cap_returns_correct_sector(self, isolated_sector_map):
        result = isolated_sector_map.get_sector("RELIANCE.NS")
        assert result != "Unknown"
