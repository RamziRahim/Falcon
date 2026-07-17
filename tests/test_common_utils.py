"""
Tests for common/utils.py's sentinel_to_display() — maps internal-only
signal strings (e.g. fundamental_analysis' "DATA_GAP") to display-safe
text so they never leak into the UI as literal text (Falcon spec).
"""
from __future__ import annotations

from common.utils import sentinel_to_display


class TestSentinelToDisplay:

    def test_data_gap_maps_to_na(self):
        assert sentinel_to_display("DATA_GAP") == "N/A"

    def test_na_passes_through_unchanged(self):
        assert sentinel_to_display("N/A") == "N/A"

    def test_real_value_passes_through_unchanged(self):
        assert sentinel_to_display("+12.34%") == "+12.34%"

    def test_debt_free_passes_through_unchanged(self):
        assert sentinel_to_display("DEBT_FREE") == "DEBT_FREE"

    def test_non_string_input_is_stringified(self):
        assert sentinel_to_display(42) == "42"
