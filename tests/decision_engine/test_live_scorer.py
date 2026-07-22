"""
Tests for decision_engine/live_scorer.py -- proving the WIRING
(run_new_scan_pipeline -> score_live_candidates -> categorize(), the
Screener.in session opened once per batch not once per ticker, and
graceful degradation when no session is available), not re-testing
categorize()'s own scoring behavior (already covered by
tests/decision_engine/test_leadership_decision_engine.py) or the
individual fundamentals fetchers' own parsing logic (already covered by
each of their own test modules).

categorize() and the four fundamentals fetchers are all monkeypatched to
record what they were called with -- score_live_candidates()'s own
control flow (session lifecycle, per-ticker looping, merging results back
onto records_df) runs for real.
"""
from __future__ import annotations

import pandas as pd
import pytest

import decision_engine.live_scorer as live_scorer


def _records_df() -> pd.DataFrame:
    return pd.DataFrame({
        "Symbol": ["AAA.NS", "BBB.NS"],
        "Sector": ["IT", "IT"],
        "RS_Rating": [80.0, 60.0],
        "Rel_Vol": [1.2, 0.9],
        "Sector_Index_Trend": ["UPTREND", "UPTREND"],
    })


def _fake_categorize_recorder(monkeypatch):
    calls = []

    def fake_categorize(candidate, sector_row, market_verdict, pattern_details=None,
                         disable_fundamental_signals=False, enable_microstructure_signals=False):
        calls.append({
            "candidate": candidate,
            "disable_fundamental_signals": disable_fundamental_signals,
            "enable_microstructure_signals": enable_microstructure_signals,
        })
        return {
            "category": "ALERT_WATCHLIST", "confidence_score": 55.0,
            "caps_applied": ["EARNINGS_PROXIMITY"], "contributing_factors": ["RS_STRONG"],
            "fakeout_risk_flags": [],
        }

    monkeypatch.setattr(live_scorer, "categorize", fake_categorize)
    return calls


def _stub_out_market_and_history(monkeypatch, history_rows: int = 25):
    monkeypatch.setattr(live_scorer, "_compute_live_market_verdict", lambda: "FAVORABLE")

    history = pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=history_rows, freq="D"),
        "Open": [100.0] * history_rows,
        "High": [101.0] * history_rows,
        "Low": [99.0] * history_rows,
        "Close": [100.0] * history_rows,
        "Volume": [100_000] * history_rows,
        "Trend_State": ["UPTREND"] * history_rows,
    })
    monkeypatch.setattr(live_scorer, "_load_pattern_history", lambda ticker: history)


def _stub_no_playwright_session(monkeypatch):
    """No SCREENER_USERNAME/PASSWORD configured -- the common case in a
    test/CI environment. score_live_candidates() must still run to
    completion using the Yahoo-only fundamentals fallback."""
    monkeypatch.setattr(live_scorer, "SCREENER_USERNAME", None)
    monkeypatch.setattr(live_scorer, "SCREENER_PASSWORD", None)


def _stub_fundamentals_sources(monkeypatch):
    fetch_calls = {"fundamental_cache": [], "corporate_engine": [], "institutional": [], "deal_activity": []}

    monkeypatch.setattr(live_scorer, "get_fundamentals", lambda ticker: (
        fetch_calls["fundamental_cache"].append(ticker) or {"roce": "18.00%", "debt_to_equity": "20.00%"}
    ))

    class _FakeCorporateEngine:
        def get_comprehensive_fundamentals(self, ticker):
            fetch_calls["corporate_engine"].append(ticker)
            return {"margin_trend_yoy": "EXPANDING", "days_to_earnings": 45}

    class _FakeInstitutionalEngine:
        def get_shareholding_profile(self, ticker):
            fetch_calls["institutional"].append(("snapshot", ticker))
            return {"institutional_sponsorship": "22.00%"}

        def get_shareholding_profile_with_trend(self, ticker, session):
            fetch_calls["institutional"].append(("with_trend", ticker, session))
            return {"institutional_sponsorship": "22.00%", "fii_trend": "INCREASING",
                    "dii_trend": "FLAT", "promoter_trend": "FLAT"}

    monkeypatch.setattr(live_scorer, "corporate_engine", _FakeCorporateEngine())
    monkeypatch.setattr(live_scorer, "institutional_engine", _FakeInstitutionalEngine())
    monkeypatch.setattr(live_scorer, "get_recent_institutional_activity", lambda ticker: (
        fetch_calls["deal_activity"].append(ticker) or {"has_buy_activity": True}
    ))

    return fetch_calls


class TestDisableFundamentalSignalsIsFalseForLivePath:
    """The one behavioral difference from backtesting/replay_engine.py
    this whole task exists to establish: live scanning must NOT skip
    fundamentals like a backtest replay does."""

    def test_categorize_called_with_disable_fundamental_signals_false(self, monkeypatch):
        calls = _fake_categorize_recorder(monkeypatch)
        _stub_out_market_and_history(monkeypatch)
        _stub_no_playwright_session(monkeypatch)
        _stub_fundamentals_sources(monkeypatch)

        live_scorer.score_live_candidates(_records_df())

        assert calls, "categorize() was never reached"
        assert all(c["disable_fundamental_signals"] is False for c in calls)

    def test_enable_microstructure_signals_left_at_default(self, monkeypatch):
        """Explicitly out of scope per this task's spec -- must not be
        silently turned on as a side effect of this wiring."""
        calls = _fake_categorize_recorder(monkeypatch)
        _stub_out_market_and_history(monkeypatch)
        _stub_no_playwright_session(monkeypatch)
        _stub_fundamentals_sources(monkeypatch)

        live_scorer.score_live_candidates(_records_df())

        assert all(c["enable_microstructure_signals"] is False for c in calls)


class TestFundamentalsMergedFromAllFourSources:

    def test_all_four_fetchers_called_once_per_ticker(self, monkeypatch):
        _fake_categorize_recorder(monkeypatch)
        _stub_out_market_and_history(monkeypatch)
        _stub_no_playwright_session(monkeypatch)
        fetch_calls = _stub_fundamentals_sources(monkeypatch)

        live_scorer.score_live_candidates(_records_df())

        assert fetch_calls["fundamental_cache"] == ["AAA.NS", "BBB.NS"]
        assert fetch_calls["corporate_engine"] == ["AAA.NS", "BBB.NS"]
        assert fetch_calls["deal_activity"] == ["AAA.NS", "BBB.NS"]
        # No live session -- falls back to the Yahoo-only snapshot call,
        # not get_shareholding_profile_with_trend().
        assert [c[0] for c in fetch_calls["institutional"]] == ["snapshot", "snapshot"]

    def test_candidate_receives_merged_fundamentals_fields(self, monkeypatch):
        calls = _fake_categorize_recorder(monkeypatch)
        _stub_out_market_and_history(monkeypatch)
        _stub_no_playwright_session(monkeypatch)
        _stub_fundamentals_sources(monkeypatch)

        live_scorer.score_live_candidates(_records_df())

        candidate = calls[0]["candidate"]
        assert candidate["ROCE"] == pytest.approx(18.0)
        assert candidate["margin_trend_yoy"] == "EXPANDING"
        assert candidate["days_to_earnings"] == 45
        assert candidate["institutional_sponsorship_pct"] == pytest.approx(22.0)
        assert candidate["has_buy_activity"] is True


class TestScreenerSessionLifecycle:

    def test_login_and_logout_called_once_not_per_ticker(self, monkeypatch):
        _fake_categorize_recorder(monkeypatch)
        _stub_out_market_and_history(monkeypatch)
        _stub_fundamentals_sources(monkeypatch)

        monkeypatch.setattr(live_scorer, "SCREENER_USERNAME", "user")
        monkeypatch.setattr(live_scorer, "SCREENER_PASSWORD", "pass")

        login_calls = []
        logout_calls = []

        def fake_login(username, password):
            login_calls.append((username, password))
            return ("fake_playwright", "fake_browser", "fake_page")

        def fake_logout(playwright, browser):
            logout_calls.append((playwright, browser))

        monkeypatch.setattr(live_scorer, "login", fake_login)
        monkeypatch.setattr(live_scorer, "logout", fake_logout)
        monkeypatch.setattr(live_scorer, "create_session", lambda **kwargs: _FakeSession())

        live_scorer.score_live_candidates(_records_df())

        assert len(login_calls) == 1, "login() must be called once per scan batch, not once per ticker"
        assert len(logout_calls) == 1

    def test_missing_credentials_skips_login_entirely_and_still_completes(self, monkeypatch):
        """No SCREENER_USERNAME/PASSWORD configured (the common dev/CI
        case) must not crash the whole scan -- it degrades to the
        Yahoo-only fundamentals snapshot."""
        calls = _fake_categorize_recorder(monkeypatch)
        _stub_out_market_and_history(monkeypatch)
        _stub_no_playwright_session(monkeypatch)
        _stub_fundamentals_sources(monkeypatch)

        def fail_login(*args, **kwargs):
            raise AssertionError("login() must not be called when credentials are missing")

        monkeypatch.setattr(live_scorer, "login", fail_login)

        result = live_scorer.score_live_candidates(_records_df())

        assert len(calls) == 2
        assert "category" in result.columns


class _FakeSession:
    def set_authenticated(self, value=True):
        pass


class TestEmptyAndMissingHistory:

    def test_empty_records_df_returns_unchanged_without_opening_a_session(self, monkeypatch):
        def fail_login(*args, **kwargs):
            raise AssertionError("login() must not be called when there's nothing to score")

        monkeypatch.setattr(live_scorer, "login", fail_login)
        monkeypatch.setattr(live_scorer, "SCREENER_USERNAME", "user")
        monkeypatch.setattr(live_scorer, "SCREENER_PASSWORD", "pass")

        result = live_scorer.score_live_candidates(pd.DataFrame())

        assert result.empty

    def test_missing_pattern_history_returns_no_data_not_a_crash(self, monkeypatch):
        _fake_categorize_recorder(monkeypatch)
        monkeypatch.setattr(live_scorer, "_compute_live_market_verdict", lambda: "FAVORABLE")
        monkeypatch.setattr(live_scorer, "_load_pattern_history", lambda ticker: None)
        _stub_no_playwright_session(monkeypatch)
        _stub_fundamentals_sources(monkeypatch)

        result = live_scorer.score_live_candidates(_records_df())

        assert (result["category"] == "NO_DATA").all()
        assert (result["confidence_score"] == 0.0).all()
