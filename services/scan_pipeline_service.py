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

import time
from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

from market_data.data_collection_engine import DataCollectionEngine, DataCollectionResult
from technical_analysis.indicator_engine import IndicatorEngine, IndicatorEngineResult
from technical_analysis.pattern_engine import PatternEngine
from technical_analysis.candidate_table_builder import build_candidate_table
from scoring.scoring_engine import scoring_engine
from decision_engine.live_scorer import score_live_candidates

StageCallback = Callable[[str], None]


def _format_eta(seconds: float) -> str:
    if seconds < 60:
        return f"~{seconds:.0f}s"
    return f"~{seconds / 60:.1f}m"


def _make_download_progress_notifier(notify: StageCallback, total: int) -> Callable[[int, int, str], None]:
    """Remaining-time estimate computed from THIS run's own observed pace
    (time.monotonic()-based elapsed / completed * remaining), same fix
    already applied to backtesting/backtest_runner.py's own progress
    estimate -- a hardcoded per-ticker guess would repeat that estimate's
    original mistake (wrong by ~9-10x), since real NSE fetch latency
    varies with cache hit rate and network conditions, not a constant.
    Recomputed on every call (not just once), so the estimate tightens as
    the scan progresses instead of staying frozen at a first guess."""
    started_at = time.monotonic()

    def _on_progress(completed: int, total_count: int, symbol: str) -> None:
        elapsed = time.monotonic() - started_at
        per_ticker = elapsed / completed
        remaining = per_ticker * (total_count - completed)
        eta_suffix = "done" if completed >= total_count else f"{_format_eta(remaining)} remaining"
        notify(f"Downloading market data ({completed}/{total_count} tickers, {eta_suffix})...")

    return _on_progress


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
    candidate table from the now-real pattern data, then runs each
    candidate through decision_engine.leadership_decision_engine.categorize()
    (via decision_engine.live_scorer.score_live_candidates()) -- the same
    deterministic decision cascade backtesting/replay_engine.py already
    uses, evaluated against live/current data instead of a historical replay.

    Always runs all three stages for the full universe on every call --
    DataCollectionEngine is already incremental (cheap for tickers seen
    before), so this doesn't re-download unchanged history.

    on_stage is called repeatedly as real stage transitions actually
    happen (not a fixed animation): once per download-stage ticker
    completion (with a live remaining-time estimate, see
    _make_download_progress_notifier), then once each for the
    indicators/patterns/scoring stage transitions. Callers wanting a
    "Fetching candidates from Screener..." stage message should emit that
    themselves before calling this function -- candidate generation
    itself happens upstream of ticker_universe even existing.
    """

    def _notify(message: str) -> None:
        if on_stage is not None:
            on_stage(message)

    _notify(f"Downloading market data (0/{len(ticker_universe)} tickers)...")
    download_progress = _make_download_progress_notifier(_notify, len(ticker_universe))
    collection_result = DataCollectionEngine().run(symbols=ticker_universe, on_download_progress=download_progress)

    _notify("Calculating technical indicators...")
    indicator_result = IndicatorEngine().run(symbols=ticker_universe)

    _notify("Detecting chart patterns...")
    PatternEngine().execute_pipeline()

    records_df = build_candidate_table(ticker_universe)

    if not records_df.empty:
        scored_df = scoring_engine.score_universe(symbols=records_df["Symbol"].tolist())
        if not scored_df.empty:
            records_df = records_df.merge(scored_df, on="Symbol", how="left")

        _notify("Scoring & categorizing candidates...")
        records_df = score_live_candidates(records_df)

    return ScanPipelineResult(
        records_df=records_df,
        collection_result=collection_result,
        indicator_result=indicator_result,
    )
