"""
Tests for decision_engine/candidate_assembler.py -- kept deliberately
small per spec, two that actually matter:

1. _parse_formatted_percentage against a real formatted string vs. a
   real non-numeric sentinel ("DEBT_FREE") -- must return None, not 0.0,
   for the sentinel case. Coercing to 0.0 would fabricate a value ("zero
   debt") the sentinel never actually claimed.
2. assemble_sector_row -- Total_Sectors must be the real sector count
   from the ranking table, not accidentally the candidate's own sector's
   Rank (an easy mixup since both are small ints sitting right next to
   each other).
"""
from __future__ import annotations

import pandas as pd
import pytest

from decision_engine.candidate_assembler import _parse_formatted_percentage, assemble_sector_row


class TestParseFormattedPercentage:

    def test_formatted_percentage_string_parses_to_float(self):
        assert _parse_formatted_percentage("14.20%") == pytest.approx(14.2)

    def test_non_numeric_sentinel_returns_none_not_zero(self):
        # The exact bug this function exists to prevent: coercing
        # "DEBT_FREE" to 0.0 would be a fabricated value, not a missing one.
        assert _parse_formatted_percentage("DEBT_FREE") is None


class TestAssembleSectorRow:

    def test_total_sectors_is_the_real_sector_count_not_the_rank(self):
        # Deliberately give the candidate's own sector a Rank (2) that
        # differs from the true total sector count (4) -- if
        # Total_Sectors were accidentally set from Rank instead of
        # len(sector_ranking_df), this would silently pass with the
        # wrong number.
        sector_ranking_df = pd.DataFrame({
            "Avg_RS_Rating": [70.0, 55.0, 40.0, 30.0],
            "Pct_Uptrend": [65.0, 50.0, 20.0, 10.0],
            "Rank": [1, 2, 3, 4],
        }, index=pd.Index(["IT", "Auto", "Metals", "Realty"], name="Sector"))

        sector_row = assemble_sector_row(sector_ranking_df, "Auto")

        assert sector_row["Rank"] == 2
        assert sector_row["Total_Sectors"] == 4
