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
from market_data.intraday_fetcher import fetch_todays_intraday_bars
from market_data.market_hours import is_live_market_hours
from technical_analysis.indicator_engine import IndicatorEngine, IndicatorEngineResult
from technical_analysis.pattern_engine import PatternEngine
from technical_analysis.candidate_table_builder import build_candidate_table
from technical_analysis.vwap_reclaim import NO_RECLAIM_RESULT, compute_vwap_reclaim_status
from scoring.scoring_engine import scoring_engine
from decision_engine.live_scorer import score_live_candidates

# The only categories VWAP Reclaim is computed for -- the day's already-
# filtered EXECUTE/WATCHLIST candidates (typically single digits to ~20),
# never the full universe. See _attach_vwap_reclaim_status()'s own
# docstring for the cost justification.
VWAP_RECLAIM_CATEGORIES = {"EXECUTE", "ALERT_WATCHLIST"}

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


def _attach_vwap_reclaim_status(records_df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds vwap_reclaimed / currently_above_vwap / vwap_value /
    dipped_below_vwap_today / vwap_invalidated_reason columns -- purely
    informational (VWAP Reclaim spec, Part 3). Must run AFTER
    score_live_candidates() has already set `category`, and reads that
    column only to decide which rows to fetch for -- it never feeds
    anything back into category/predicted_p/compute_score(), and this is
    exactly why it's wired here rather than inside live_scorer.py's own
    categorize()-calling loop.

    Scoped strictly to today's EXECUTE/WATCHLIST candidates
    (VWAP_RECLAIM_CATEGORIES) -- confirmed live (Part 1's investigation)
    that fetching intraday bars for a typical day's count of those
    (single digits to ~20) takes ~5 seconds total via yfinance, immaterial
    against a 28-58 minute scan. Fetching this for the FULL universe
    (100+ tickers) was explicitly out of scope -- that's the real
    infrastructure cost this design avoids.

    Same-day-only signal: skipped entirely outside live NSE trading hours
    (market_data.market_hours.is_live_market_hours()) -- every row gets
    invalidated_reason="market_closed" rather than a stale or fabricated
    value, matching ui/header.py's own "Market Closed" framing instead of
    silently showing something that looks like a live reading when it
    isn't one.
    """
    if records_df.empty or "category" not in records_df.columns:
        return records_df

    records_df = records_df.copy()
    market_live = is_live_market_hours()

    def _status_for_row(row: pd.Series) -> dict:
        if not market_live:
            return dict(NO_RECLAIM_RESULT, invalidated_reason="market_closed")
        if row["category"] not in VWAP_RECLAIM_CATEGORIES:
            return dict(NO_RECLAIM_RESULT, invalidated_reason="not_a_filtered_candidate")
        bars = fetch_todays_intraday_bars(row["Symbol"])
        return compute_vwap_reclaim_status(bars)

    statuses = [_status_for_row(row) for _, row in records_df.iterrows()]

    records_df["vwap_reclaimed"] = [s["vwap_reclaimed"] for s in statuses]
    records_df["currently_above_vwap"] = [s["currently_above_vwap"] for s in statuses]
    records_df["vwap_value"] = [s["vwap_value"] for s in statuses]
    records_df["dipped_below_vwap_today"] = [s["dipped_below_vwap_today"] for s in statuses]
    records_df["vwap_invalidated_reason"] = [s["invalidated_reason"] for s in statuses]

    return records_df


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
    # Scoped to today's ticker_universe (2026-08-22) -- execute_pipeline()
    # used to reprocess data/technical/'s ENTIRE cached history every
    # scan (568+ tickers accumulated across days of testing), confirmed
    # live as the single largest phase of a real scan (~20 of ~50+
    # total minutes). A ticker outside today's universe keeps whatever
    # data/patterns/*.parquet it already has -- exactly the staleness
    # case ui/dashboard_data.py's format_stale_data_notice() already
    # exists to surface, not a new gap.
    PatternEngine().execute_pipeline(ticker_universe=ticker_universe)

    records_df = build_candidate_table(ticker_universe)

    if not records_df.empty:
        scored_df = scoring_engine.score_universe(symbols=records_df["Symbol"].tolist())
        if not scored_df.empty:
            records_df = records_df.merge(scored_df, on="Symbol", how="left")

        _notify("Scoring & categorizing candidates...")
        records_df = score_live_candidates(records_df)

        # Runs strictly after categorization -- see _attach_vwap_reclaim_status()'s
        # own docstring for why this must never move earlier.
        records_df = _attach_vwap_reclaim_status(records_df)

    return ScanPipelineResult(
        records_df=records_df,
        collection_result=collection_result,
        indicator_result=indicator_result,
    )
