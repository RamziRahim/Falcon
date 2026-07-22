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
         patch.object(svc, "score_live_candidates") as mock_score_live:

        mock_dce_cls.return_value.run.return_value = DataCollectionResult()
        mock_ie_cls.return_value.run.return_value = IndicatorEngineResult()
        mock_build.return_value = pd.DataFrame()
        # Pass-through by default -- real categorize()-wiring behavior is
        # covered by tests/decision_engine/test_live_scorer.py; this test
        # module only needs to prove the *pipeline* calls it, without
        # hitting real Playwright/network fetches per test run.
        mock_score_live.side_effect = lambda df: df

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

        mocked_pipeline["dce_cls"].return_value.run.assert_called_once_with(symbols=universe)
        mocked_pipeline["ie_cls"].return_value.run.assert_called_once_with(symbols=universe)
        mocked_pipeline["build"].assert_called_once_with(universe)

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

    def test_returns_collection_and_indicator_results(self, mocked_pipeline):
        collection = DataCollectionResult(downloaded=5, updated=5, failed=1, warnings=0)
        indicator = IndicatorEngineResult(processed=4, exported=4, failed=0, skipped=1)
        mocked_pipeline["dce_cls"].return_value.run.return_value = collection
        mocked_pipeline["ie_cls"].return_value.run.return_value = indicator

        result = svc.run_new_scan_pipeline(["DEMO.NS"])

        assert result.collection_result is collection
        assert result.indicator_result is indicator
