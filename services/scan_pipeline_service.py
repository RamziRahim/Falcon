"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : scan_pipeline_service.py
Package     : Services

Purpose
-------
Orchestrates the full "New Scan" pipeline for the UI: market data collection
(Phase 3) -> indicator calculation (Phase 4) -> pattern detection (Phase 5)
-> candidate table assembly -> scoring.

Kept Streamlit-free (no st.* calls) so the pipeline and its call order are
directly testable without importing app.py's side-effecting top-level
script. Stage progress is reported via an optional on_stage callback rather
than calling st.empty()/st.info() here directly.

===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

from market_data.data_collection_engine import DataCollectionEngine, DataCollectionResult
from technical_analysis.indicator_engine import IndicatorEngine, IndicatorEngineResult
from technical_analysis.pattern_engine import PatternEngine
from technical_analysis.candidate_table_builder import build_candidate_table
from scoring.scoring_engine import scoring_engine

StageCallback = Callable[[str], None]


@dataclass(slots=True)
class ScanPipelineResult:
    records_df: pd.DataFrame
    collection_result: DataCollectionResult
    indicator_result: IndicatorEngineResult


def run_new_scan_pipeline(
    ticker_universe: list[str],
    on_stage: Optional[StageCallback] = None,
) -> ScanPipelineResult:
    """
    Runs Phase 3 (market data), Phase 4 (indicators), and Phase 5 (patterns)
    for ticker_universe, then assembles and scores the display-ready
    candidate table from the now-real pattern data.

    Always runs all three stages for the full universe on every call --
    DataCollectionEngine is already incremental (cheap for tickers seen
    before), so this doesn't re-download unchanged history.
    """

    def _notify(message: str) -> None:
        if on_stage is not None:
            on_stage(message)

    _notify(f"Downloading market data for {len(ticker_universe)} tickers...")
    collection_result = DataCollectionEngine().run(symbols=ticker_universe)

    _notify("Calculating technical indicators...")
    indicator_result = IndicatorEngine().run(symbols=ticker_universe)

    _notify("Detecting chart patterns...")
    PatternEngine().execute_pipeline()

    records_df = build_candidate_table(ticker_universe)

    if not records_df.empty:
        scored_df = scoring_engine.score_universe(symbols=records_df["Symbol"].tolist())
        if not scored_df.empty:
            records_df = records_df.merge(scored_df, on="Symbol", how="left")

    return ScanPipelineResult(
        records_df=records_df,
        collection_result=collection_result,
        indicator_result=indicator_result,
    )
