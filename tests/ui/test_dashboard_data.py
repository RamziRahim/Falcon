"""
Tests for ui/dashboard_data.py -- the pure data-adapter feeding the
mockup-derived dashboard template. Focused on the "no fabricated data"
guarantees and the field-name switch the build instructions called out
explicitly (predicted_p drives the confidence gauge, not confidence_score),
not exhaustive coverage of every formatting helper.
"""
from __future__ import annotations

import pandas as pd
import pytest

from ui.dashboard_data import (
    NA,
    build_candidate_view,
    build_dashboard_context,
    build_market_pulse,
    build_sector_view,
    compute_day_change_pct,
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
