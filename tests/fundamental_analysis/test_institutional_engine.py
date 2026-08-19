"""
Test for fundamental_analysis/institutional_engine.py's
get_shareholding_profile_with_trend() -- confirms the Yahoo-sourced
snapshot and the Screener-store-sourced trend merge into one dict
without either clobbering the other.

As of docs/known_data_issues.md item #4, the trend fields no longer come
from a separate per-ticker Screener.in company-page visit
(get_shareholding_trend()/shareholding_scraper.py) -- they're a
pass-through from the Screener fundamentals store, populated once per
scan from the same candidate-generation query-table scrape.
"""
from __future__ import annotations

from unittest.mock import patch

import fundamental_analysis.institutional_engine as institutional_engine_module
from fundamental_analysis.institutional_engine import InstitutionalEngine


class TestShareholdingProfileWithTrend:

    def test_merges_snapshot_and_trend_fields(self):
        engine = InstitutionalEngine()

        with patch.object(engine, "get_shareholding_profile", return_value={
            "promoter_holding": "51.18%",
            "institutional_sponsorship": "29.04%",
            "public_retail_float": "19.78%",
        }), patch.object(
            institutional_engine_module, "get_promoter_trend", return_value="INCREASING",
        ), patch.object(
            institutional_engine_module, "get_fii_trend", return_value="DECREASING",
        ), patch.object(
            institutional_engine_module, "get_dii_trend", return_value="INCREASING",
        ):
            result = engine.get_shareholding_profile_with_trend("RELIANCE.NS", session=object())

        assert result["promoter_holding"] == "51.18%"  # snapshot field preserved
        assert result["institutional_sponsorship"] == "29.04%"  # untouched by trend merge
        assert result["promoter_trend"] == "INCREASING"  # trend field added
        assert result["fii_trend"] == "DECREASING"
        assert result["dii_trend"] == "INCREASING"

    def test_ticker_passed_through_unmodified_to_store_lookups(self):
        """No .NS stripping/reformatting needed here -- the store keys on
        the same .NS-suffixed ticker candidate_generator.py already uses
        when it writes (unlike the old per-page-visit scraper, which
        needed a bare company slug for its own URL)."""
        engine = InstitutionalEngine()

        with patch.object(engine, "get_shareholding_profile", return_value={}), patch.object(
            institutional_engine_module, "get_promoter_trend", return_value=None,
        ) as mock_promoter, patch.object(
            institutional_engine_module, "get_fii_trend", return_value=None,
        ) as mock_fii, patch.object(
            institutional_engine_module, "get_dii_trend", return_value=None,
        ) as mock_dii:
            engine.get_shareholding_profile_with_trend("RELIANCE.NS", session=object())

        mock_promoter.assert_called_once_with("RELIANCE.NS")
        mock_fii.assert_called_once_with("RELIANCE.NS")
        mock_dii.assert_called_once_with("RELIANCE.NS")
