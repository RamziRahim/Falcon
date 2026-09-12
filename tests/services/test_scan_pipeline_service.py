"""
Tests for services/scan_pipeline_service.py -- the New Scan orchestration
that wires market data collection (Phase 3), indicator calculation
(Phase 4), and pattern detection (Phase 5) together. This is fundamentally
an integration/wiring regression test: a stage getting silently dropped or
reordered here is exactly the bug this module exists to prevent.
"""
from __future__ import annotations

from unittest.mock import Mock, patch

import pandas as pd
import pytest

import services.scan_pipeline_service as svc
from market_data.data_collection_engine import DataCollectionResult
from technical_analysis.indicator_engine import IndicatorEngineResult


@pytest.fixture
def mocked_pipeline():
    """
    Patches all four collaborators inside scan_pipeline_service and returns
    a shared call-order-tracking Mock manager alongside them.
    """
    manager = Mock()

    with patch.object(svc, "DataCollectionEngine") as mock_dce_cls, \
         patch.object(svc, "IndicatorEngine") as mock_ie_cls, \
         patch.object(svc, "PatternEngine") as mock_pe_cls, \
         patch.object(svc, "build_candidate_table") as mock_build, \
         patch.object(svc, "scoring_engine") as mock_scoring, \
         patch.object(svc, "score_live_candidates") as mock_score_live, \
         patch.object(svc, "is_live_market_hours") as mock_market_hours, \
         patch.object(svc, "fetch_todays_intraday_bars") as mock_fetch_intraday:

        mock_dce_cls.return_value.run.return_value = DataCollectionResult()
        mock_ie_cls.return_value.run.return_value = IndicatorEngineResult()
        mock_build.return_value = pd.DataFrame()
        # Pass-through by default -- real categorize()-wiring behavior is
        # covered by tests/decision_engine/test_live_scorer.py; this test
        # module only needs to prove the *pipeline* calls it, without
        # hitting real Playwright/network fetches per test run.
        mock_score_live.side_effect = lambda df: df
        # Defaults to "market closed" so existing tests (none of which
        # assert on vwap_* columns) never trigger a real yfinance fetch
        # for a fake ticker -- VWAP-reclaim-specific tests below override
        # this explicitly.
        mock_market_hours.return_value = False
        mock_fetch_intraday.return_value = pd.DataFrame()

        manager.attach_mock(mock_dce_cls.return_value.run, "data_collection_run")
        manager.attach_mock(mock_ie_cls.return_value.run, "indicator_run")
        manager.attach_mock(mock_pe_cls.return_value.execute_pipeline, "pattern_execute")
        manager.attach_mock(mock_build, "build_candidate_table")

        yield {
            "manager": manager,
            "dce_cls": mock_dce_cls,
            "ie_cls": mock_ie_cls,
            "pe_cls": mock_pe_cls,
            "build": mock_build,
            "scoring": mock_scoring,
            "score_live": mock_score_live,
            "market_hours": mock_market_hours,
            "fetch_intraday": mock_fetch_intraday,
        }


class TestEngineCallOrder:
    """Regression test for the exact gap that caused this module to exist:
    someone re-shuffling this block later and silently dropping a stage."""

    def test_stages_run_in_correct_order(self, mocked_pipeline):
        svc.run_new_scan_pipeline(["DEMO.NS"])

        call_names = [call[0] for call in mocked_pipeline["manager"].mock_calls]
        assert call_names == [
            "data_collection_run",
            "indicator_run",
            "pattern_execute",
            "build_candidate_table",
        ], (
            "New Scan must run market data collection, then indicators, then "
            "patterns, then build the candidate table -- in that order."
        )

    def test_engines_receive_the_full_ticker_universe(self, mocked_pipeline):
        universe = ["A.NS", "B.NS", "C.NS"]
        svc.run_new_scan_pipeline(universe)

        # DataCollectionEngine.run() also receives on_download_progress now
        # (the live per-ticker progress callback) -- checked separately
        # below, so only the symbols kwarg is asserted here rather than
        # the full call signature.
        dce_kwargs = mocked_pipeline["dce_cls"].return_value.run.call_args.kwargs
        assert dce_kwargs["symbols"] == universe
        mocked_pipeline["ie_cls"].return_value.run.assert_called_once_with(symbols=universe)
        mocked_pipeline["build"].assert_called_once_with(universe)
        # 2026-08-22: pattern detection scoped to today's universe too --
        # it used to reprocess the ENTIRE data/technical/ cache regardless
        # of ticker_universe, confirmed live as the largest phase of a
        # real scan once that cache grows across days.
        mocked_pipeline["pe_cls"].return_value.execute_pipeline.assert_called_once_with(ticker_universe=universe)

    def test_data_collection_receives_a_download_progress_callback(self, mocked_pipeline):
        svc.run_new_scan_pipeline(["DEMO.NS"])

        dce_kwargs = mocked_pipeline["dce_cls"].return_value.run.call_args.kwargs
        assert callable(dce_kwargs["on_download_progress"])

    def test_stage_callback_fires_for_each_stage_in_order(self, mocked_pipeline):
        stages_seen = []
        svc.run_new_scan_pipeline(["DEMO.NS"], on_stage=stages_seen.append)

        assert len(stages_seen) == 3
        assert "data" in stages_seen[0].lower() or "download" in stages_seen[0].lower()
        assert "indicator" in stages_seen[1].lower()
        assert "pattern" in stages_seen[2].lower()

    def test_on_stage_is_optional(self, mocked_pipeline):
        """Must not crash when no progress callback is supplied."""
        svc.run_new_scan_pipeline(["DEMO.NS"], on_stage=None)


class TestDownloadProgressNotifier:
    """_make_download_progress_notifier() -- real per-ticker progress
    messages with a remaining-time estimate computed from THIS run's own
    observed pace (time.monotonic()-based), not a hardcoded guess, per
    the same fix already applied to backtesting/backtest_runner.py's own
    progress estimate."""

    def test_message_includes_completed_and_total_counts(self):
        messages = []
        notifier = svc._make_download_progress_notifier(messages.append, total=50)

        notifier(1, 50, "AETHER.NS")

        assert "1/50" in messages[0]

    def test_eta_shrinks_as_more_tickers_complete_at_a_steady_pace(self, monkeypatch):
        # Simulated steady 2s/ticker pace via a fake monotonic clock --
        # deterministic, no real sleeping needed.
        fake_time = {"now": 0.0}
        monkeypatch.setattr(svc.time, "monotonic", lambda: fake_time["now"])

        messages = []
        notifier = svc._make_download_progress_notifier(messages.append, total=10)

        fake_time["now"] = 2.0
        notifier(1, 10, "A.NS")  # 2s elapsed / 1 done -> 9 remaining * 2s/ea = ~18s left

        fake_time["now"] = 18.0
        notifier(9, 10, "I.NS")  # 18s elapsed / 9 done -> 1 remaining * 2s/ea = ~2s left

        assert "18s" in messages[0] or "~18s" in messages[0]
        assert "2s" in messages[1] or "~2s" in messages[1]

    def test_final_ticker_reports_done_not_a_zero_second_eta(self, monkeypatch):
        fake_time = {"now": 0.0}
        monkeypatch.setattr(svc.time, "monotonic", lambda: fake_time["now"])

        messages = []
        notifier = svc._make_download_progress_notifier(messages.append, total=3)

        fake_time["now"] = 6.0
        notifier(3, 3, "C.NS")

        assert "done" in messages[0].lower()

    def test_eta_over_a_minute_reported_in_minutes(self, monkeypatch):
        fake_time = {"now": 0.0}
        monkeypatch.setattr(svc.time, "monotonic", lambda: fake_time["now"])

        messages = []
        notifier = svc._make_download_progress_notifier(messages.append, total=100)

        fake_time["now"] = 10.0
        notifier(1, 100, "A.NS")  # 10s/ticker * 99 remaining = 990s = 16.5m

        assert "m" in messages[0]
        assert "s remaining" not in messages[0]


class TestResultComposition:

    def test_scoring_merged_when_records_non_empty(self, mocked_pipeline):
        mocked_pipeline["build"].return_value = pd.DataFrame({"Symbol": ["DEMO.NS"], "Price": [100.0]})
        mocked_pipeline["scoring"].score_universe.return_value = pd.DataFrame(
            {"Symbol": ["DEMO.NS"], "RS_Rating": [88]}
        )

        result = svc.run_new_scan_pipeline(["DEMO.NS"])

        assert "RS_Rating" in result.records_df.columns
        assert result.records_df.loc[0, "RS_Rating"] == 88

    def test_scoring_skipped_when_records_empty(self, mocked_pipeline):
        mocked_pipeline["build"].return_value = pd.DataFrame()

        result = svc.run_new_scan_pipeline(["DEMO.NS"])

        mocked_pipeline["scoring"].score_universe.assert_not_called()
        mocked_pipeline["score_live"].assert_not_called()
        assert result.records_df.empty

    def test_categorize_wiring_runs_when_records_non_empty(self, mocked_pipeline):
        """decision_engine.live_scorer.score_live_candidates() -- the
        categorize() wiring itself -- must actually be invoked with the
        scored candidate table, and its result (not the pre-categorize
        table) must be what ends up in records_df."""
        mocked_pipeline["build"].return_value = pd.DataFrame({"Symbol": ["DEMO.NS"], "Price": [100.0]})
        mocked_pipeline["scoring"].score_universe.return_value = pd.DataFrame(
            {"Symbol": ["DEMO.NS"], "RS_Rating": [88]}
        )
        mocked_pipeline["score_live"].side_effect = lambda df: df.assign(category=["EXECUTE"])

        result = svc.run_new_scan_pipeline(["DEMO.NS"])

        mocked_pipeline["score_live"].assert_called_once()
        called_with_df = mocked_pipeline["score_live"].call_args[0][0]
        assert "RS_Rating" in called_with_df.columns, (
            "score_live_candidates must be called AFTER scoring_engine's merge, "
            "not before -- it needs RS_Rating/Sector already present."
        )
        assert result.records_df.loc[0, "category"] == "EXECUTE"

    def test_vwap_reclaim_skipped_outside_market_hours(self, mocked_pipeline):
        mocked_pipeline["build"].return_value = pd.DataFrame({"Symbol": ["DEMO.NS"], "Price": [100.0]})
        mocked_pipeline["score_live"].side_effect = lambda df: df.assign(category=["EXECUTE"])
        mocked_pipeline["market_hours"].return_value = False

        result = svc.run_new_scan_pipeline(["DEMO.NS"])

        mocked_pipeline["fetch_intraday"].assert_not_called()
        assert result.records_df.loc[0, "vwap_invalidated_reason"] == "market_closed"
        assert bool(result.records_df.loc[0, "vwap_reclaimed"]) is False

    def test_vwap_reclaim_fetched_only_for_execute_and_watchlist(self, mocked_pipeline):
        mocked_pipeline["build"].return_value = pd.DataFrame(
            {"Symbol": ["EXEC.NS", "WATCH.NS", "MON.NS", "AVOID.NS"], "Price": [100.0] * 4}
        )
        mocked_pipeline["score_live"].side_effect = lambda df: df.assign(
            category=["EXECUTE", "ALERT_WATCHLIST", "MONITOR", "AVOID"]
        )
        mocked_pipeline["market_hours"].return_value = True
        mocked_pipeline["fetch_intraday"].return_value = pd.DataFrame()

        svc.run_new_scan_pipeline(["EXEC.NS", "WATCH.NS", "MON.NS", "AVOID.NS"])

        fetched_symbols = {call.args[0] for call in mocked_pipeline["fetch_intraday"].call_args_list}
        assert fetched_symbols == {"EXEC.NS", "WATCH.NS"}, (
            "VWAP Reclaim must be fetched only for the day's EXECUTE/WATCHLIST "
            "candidates, never MONITOR/AVOID and never the full universe."
        )

    def test_vwap_reclaim_never_changes_category_or_predicted_p(self, mocked_pipeline):
        """Acceptance criterion: this field is purely informational and
        must never feed back into the decision that already happened."""
        mocked_pipeline["build"].return_value = pd.DataFrame({"Symbol": ["DEMO.NS"], "Price": [100.0]})
        mocked_pipeline["score_live"].side_effect = lambda df: df.assign(
            category=["EXECUTE"], predicted_p=[0.77],
        )
        mocked_pipeline["market_hours"].return_value = True
        mocked_pipeline["fetch_intraday"].return_value = pd.DataFrame({
            "Datetime": pd.date_range("2026-09-04 09:15", periods=20, freq="min"),
            "High": [100.0] * 20, "Low": [100.0] * 20, "Close": [100.0] * 20,
            "Volume": [1000.0] * 20,
        })

        result = svc.run_new_scan_pipeline(["DEMO.NS"])

        assert result.records_df.loc[0, "category"] == "EXECUTE"
        assert result.records_df.loc[0, "predicted_p"] == pytest.approx(0.77)
        # And the VWAP fields themselves are real, not just absent.
        assert result.records_df.loc[0, "vwap_invalidated_reason"] is None

    def test_returns_collection_and_indicator_results(self, mocked_pipeline):
        collection = DataCollectionResult(downloaded=5, updated=5, failed=1, warnings=0)
        indicator = IndicatorEngineResult(processed=4, exported=4, failed=0, skipped=1)
        mocked_pipeline["dce_cls"].return_value.run.return_value = collection
        mocked_pipeline["ie_cls"].return_value.run.return_value = indicator

        result = svc.run_new_scan_pipeline(["DEMO.NS"])

        assert result.collection_result is collection
        assert result.indicator_result is indicator
