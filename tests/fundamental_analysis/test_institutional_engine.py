"""
Test for fundamental_analysis/institutional_engine.py's
get_shareholding_profile_with_trend() -- confirms the Yahoo-sourced
snapshot and the Screener-scraped QoQ trend merge into one dict without
either clobbering the other.
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
            institutional_engine_module, "get_shareholding_trend", return_value={
                "promoter_pct_latest": 50.48, "promoter_trend": "INCREASING",
                "fii_pct_latest": 17.19, "fii_trend": "DECREASING",
                "dii_pct_latest": 21.10, "dii_trend": "INCREASING",
            },
        ) as mock_trend:
            result = engine.get_shareholding_profile_with_trend("RELIANCE.NS", session=object())

        assert result["promoter_holding"] == "51.18%"  # snapshot field preserved
        assert result["promoter_trend"] == "INCREASING"  # trend field added
        assert result["fii_trend"] == "DECREASING"

        # .NS suffix must be stripped before being used as the Screener.in slug
        called_company_slug = mock_trend.call_args[0][1]
        assert called_company_slug == "RELIANCE"
