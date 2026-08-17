"""
Regression tests for app.py bugs (Falcon spec).

The dashboard rebuild (ui/dashboard.py + ui/dashboard_data.py +
ui/dashboard_template.html, replacing the old Streamlit-native KPI-card/
fundamentals-panel/sector-ranking-panel rendering) moved two of the
original protections here to those new files -- their regression
coverage moved with them (see TestMarketStatusSingleSourceOfTruth below
for the market-status one, and tests/ui/test_dashboard_data.py's sentinel
tests for the fundamentals one). The old container-nesting protection
(#4 below) doesn't apply anymore -- there are no separately-called
Streamlit sibling widgets to nest incorrectly now that the whole surface
is one Jinja2-rendered HTML block.

app.py is a top-to-bottom Streamlit script, not a library of functions --
importing it directly would execute render_header()'s live index-quote
fetch and other side effects on every test run. These tests inspect the
source directly instead, which is enough to pin the fix and catch a
regression back to a hardcoded literal or an unmapped sentinel.
"""
from __future__ import annotations

from pathlib import Path

APP_SOURCE = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
DASHBOARD_SOURCE = (Path(__file__).resolve().parent.parent / "ui" / "dashboard.py").read_text(encoding="utf-8")


class TestMarketStatusSingleSourceOfTruth:
    """The KPI card's market_status used to be a separate hardcoded "OPEN"
    literal, independent of ui/header.py's real get_market_status() badge
    -- the two could disagree on screen at the same moment. That literal
    is gone (app.py no longer renders a KPI card at all), but the same
    single-source-of-truth requirement now applies to
    ui/dashboard.py's _is_market_open(), which drives the dashboard
    template's own market-open state."""

    def test_app_never_hardcodes_a_literal_market_status(self):
        assert 'market_status="OPEN"' not in APP_SOURCE
        assert 'market_status="CLOSED"' not in APP_SOURCE

    def test_dashboard_derives_market_open_from_header_not_a_reimplementation(self):
        assert "get_market_status" in DASHBOARD_SOURCE
        # Guards against the duplication this test previously missed: an
        # independent weekday/hours/holiday reimplementation living in
        # dashboard.py instead of calling the real header.py function.
        assert "MARKET_OPEN_TIME" not in DASHBOARD_SOURCE
        assert "get_nse_holidays" not in DASHBOARD_SOURCE


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
