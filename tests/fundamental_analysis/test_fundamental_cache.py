"""
Tests for fundamental_analysis/fundamental_cache.py -- as of
docs/known_data_issues.md item #4, this is a thin pass-through onto
fundamental_analysis/screener_fundamentals_store.py rather than its own
live-Yahoo-fetch-plus-7-day-cache layer (the old version's staleness/
fetch-failure-fallback behavior no longer applies -- there's no live
fetch left here to go stale or fail; the Screener store is populated
once per scan by candidate_generation, not lazily per-candidate).
"""
from __future__ import annotations

from fundamental_analysis.fundamental_cache import get_fundamentals


class TestReadsFromScreenerStore:

    def test_roce_and_debt_to_equity_come_from_the_store(self, isolated_screener_fundamentals_store):
        import pandas as pd
        df = pd.DataFrame([{
            "Symbol": "DUMMY.NS", "ROCE %": 12.5, "Debt / Eq": 0.35,
            "Prom. Hold. %": 50.0, "Change in Prom Hold %": 0.0,
            "FII Hold %": 10.0, "Chg in FII Hold %": 0.0,
            "DII Hold %": 5.0, "Chg in DII Hold %": 0.0,
            "OPM Qtr %": 20.0, "OPM PY Qtr %": 18.0,
        }])
        isolated_screener_fundamentals_store.save_from_candidate_table(df)

        result = get_fundamentals("DUMMY.NS")

        assert result["roce"] == "12.50%"
        # Screener's own D/E is a plain ratio (0.35); the returned string
        # is on the same "XX.XX%" scale the old Yahoo convention used
        # (candidate_assembler.py's _parse_formatted_percentage() divides
        # by 100 to recover the ratio) -- 0.35 -> "35.00%", not "0.35%".
        assert result["debt_to_equity"] == "35.00%"

    def test_never_scanned_ticker_returns_honest_na_not_a_crash(self, isolated_screener_fundamentals_store):
        result = get_fundamentals("NEVER_SEEN.NS")

        assert result["roce"] == "N/A"
        assert result["debt_to_equity"] == "N/A"

    def test_revenue_yoy_quarterly_growth_key_is_present_but_unused(self, isolated_screener_fundamentals_store):
        """Kept for dict-shape compatibility with any future caller --
        confirmed via a full-codebase audit that nothing currently reads
        this specific field from get_fundamentals() (dashboard_data.py's
        "Revenue Growth (YoY)" reads the same-named field from
        corporate_engine.get_comprehensive_fundamentals() instead)."""
        result = get_fundamentals("ANY.NS")

        assert "revenue_yoy_quarterly_growth" in result

    def test_force_refresh_is_a_harmless_no_op(self, isolated_screener_fundamentals_store):
        """force_refresh is kept for call-site compatibility -- there's no
        live fetch left for it to force; both calls just read the store."""
        result = get_fundamentals("ANY.NS", force_refresh=True)

        assert result["roce"] == "N/A"
