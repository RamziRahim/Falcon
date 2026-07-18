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

import ast
from pathlib import Path

APP_SOURCE = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")


def _container_with_line_ranges(tree: ast.Module) -> list[tuple[int, int]]:
    """Line ranges of every `with st.container(...):` block in the module."""
    ranges = []
    for node in ast.walk(tree):
        if isinstance(node, ast.With):
            for item in node.items:
                ctx = item.context_expr
                if (
                    isinstance(ctx, ast.Call)
                    and isinstance(ctx.func, ast.Attribute)
                    and ctx.func.attr == "container"
                ):
                    ranges.append((node.lineno, node.end_lineno))
    return ranges


def _line_in_any_range(lineno: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= lineno <= end for start, end in ranges)


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


class TestNewScanRunsFullPipeline:
    """
    New Scan used to jump straight from candidate generation to
    build_candidate_table(), reading whatever pattern data already existed
    on disk -- never actually running market data collection or pattern
    detection for newly-found candidates. Pins the fix in place: app.py
    must delegate to the pipeline service (whose own call-order is tested
    in tests/services/test_scan_pipeline_service.py) rather than reading
    stale data/patterns/ files directly.
    """

    def test_delegates_to_scan_pipeline_service(self):
        assert "from services.scan_pipeline_service import run_new_scan_pipeline" in APP_SOURCE
        assert "run_new_scan_pipeline(ticker_universe" in APP_SOURCE

    def test_renders_scan_warnings(self):
        assert "from ui.scan_warnings import render as render_scan_warnings" in APP_SOURCE
        assert "render_scan_warnings(" in APP_SOURCE

    def test_no_longer_calls_build_candidate_table_directly(self):
        # build_candidate_table() now lives inside scan_pipeline_service --
        # app.py calling it directly again would silently reintroduce the
        # exact gap this task fixed (skipping Phase 3/4/5 for new tickers).
        assert "build_candidate_table(ticker_universe)" not in APP_SOURCE
        assert "from technical_analysis.candidate_table_builder import" not in APP_SOURCE


class TestContainerNestingFix:
    """
    #4: st.markdown('<div class="panel-box">') opened in one call, followed
    by a separately-called SectorRankingPanel.render()/AI panel content,
    then a closing </div> in a third call, does NOT nest in Streamlit --
    each call renders as an independent sibling. The div rendered as its
    own empty bordered block; the real content rendered separately below
    it. Fixed with `with st.container(border=True):`, which genuinely
    nests -- verified here via AST line-range containment rather than
    string matching, since a regression back to sibling calls is still
    syntactically valid Python and wouldn't be caught by a simple substring
    check.
    """

    def test_sector_ranking_panel_renders_inside_a_container_block(self):
        tree = ast.parse(APP_SOURCE)
        ranges = _container_with_line_ranges(tree)
        assert ranges, "Expected at least one `with st.container(...):` block in app.py"

        render_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "render"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "SectorRankingPanel"
        ]
        assert render_calls, "Expected a SectorRankingPanel.render(...) call in app.py"

        for call in render_calls:
            assert _line_in_any_range(call.lineno, ranges), (
                "SectorRankingPanel.render(...) must be called inside a "
                "`with st.container(...):` block, not as a sibling after a "
                "separately-opened <div> -- that leaves an empty bordered "
                "block with the real chart rendered separately below it."
            )

    def test_ai_panel_heading_renders_inside_a_container_block(self):
        tree = ast.parse(APP_SOURCE)
        ranges = _container_with_line_ranges(tree)

        heading_strings = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "Falcon AI Engine Guidance" in node.value
        ]
        assert heading_strings, "Expected the AI panel heading string in app.py"

        for node in heading_strings:
            assert _line_in_any_range(node.lineno, ranges), (
                "The AI panel heading must render inside a "
                "`with st.container(...):` block -- previously this bug made "
                "the AI panel show as a thin, empty green-bordered strip "
                "with no visible content."
            )
