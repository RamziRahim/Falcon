"""
Test for scoring/sector_rotation.py's Pct_Uptrend addition (sector
velocity/breadth alongside the existing Avg_RS_Rating magnitude ranking).
Kept intentionally small (one test) per the spec's own scoping.
"""
from __future__ import annotations

import pandas as pd

from scoring.sector_rotation import rank_sectors


class TestPctUptrendBreadth:

    def test_missing_trend_state_excluded_from_denominator_not_counted_as_downtrend(self):
        """
        Health has 2 tickers: one UPTREND, one with a missing Trend_State.
        The missing row must be excluded from the denominator entirely --
        Pct_Uptrend should be 100.0% (1 of 1 valid), not 50.0% (which would
        happen if the missing value were silently treated as DOWNTREND).
        """
        universe = pd.DataFrame({
            "Symbol": ["A", "B", "C", "D", "E"],
            "Sector": ["Tech", "Tech", "Tech", "Health", "Health"],
            "RS_Rating": [90, 85, 40, 70, 60],
            "Trend_State": ["UPTREND", "UPTREND", "DOWNTREND", "UPTREND", None],
        })

        ranking = rank_sectors(universe)

        assert ranking.loc["Tech", "Pct_Uptrend"] == 66.7
        assert ranking.loc["Health", "Pct_Uptrend"] == 100.0, (
            "Health's missing Trend_State row must be excluded from the "
            "denominator -- counting it as DOWNTREND would wrongly produce "
            "50.0% instead of 100.0%."
        )
