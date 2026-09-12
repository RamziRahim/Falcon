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
    build_chart_view,
    build_dashboard_context,
    build_market_pulse,
    build_monitor_candidate_view,
    build_sector_view,
    compute_day_change_pct,
    fetch_fundamentals_view,
    format_stale_data_notice,
    get_monitor_setup_state,
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


class TestPeVsSectorField:
    """P/E vs Sector (2026-08-20): both values now come from the
    Screener fundamentals store (fundamental_analysis/screener_fundamentals_store.py's
    get_pe_ratio_display()/get_industry_pe_display()) -- previously
    always NA, no real data source existed. Only shown when BOTH values
    are real; a half-comparison would imply more than the data supports."""

    def test_shows_both_values_when_both_are_real(self, monkeypatch):
        monkeypatch.setattr(
            "fundamental_analysis.screener_fundamentals_store.get_pe_ratio_display",
            lambda symbol: "48.69",
        )
        monkeypatch.setattr(
            "fundamental_analysis.screener_fundamentals_store.get_industry_pe_display",
            lambda symbol: "32.10",
        )

        row = next(r for r in fetch_fundamentals_view("TEST.NS") if r["k"] == "P/E vs Sector")

        assert row["v"] == "48.69 vs 32.10"

    def test_na_when_company_pe_missing(self, monkeypatch):
        monkeypatch.setattr(
            "fundamental_analysis.screener_fundamentals_store.get_pe_ratio_display",
            lambda symbol: "N/A",
        )
        monkeypatch.setattr(
            "fundamental_analysis.screener_fundamentals_store.get_industry_pe_display",
            lambda symbol: "32.10",
        )

        row = next(r for r in fetch_fundamentals_view("TEST.NS") if r["k"] == "P/E vs Sector")

        assert row["v"] == NA

    def test_na_when_industry_pe_missing(self, monkeypatch):
        monkeypatch.setattr(
            "fundamental_analysis.screener_fundamentals_store.get_pe_ratio_display",
            lambda symbol: "48.69",
        )
        monkeypatch.setattr(
            "fundamental_analysis.screener_fundamentals_store.get_industry_pe_display",
            lambda symbol: "N/A",
        )

        row = next(r for r in fetch_fundamentals_view("TEST.NS") if r["k"] == "P/E vs Sector")

        assert row["v"] == NA


class TestDashboardContextSplitsExecuteAndWatchlist:

    def test_execute_watchlist_and_monitor_land_in_separate_buckets(self):
        """MONITOR is included as of the MONITOR-watchlist-section spec --
        only AVOID (and NO_DATA/anything else uncategorized) never reaches
        the dashboard at all."""
        records_df = pd.DataFrame([
            _row(Symbol="A.NS", category="EXECUTE"),
            _row(Symbol="B.NS", category="ALERT_WATCHLIST"),
            _row(Symbol="C.NS", category="AVOID"),  # must be excluded entirely
            _row(Symbol="D.NS", category="MONITOR"),
        ])
        ctx = build_dashboard_context(
            records_df=records_df, history_by_symbol={}, regime_snapshot=None, index_quotes={},
        )
        assert [c["symbol"] for c in ctx["execute_candidates"]] == ["A.NS"]
        assert [c["symbol"] for c in ctx["watchlist_candidates"]] == ["B.NS"]
        assert [c["symbol"] for c in ctx["monitor_candidates"]] == ["D.NS"]
        assert len(ctx["all_candidates"]) == 3  # AVOID is the only tier excluded


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


class TestFormatStaleDataNotice:
    """format_stale_data_notice() -- the guard against a candidate's card/
    chart silently showing data from a Phase 3/4 fetch that failed for
    that one ticker during an otherwise-successful scan, first surfaced
    while diagnosing a real GLAXO.NS chart gap (docs/known_data_issues.md)."""

    def test_none_when_data_is_current_with_scan_date(self):
        notice = format_stale_data_notice("TEST.NS", pd.Timestamp("2026-01-30"), pd.Timestamp("2026-01-30"))

        assert notice is None

    def test_none_when_data_is_newer_than_scan_date(self):
        """Shouldn't happen in practice, but a data date AFTER the scan
        date must not be flagged as stale either -- only strictly older
        data is a problem."""
        notice = format_stale_data_notice("TEST.NS", pd.Timestamp("2026-02-01"), pd.Timestamp("2026-01-30"))

        assert notice is None

    def test_warns_when_data_predates_scan_date(self):
        notice = format_stale_data_notice("GLAXO.NS", pd.Timestamp("2026-08-18"), pd.Timestamp("2026-08-19"))

        assert notice is not None
        assert "2026-08-18" in notice
        assert "GLAXO.NS" in notice

    def test_compares_dates_not_datetimes_same_day_different_time_is_current(self):
        """A scan completing at 22:52 on the same calendar day the data's
        own latest bar is dated must NOT be flagged -- comparing full
        datetimes would wrongly treat every same-day scan as stale
        because the data's own timestamp has no time component (midnight)
        while the scan's does."""
        data_date = pd.Timestamp("2026-08-19")
        scan_datetime = pd.Timestamp("2026-08-19 22:52:00")

        notice = format_stale_data_notice("TEST.NS", data_date, scan_datetime)

        assert notice is None

    def test_none_when_scan_date_is_none(self):
        """No scan-timestamp context available (e.g. app.py's session
        state hasn't recorded one yet) -- degrade to no notice, not a
        crash or a false-positive warning."""
        notice = format_stale_data_notice("TEST.NS", pd.Timestamp("2026-08-18"), None)

        assert notice is None

    def test_none_when_data_date_is_none(self):
        notice = format_stale_data_notice("TEST.NS", None, pd.Timestamp("2026-08-19"))

        assert notice is None

    def test_none_when_scan_is_saturday_and_data_is_from_preceding_friday(self):
        """2026-08-22 fix, confirmed live: a scan run on a weekend has no
        newer trading day to compare against by definition -- Friday's
        data is already exactly as current as it could possibly be, not
        stale. 2026-08-21 is a real Friday, 2026-08-22 a real Saturday."""
        notice = format_stale_data_notice(
            "TEST.NS", pd.Timestamp("2026-08-21"), pd.Timestamp("2026-08-22"),
        )

        assert notice is None

    def test_none_when_scan_is_sunday_and_data_is_from_preceding_friday(self):
        notice = format_stale_data_notice(
            "TEST.NS", pd.Timestamp("2026-08-21"), pd.Timestamp("2026-08-23"),
        )

        assert notice is None

    def test_still_warns_when_data_predates_the_most_recent_trading_day(self):
        """Genuine staleness must still fire on a weekend scan -- the fix
        narrows the false-positive case, it doesn't blind the check
        entirely. Data from Thursday the 20th, scanned Saturday the 22nd,
        with Friday the 21st being the real most-recent trading day the
        data should have -- one real trading day behind, not caught up."""
        notice = format_stale_data_notice(
            "TEST.NS", pd.Timestamp("2026-08-20"), pd.Timestamp("2026-08-22"),
        )

        assert notice is not None
        assert "2026-08-20" in notice

    def test_nse_holiday_is_also_skipped_when_finding_the_most_recent_trading_day(self, monkeypatch):
        """Not just weekends -- a real NSE equity holiday must be walked
        past too. Overrides this file's own autouse empty-holiday-set
        fixture for just this one test."""
        from datetime import date

        monkeypatch.setattr(
            "market_data.holiday_calendar.get_nse_holidays",
            lambda: {date(2026, 8, 21)},  # pretend Friday the 21st is a holiday
        )

        # As of Saturday the 22nd, with Friday (21st) a holiday too, the
        # real most-recent trading day is Thursday the 20th.
        notice = format_stale_data_notice(
            "TEST.NS", pd.Timestamp("2026-08-20"), pd.Timestamp("2026-08-22"),
        )

        assert notice is None


class TestStaleNoticeWiredIntoCardsAndCharts:
    """The notice must actually reach the rendered card/chart dicts, not
    just exist as a standalone helper nobody calls."""

    def test_chart_view_carries_stale_notice_when_scan_date_is_later(self):
        history = _history(100.0)  # dates through 2026-01-30
        chart = build_chart_view(
            history, "TEST.NS", 100.0, 1.0, "IT", scan_date=pd.Timestamp("2026-02-15"),
        )

        assert chart["staleNotice"] is not None
        assert "2026-01-30" in chart["staleNotice"]

    def test_chart_view_has_no_notice_when_scan_date_matches_latest_bar(self):
        history = _history(100.0)
        chart = build_chart_view(
            history, "TEST.NS", 100.0, 1.0, "IT", scan_date=pd.Timestamp("2026-01-30"),
        )

        assert chart["staleNotice"] is None

    def test_chart_view_has_no_notice_when_scan_date_omitted(self):
        """Default (no scan_date passed) must not fabricate a warning --
        matches every existing caller that predates this feature."""
        history = _history(100.0)
        chart = build_chart_view(history, "TEST.NS", 100.0, 1.0, "IT")

        assert chart["staleNotice"] is None

    def test_candidate_card_carries_stale_notice_when_scan_date_is_later(self):
        row = _row(Symbol="TEST.NS")
        history = _history(100.0)

        view = build_candidate_view(row, history, scan_date=pd.Timestamp("2026-02-15"))

        assert view["staleNotice"] is not None
        assert "TEST.NS" in view["staleNotice"]

    def test_dashboard_context_threads_last_scan_completed_at_to_every_candidate(self):
        records_df = pd.DataFrame([
            _row(Symbol="A.NS", category="EXECUTE", Price=101.0),
            _row(Symbol="B.NS", category="ALERT_WATCHLIST", Price=529.0),
        ])
        # A.NS's own history is stale relative to the scan; B.NS's is current.
        history_by_symbol = {
            "A.NS": _history(100.0),  # through 2026-01-30
            "B.NS": pd.concat([_history(500.0, wavy=True), pd.DataFrame([{
                "Date": pd.Timestamp("2026-02-15"), "Open": 530, "High": 531, "Low": 529,
                "Close": 530, "Volume": 100_000, "EMA_20": 530, "EMA_50": 530,
            }])], ignore_index=True),
        }

        ctx = build_dashboard_context(
            records_df=records_df, history_by_symbol=history_by_symbol,
            regime_snapshot=None, index_quotes={},
            last_scan_completed_at=pd.Timestamp("2026-02-15"),
        )

        by_symbol = {c["symbol"]: c for c in ctx["all_charts"]}
        assert by_symbol["A.NS"]["staleNotice"] is not None
        assert by_symbol["B.NS"]["staleNotice"] is None

    def test_dashboard_context_has_no_stale_notices_when_last_scan_completed_at_omitted(self):
        """Backward-compat: existing callers not yet passing
        last_scan_completed_at (or a caller with no session-state value
        yet) still get every candidate with staleNotice=None, matching
        today's rendering exactly."""
        records_df = pd.DataFrame([_row(Symbol="A.NS", category="EXECUTE", Price=101.0)])
        history_by_symbol = {"A.NS": _history(100.0)}

        ctx = build_dashboard_context(
            records_df=records_df, history_by_symbol=history_by_symbol,
            regime_snapshot=None, index_quotes={},
        )

        assert ctx["all_charts"][0]["staleNotice"] is None


def _monitor_pattern_row(**overrides) -> dict:
    """One data/patterns/*.parquet-shaped row's worth of Is_X_Setup
    booleans -- what get_monitor_setup_state() reads. All False by
    default (nothing forming)."""
    base = {
        "Is_VCP_Setup": False, "Is_Flat_Base_Setup": False, "Is_Cup_Handle_Setup": False,
        "Is_Ascending_Triangle_Setup": False, "Is_Bull_Flag_Setup": False,
    }
    base.update(overrides)
    return base


class TestGetMonitorSetupState:
    """The real, available partial pattern-detector state a MONITOR card
    can honestly show -- Is_X_Setup booleans, NOT Pattern_Type (which
    pattern_engine.py only ever populates for CONFIRMED breakouts, always
    empty for a MONITOR candidate by definition)."""

    def test_none_when_nothing_forming(self):
        assert get_monitor_setup_state(_monitor_pattern_row()) is None

    def test_single_setup_forming(self):
        state = get_monitor_setup_state(_monitor_pattern_row(Is_Flat_Base_Setup=True))

        assert state == "Flat Base forming, not yet confirmed"

    def test_multiple_setups_forming_are_all_named(self):
        state = get_monitor_setup_state(
            _monitor_pattern_row(Is_VCP_Setup=True, Is_Bull_Flag_Setup=True)
        )

        assert state == "VCP, Bull Flag forming, not yet confirmed"

    def test_does_not_read_pattern_type(self):
        """A confirmed Pattern_Type value must not leak into this --
        get_monitor_setup_state() only ever exists to answer 'what's
        forming', a question Pattern_Type structurally can't answer for
        a MONITOR candidate."""
        row = _monitor_pattern_row(Is_Flat_Base_Setup=True)
        row["Pattern_Type"] = "Cup_Handle"  # a CONFIRMED pattern, unrelated

        state = get_monitor_setup_state(row)

        assert state == "Flat Base forming, not yet confirmed"


def _monitor_row(**overrides) -> pd.Series:
    base = {
        "Symbol": "TEST.NS", "Price": 100.0, "category": "MONITOR",
        "RS_Rating": 85.0, "Sector": "Healthcare", "Trend_State": "UPTREND",
    }
    base.update(overrides)
    return pd.Series(base)


class TestBuildMonitorCandidateView:
    """MONITOR cards must never carry a trade plan, fakeout-risk flags,
    or a confidence gauge value -- categorize() never computes any of
    those for a MONITOR candidate (B-8: capped before the model), so
    fabricating them here would misrepresent what Falcon actually knows."""

    def test_no_trade_plan_field_at_all(self):
        view = build_monitor_candidate_view(_monitor_row(), history=None)

        assert "plan" not in view

    def test_no_confidence_score_or_waterfall_fields(self):
        view = build_monitor_candidate_view(_monitor_row(), history=None)

        assert "confidenceScore" not in view
        assert "waterfall" not in view
        assert "fundamentals" not in view

    def test_conf_is_honest_na_not_a_fabricated_score(self):
        view = build_monitor_candidate_view(_monitor_row(), history=None)

        assert view["conf"] == NA

    def test_risk_flags_and_factors_are_empty_not_fabricated(self):
        view = build_monitor_candidate_view(_monitor_row(), history=None)

        assert view["riskFlags"] == []
        assert view["factors"] == []

    def test_reason_is_always_no_confirmed_breakout_yet(self):
        """The ONLY way to reach MONITOR (leadership_decision_engine.py's
        B-8 branch: score>=40, no confirmed pattern) -- never a different,
        more-specific-sounding reason the data doesn't actually support."""
        view = build_monitor_candidate_view(_monitor_row(), history=None)

        assert view["monitorReason"] == "No confirmed breakout yet"

    def test_real_trend_state_and_rs_rating_shown(self):
        view = build_monitor_candidate_view(_monitor_row(Trend_State="UPTREND", RS_Rating=77.0), history=None)

        assert view["trendState"] == "UPTREND"
        assert view["rsRating"] == "77"

    def test_setup_state_read_from_latest_history_row(self):
        history = _history(100.0)
        history.loc[history.index[-1], "Is_VCP_Setup"] = True

        view = build_monitor_candidate_view(_monitor_row(), history=history)

        assert view["setupState"] == "VCP forming, not yet confirmed"

    def test_setup_state_none_when_history_missing(self):
        view = build_monitor_candidate_view(_monitor_row(), history=None)

        assert view["setupState"] is None

    def test_stale_notice_wired_same_as_other_tiers(self):
        history = _history(100.0)  # dates through 2026-01-30

        view = build_monitor_candidate_view(_monitor_row(), history=history, scan_date=pd.Timestamp("2026-02-15"))

        assert view["staleNotice"] is not None
        assert "TEST.NS" in view["staleNotice"]


class TestMonitorTierInDashboardContext:
    """MONITOR-watchlist-section spec: MONITOR rows are real categorize()
    output that used to be silently dropped before reaching this
    function at all -- confirmed live (2026-08-20 real scan: 20 real
    MONITOR candidates, 0 EXECUTE, 0 WATCHLIST, entirely invisible under
    the old two-category filter)."""

    def test_monitor_candidates_populated_from_real_scan_data(self):
        records_df = pd.DataFrame([
            _row(Symbol="A.NS", category="EXECUTE"),
            _monitor_row(Symbol="M1.NS"),
            _monitor_row(Symbol="M2.NS"),
        ])
        ctx = build_dashboard_context(
            records_df=records_df, history_by_symbol={}, regime_snapshot=None, index_quotes={},
        )

        assert {c["symbol"] for c in ctx["monitor_candidates"]} == {"M1.NS", "M2.NS"}

    def test_monitor_count_independent_of_execute_and_watchlist_counts(self):
        """Not conflated with the other tiers -- each bucket's count
        reflects only its own category."""
        records_df = pd.DataFrame([
            _row(Symbol="A.NS", category="EXECUTE"),
            _row(Symbol="B.NS", category="ALERT_WATCHLIST"),
            _monitor_row(Symbol="M1.NS"),
            _monitor_row(Symbol="M2.NS"),
            _monitor_row(Symbol="M3.NS"),
        ])
        ctx = build_dashboard_context(
            records_df=records_df, history_by_symbol={}, regime_snapshot=None, index_quotes={},
        )

        assert len(ctx["execute_candidates"]) == 1
        assert len(ctx["watchlist_candidates"]) == 1
        assert len(ctx["monitor_candidates"]) == 3

    def test_honest_empty_monitor_list_when_zero_monitor_candidates(self):
        records_df = pd.DataFrame([_row(Symbol="A.NS", category="EXECUTE")])
        ctx = build_dashboard_context(
            records_df=records_df, history_by_symbol={}, regime_snapshot=None, index_quotes={},
        )

        assert ctx["monitor_candidates"] == []

    def test_avoid_still_excluded_entirely(self):
        records_df = pd.DataFrame([
            _row(Symbol="C.NS", category="AVOID"),
            _monitor_row(Symbol="M1.NS"),
        ])
        ctx = build_dashboard_context(
            records_df=records_df, history_by_symbol={}, regime_snapshot=None, index_quotes={},
        )

        assert len(ctx["all_candidates"]) == 1
        assert ctx["all_candidates"][0]["symbol"] == "M1.NS"


class TestUniversalChartViewingIncludesMonitor:
    """Part 2 of the MONITOR-watchlist-section spec: clicking a MONITOR
    card must chart it the same way an EXECUTE/WATCHLIST card's click
    does -- MONITOR candidates need their own real, independently
    computed chart in all_charts, not just a card."""

    def test_monitor_candidates_get_their_own_chart(self):
        records_df = pd.DataFrame([_monitor_row(Symbol="M1.NS")])
        history_by_symbol = {"M1.NS": _history(250.0)}

        ctx = build_dashboard_context(
            records_df=records_df, history_by_symbol=history_by_symbol,
            regime_snapshot=None, index_quotes={},
        )

        assert {c["symbol"] for c in ctx["all_charts"]} == {"M1.NS"}

    def test_default_chart_falls_back_to_monitor_when_no_execute_or_watchlist(self):
        """The real live-scan case this spec was written to fix:
        0 EXECUTE, 0 WATCHLIST, N MONITOR must still default to a real,
        chartable candidate rather than the empty state."""
        records_df = pd.DataFrame([
            _monitor_row(Symbol="M1.NS"),
            _monitor_row(Symbol="M2.NS"),
        ])
        history_by_symbol = {"M1.NS": _history(250.0), "M2.NS": _history(300.0)}

        ctx = build_dashboard_context(
            records_df=records_df, history_by_symbol=history_by_symbol,
            regime_snapshot=None, index_quotes={},
        )

        assert ctx["default_chart_symbol"] == "M1.NS"
        assert ctx["chart"] is not None
        assert ctx["chart"]["symbol"] == "M1.NS"

    def test_execute_still_preferred_over_monitor_for_default(self):
        records_df = pd.DataFrame([
            _monitor_row(Symbol="M1.NS"),
            _row(Symbol="E1.NS", category="EXECUTE"),
        ])
        history_by_symbol = {"M1.NS": _history(250.0), "E1.NS": _history(500.0)}

        ctx = build_dashboard_context(
            records_df=records_df, history_by_symbol=history_by_symbol,
            regime_snapshot=None, index_quotes={},
        )

        assert ctx["default_chart_symbol"] == "E1.NS"

    def test_ema_and_volume_recompute_independently_for_a_monitor_symbol(self):
        """Same gap already called out and fixed for EXECUTE/WATCHLIST
        (TestChartRePointsPerCandidate) -- must hold for MONITOR too, not
        a half-fix that only recomputes the candlesticks."""
        records_df = pd.DataFrame([
            _row(Symbol="E1.NS", category="EXECUTE"),
            _monitor_row(Symbol="M1.NS"),
        ])
        history_by_symbol = {
            "E1.NS": _history(100.0),
            "M1.NS": _history(500.0, wavy=True),
        }

        ctx = build_dashboard_context(
            records_df=records_df, history_by_symbol=history_by_symbol,
            regime_snapshot=None, index_quotes={},
        )

        by_symbol = {c["symbol"]: c for c in ctx["all_charts"]}
        e1_ema20 = by_symbol["E1.NS"]["ranges"]["3M"]["ema20Points"]
        m1_ema20 = by_symbol["M1.NS"]["ranges"]["3M"]["ema20Points"]

        assert e1_ema20 != ""
        assert m1_ema20 != ""
        assert e1_ema20 != m1_ema20
