"""
Tests for ui/dashboard_data.py -- the pure data-adapter feeding the
mockup-derived dashboard template. Focused on the "no fabricated data"
guarantees and the field-name switch the build instructions called out
explicitly (predicted_p drives the confidence gauge, not confidence_score),
not exhaustive coverage of every formatting helper.
"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from ui.dashboard_data import (
    NA,
    build_candidate_view,
    build_dashboard_context,
    build_market_pulse,
    build_sector_view,
    compute_day_change_pct,
    fetch_fundamentals_view,
)


def _row(**overrides) -> pd.Series:
    base = {
        "Symbol": "TEST.NS", "Price": 100.0, "category": "EXECUTE", "confidence_score": 78.0,
        "predicted_p": 0.81, "model_version": "v1", "caps_applied": "", "contributing_factors": "VCP_BREAKOUT",
        "fakeout_risk_flags": "", "entry": 100.0, "stop_loss": 92.0, "target": 118.0, "reward_risk": 2.25,
        "stop_provenance": "STRUCTURAL", "target_provenance": "MEASURED_MOVE", "RS_Rating": 90.0, "Sector": "IT",
    }
    base.update(overrides)
    return pd.Series(base)


class TestComputeDayChangePct:

    def test_two_valid_closes_gives_real_pct(self):
        history = pd.DataFrame({"Close": [100.0, 105.0]})
        assert compute_day_change_pct(history) == pytest.approx(5.0)

    def test_none_when_history_missing(self):
        assert compute_day_change_pct(None) is None

    def test_none_when_fewer_than_two_rows(self):
        assert compute_day_change_pct(pd.DataFrame({"Close": [100.0]})) is None


class TestCandidateViewUsesPredictedPNotConfidenceScore:
    """The build instructions were explicit: the confidence gauge reads
    predicted_p (the calibrated model's real probability), not the old
    confidence_score composite -- conflating the two would show a number
    that isn't what actually decided EXECUTE vs. WATCHLIST."""

    def test_gauge_reflects_predicted_p_value(self):
        view = build_candidate_view(_row(predicted_p=0.81, confidence_score=40.0), history=None)
        assert view["conf"] == "81"
        assert view["confFraction"] == pytest.approx(0.81)

    def test_gauge_is_honest_na_when_model_never_scored_the_candidate(self):
        # e.g. AVOID/MONITOR, or a pattern-confirmed candidate the model
        # genuinely couldn't score (missing v2 feature inputs) --
        # categorize()'s own None convention, never a fabricated number.
        view = build_candidate_view(_row(predicted_p=None), history=None)
        assert view["conf"] == NA
        assert view["confFraction"] == 0.0

    def test_watchlist_category_label_reads_watchlist_not_alert_watchlist(self):
        view = build_candidate_view(_row(category="ALERT_WATCHLIST"), history=None)
        assert view["categoryLabel"] == "WATCHLIST"

    def test_execute_category_label_and_color(self):
        view = build_candidate_view(_row(category="EXECUTE"), history=None)
        assert view["categoryLabel"] == "EXECUTE"

    def test_trade_plan_carries_real_provenance_not_just_numbers(self):
        view = build_candidate_view(_row(), history=None)
        assert view["plan"]["stopProvenance"] == "STRUCTURAL"
        assert view["plan"]["targetProvenance"] == "MEASURED_MOVE"

    def test_no_history_gives_honest_na_change_not_zero(self):
        view = build_candidate_view(_row(), history=None)
        assert view["changeFmt"] == NA


class TestNoFabricatedDataOnEmptyInput:

    def test_empty_records_df_gives_empty_sector_view_not_a_crash(self):
        assert build_sector_view(pd.DataFrame()) == []

    def test_empty_records_df_dashboard_context_has_no_candidates(self):
        ctx = build_dashboard_context(
            records_df=pd.DataFrame(), history_by_symbol={}, regime_snapshot=None, index_quotes={},
        )
        assert ctx["execute_candidates"] == []
        assert ctx["watchlist_candidates"] == []
        assert ctx["all_candidates"] == []
        assert ctx["chart"] is None
        assert ctx["all_charts"] == []
        assert ctx["default_chart_symbol"] is None

    def test_market_pulse_regime_unknown_when_snapshot_is_none(self):
        pulse = build_market_pulse(regime_snapshot=None, index_quotes={})
        assert pulse["regime"]["label"] == "UNKNOWN"

    def test_market_pulse_flows_are_marked_unavailable_not_fabricated(self):
        pulse = build_market_pulse(regime_snapshot=None, index_quotes={})
        assert pulse["flows"]["available"] is False

    def test_index_quote_fetch_failure_is_honest_na_not_a_fabricated_price(self):
        pulse = build_market_pulse(regime_snapshot=None, index_quotes={"NIFTY 50": None})
        assert pulse["indices"][0]["price"] == NA
        assert pulse["indices"][0]["change"] == "unavailable"


class TestFundamentalsPanelNeverLeaksRawSentinels:
    """Regression coverage moved here from the pre-dashboard-rebuild
    tests/test_app.py, which pinned this same guarantee against app.py's
    old roce_str/yoy_rev_str/de_str assignments -- that code moved to
    fetch_fundamentals_view() below, so the test moved with it. An
    internal-only sentinel like "DATA_GAP" reaching the screen as literal
    text would look like a broken/leaked implementation detail to a user."""

    def test_data_gap_sentinel_never_reaches_display(self, monkeypatch):
        # fetch_fundamentals_view() imports each source function locally
        # inside its own body (not as a ui.dashboard_data module attribute),
        # so patching has to target each source module directly.
        import fundamental_analysis.fundamental_cache as fc
        import fundamental_analysis.corporate_engine as ce
        import fundamental_analysis.institutional_engine as ie

        monkeypatch.setattr(fc, "get_fundamentals", lambda symbol: {"roce": "DATA_GAP", "debt_to_equity": "DATA_GAP"})
        monkeypatch.setattr(
            ce.corporate_engine, "get_comprehensive_fundamentals",
            lambda symbol: {"revenue_yoy_quarterly_growth": "DATA_GAP", "margin_trend_yoy": "DATA_GAP"},
        )
        monkeypatch.setattr(
            ie.institutional_engine, "get_shareholding_profile",
            lambda symbol: {"institutional_sponsorship": "DATA_GAP"},
        )

        rows = fetch_fundamentals_view("TEST.NS")
        values = [row["v"] for row in rows]

        assert "DATA_GAP" not in values
        assert NA in values


class TestDashboardContextSplitsExecuteAndWatchlist:

    def test_execute_and_watchlist_land_in_separate_buckets(self):
        records_df = pd.DataFrame([
            _row(Symbol="A.NS", category="EXECUTE"),
            _row(Symbol="B.NS", category="ALERT_WATCHLIST"),
            _row(Symbol="C.NS", category="AVOID"),  # must be excluded entirely
            _row(Symbol="D.NS", category="MONITOR"),  # must be excluded entirely
        ])
        ctx = build_dashboard_context(
            records_df=records_df, history_by_symbol={}, regime_snapshot=None, index_quotes={},
        )
        assert [c["symbol"] for c in ctx["execute_candidates"]] == ["A.NS"]
        assert [c["symbol"] for c in ctx["watchlist_candidates"]] == ["B.NS"]
        assert len(ctx["all_candidates"]) == 2  # AVOID/MONITOR never reach the dashboard


def _history(base_price: float, n: int = 30, wavy: bool = False) -> pd.DataFrame:
    """Distinct OHLCV+EMA series per candidate -- lets a test prove two
    candidates' charts are genuinely independently computed, not one
    chart relabeled for a second symbol. build_chart_view() normalizes
    every range to a 0-100% band relative to its own min/max
    (SVG-friendly), so two plain linear ramps at different base prices
    would still normalize to an IDENTICAL relative polyline -- wavy=True
    uses a non-linear (sine-based) shape so the two candidates' relative
    structure genuinely differs, not just their absolute price level."""
    if wavy:
        closes = [base_price + 10 * math.sin(i / 3) + i * 0.3 for i in range(n)]
        ema20 = [base_price + 8 * math.sin(i / 3 + 1) + i * 0.2 for i in range(n)]
        ema50 = [base_price + 6 * math.sin(i / 4) + i * 0.1 for i in range(n)]
    else:
        closes = [base_price + i for i in range(n)]
        ema20 = [base_price + i * 0.5 for i in range(n)]
        ema50 = [base_price + i * 0.25 for i in range(n)]
    return pd.DataFrame({
        "Date": pd.date_range("2026-01-01", periods=n, freq="D"),
        "Open": closes, "High": [c + 1 for c in closes], "Low": [c - 1 for c in closes],
        "Close": closes, "Volume": [100_000 + i * 10 for i in range(n)],
        "EMA_20": ema20, "EMA_50": ema50,
    })


class TestChartRePointsPerCandidate:
    """build_dashboard_context()'s all_charts/default_chart_symbol -- the
    data underpinning falconOpenCandidate() re-pointing the main chart
    panel to whichever candidate was actually clicked (dashboard_template.html),
    not just relabeling whichever chart happened to render as the default."""

    def _context(self):
        records_df = pd.DataFrame([
            _row(Symbol="A.NS", category="EXECUTE", Price=101.0),
            _row(Symbol="B.NS", category="ALERT_WATCHLIST", Price=529.0),
        ])
        history_by_symbol = {"A.NS": _history(100.0), "B.NS": _history(500.0, wavy=True)}
        return build_dashboard_context(
            records_df=records_df, history_by_symbol=history_by_symbol,
            regime_snapshot=None, index_quotes={},
        )

    def test_every_execute_and_watchlist_candidate_gets_its_own_chart(self):
        ctx = self._context()

        assert {c["symbol"] for c in ctx["all_charts"]} == {"A.NS", "B.NS"}

    def test_default_chart_symbol_prefers_the_execute_candidate(self):
        ctx = self._context()

        assert ctx["default_chart_symbol"] == "A.NS"

    def test_chart_key_still_matches_the_default_symbol_entry_in_all_charts(self):
        """Backward-compat: existing callers reading ctx["chart"] alone
        (e.g. the empty-input None check) still see exactly the panel
        that starts visible."""
        ctx = self._context()

        default_entry = next(c for c in ctx["all_charts"] if c["symbol"] == ctx["default_chart_symbol"])
        assert ctx["chart"] == default_entry

    def test_each_candidates_chart_reflects_its_own_real_price_not_a_shared_value(self):
        ctx = self._context()

        by_symbol = {c["symbol"]: c for c in ctx["all_charts"]}
        assert by_symbol["A.NS"]["priceFmt"] != by_symbol["B.NS"]["priceFmt"]
        assert "101" in by_symbol["A.NS"]["priceFmt"]
        assert "529" in by_symbol["B.NS"]["priceFmt"]

    def test_ema_overlays_are_independently_computed_per_symbol_not_reused(self):
        """The specific gap #4 called out: EMA/volume overlays must
        recompute for the newly-selected symbol, not just the candlestick
        title. A.NS and B.NS have deliberately different EMA_20 series
        (_history()'s base_price offsets both), so their rendered SVG
        polyline point-strings for the same range must differ."""
        ctx = self._context()

        by_symbol = {c["symbol"]: c for c in ctx["all_charts"]}
        a_ema20 = by_symbol["A.NS"]["ranges"]["3M"]["ema20Points"]
        b_ema20 = by_symbol["B.NS"]["ranges"]["3M"]["ema20Points"]

        assert a_ema20 != ""
        assert b_ema20 != ""
        assert a_ema20 != b_ema20

    def test_charts_are_keyed_by_symbol_for_client_side_panel_lookup(self):
        """dashboard_template.html toggles panels via
        data-chart-panel="{{ chart.symbol }}" keyed against the clicked
        candidate's id (== Symbol) -- every chart dict must carry the same
        "symbol" key build_candidate_view()'s "id" uses, or the click
        handler's querySelector would silently find nothing."""
        ctx = self._context()

        candidate_ids = {c["id"] for c in ctx["all_candidates"]}
        chart_symbols = {c["symbol"] for c in ctx["all_charts"]}
        assert candidate_ids == chart_symbols
