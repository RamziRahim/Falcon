"""
Tests for fundamental_analysis/screener_fundamentals_store.py's
get_pe_ratio_display()/get_industry_pe_display() -- added 2026-08-20
alongside the account's real "Ind PE" column (docs/known_data_issues.md).
"P/E" itself was already scraped since the original 2026-08-18 spec but
never made it into COLUMN_TO_FIELD, so it was captured and immediately
discarded every scan -- these tests cover the fix.
"""
from __future__ import annotations

import pandas as pd

from fundamental_analysis.screener_fundamentals_store import (
    get_industry_pe_display,
    get_pe_ratio_display,
)


class TestPeRatioDisplays:

    def test_pe_ratio_comes_from_the_store(self, isolated_screener_fundamentals_store):
        df = pd.DataFrame([{"Symbol": "DUMMY.NS", "P/E": 48.69, "Ind PE": 32.10}])
        isolated_screener_fundamentals_store.save_from_candidate_table(df)

        assert get_pe_ratio_display("DUMMY.NS") == "48.69"
        assert get_industry_pe_display("DUMMY.NS") == "32.10"

    def test_never_scanned_ticker_returns_honest_na_not_a_crash(self, isolated_screener_fundamentals_store):
        assert get_pe_ratio_display("NEVER_SEEN.NS") == "N/A"
        assert get_industry_pe_display("NEVER_SEEN.NS") == "N/A"

    def test_missing_value_within_a_scanned_ticker_is_na_not_zero(self, isolated_screener_fundamentals_store):
        """A ticker present in the store from a scan that predates this
        column pair (e.g. scraped before "Ind PE" was added) must not
        show a fabricated 0.00 for the field it never had."""
        df = pd.DataFrame([{"Symbol": "DUMMY.NS", "ROCE %": 20.0}])
        isolated_screener_fundamentals_store.save_from_candidate_table(df)

        assert get_pe_ratio_display("DUMMY.NS") == "N/A"
        assert get_industry_pe_display("DUMMY.NS") == "N/A"
