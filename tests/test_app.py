"""
Regression tests for two app.py bugs (Falcon spec):

1. The KPI card's market_status was a separate hardcoded "OPEN" literal,
   independent of ui/header.py's real get_market_status() badge -- the two
   could disagree on screen at the same moment.
2. The fundamentals panel passed internal-only sentinel strings (e.g.
   "DATA_GAP") straight through to display instead of a user-facing label.

app.py is a top-to-bottom Streamlit script, not a library of functions --
importing it directly would execute render_header()'s live index-quote
fetch and other side effects on every test run. These tests inspect the
source directly instead, which is enough to pin the fix and catch a
regression back to a hardcoded literal or an unmapped sentinel.
"""
from __future__ import annotations

from pathlib import Path

APP_SOURCE = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")


class TestMarketStatusSingleSourceOfTruth:

    def test_never_hardcodes_a_literal_market_status(self):
        assert 'market_status="OPEN"' not in APP_SOURCE
        assert 'market_status="CLOSED"' not in APP_SOURCE

    def test_derives_market_status_from_header(self):
        assert "market_status=get_market_status()" in APP_SOURCE
        assert "from ui.header import" in APP_SOURCE
        import_line = next(
            line for line in APP_SOURCE.splitlines()
            if line.strip().startswith("from ui.header import")
        )
        assert "get_market_status" in import_line


class TestSentinelNeverLeaksToDisplay:

    def _assignment_line(self, var_name: str) -> str:
        return next(
            line for line in APP_SOURCE.splitlines()
            if line.strip().startswith(f"{var_name} =")
        )

    def test_roce_str_goes_through_sentinel_mapping(self):
        assert "sentinel_to_display(" in self._assignment_line("roce_str")

    def test_yoy_rev_str_goes_through_sentinel_mapping(self):
        assert "sentinel_to_display(" in self._assignment_line("yoy_rev_str")

    def test_de_str_goes_through_sentinel_mapping(self):
        assert "sentinel_to_display(" in self._assignment_line("de_str")

    def test_data_gap_literal_no_longer_used_as_a_default(self):
        # The raw sentinel may still appear in a comment or import elsewhere,
        # but the fundamentals fields themselves must never pass it straight
        # through as a bare default value.
        for var_name in ("roce_str", "yoy_rev_str", "de_str"):
            assert '"DATA_GAP"' not in self._assignment_line(var_name)
