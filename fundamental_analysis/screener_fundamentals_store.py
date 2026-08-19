"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : screener_fundamentals_store.py
Package     : Fundamental Analysis

Purpose
-------
Persists the 9 fundamental ratio columns candidate_generation's own
Screener.in scrape already captures (candidate_generation/sources/
screener_adapter.py's EXPECTED_COLUMNS) so downstream scoring/display
code reads them from storage instead of making separate live Yahoo/NSE
calls for the same information -- see docs/known_data_issues.md item #4
for the full decision record.

Written ONCE per candidate-generation scrape
(candidate_generation/candidate_generator.py, right after each strategy's
run_source() call returns -- the raw per-strategy DataFrame still carries
every EXPECTED_COLUMNS field; consolidator.py's own groupby(...).agg(...)
step further downstream uses NAMED aggregations for a fixed column list
and silently drops every other column, so this cannot be hooked in after
consolidation without either changing consolidator.py's existing,
tested aggregation or losing the ratio columns entirely -- confirmed by
reading its implementation, not assumed).

Read by fundamental_cache.py / corporate_engine.py / institutional_engine.py's
redirected implementations (docs/known_data_issues.md item #4, Part 3).

Field-name/format contract preserved exactly: every get_*_display()/
get_*_trend() function below reproduces the SAME string/type shape the
OLD Yahoo-sourced function it replaces used to produce, so
candidate_assembler.py and ui/dashboard_data.py need zero changes to
consume this -- only the SOURCE changed.
===============================================================================
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from config import DATA_FOLDER
from common.logger import get_logger

logger = get_logger(__name__)

STORE_PATH = Path(DATA_FOLDER) / "screener_fundamentals_store.json"

# Screener column name (screener_adapter.EXPECTED_COLUMNS) -> stored field
# name. Kept as an explicit mapping (not just the raw Screener header
# text) so storage keys stay stable even if EXPECTED_COLUMNS' own wording
# ever changes.
COLUMN_TO_FIELD = {
    "ROCE %": "roce_pct",
    "Debt / Eq": "debt_to_equity_ratio",
    "Prom. Hold. %": "promoter_holding_pct",
    "Change in Prom Hold %": "promoter_holding_change_pct",
    "FII Hold %": "fii_holding_pct",
    "Chg in FII Hold %": "fii_holding_change_pct",
    "DII Hold %": "dii_holding_pct",
    "Chg in DII Hold %": "dii_holding_change_pct",
    "OPM Qtr %": "opm_latest_qtr_pct",
    "OPM PY Qtr %": "opm_preceding_year_qtr_pct",
}


def _load_store() -> dict[str, dict[str, Any]]:
    if not STORE_PATH.exists():
        return {}
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as ex:
        logger.warning("Failed to load screener fundamentals store: %s", ex)
        return {}


def _save_store(store: dict[str, dict[str, Any]]) -> None:
    try:
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(STORE_PATH, "w", encoding="utf-8") as fh:
            json.dump(store, fh, indent=2)
    except Exception as ex:
        logger.warning("Failed to save screener fundamentals store: %s", ex)


def save_from_candidate_table(df: pd.DataFrame) -> None:
    """
    Persists the 10 covered fields (see COLUMN_TO_FIELD) for every row in
    df -- a raw per-strategy candidate DataFrame straight from
    source_runner.run_source(), still carrying every
    screener_adapter.EXPECTED_COLUMNS field (call this BEFORE
    consolidator.consolidate(), not after -- see this module's own
    docstring for why).

    Overwrites each ticker's prior entry unconditionally (today's scrape
    is always the freshest available data) -- no staleness/TTL logic
    here, unlike fundamental_cache.py's old 7-day cache, since this runs
    fresh every scan rather than being fetched lazily per-candidate.

    Silently skips a row whose Symbol is missing/blank rather than
    raising -- one malformed row must not lose the rest of the scan's
    data. Never raises -- a persistence failure must not block candidate
    generation itself.
    """
    if df is None or df.empty or "Symbol" not in df.columns:
        return

    try:
        store = _load_store()
        scraped_at = datetime.now().isoformat()
        written = 0

        for _, row in df.iterrows():
            symbol = row.get("Symbol")
            if not symbol or pd.isna(symbol):
                continue

            ticker = str(symbol) if str(symbol).endswith(".NS") else f"{symbol}.NS"

            entry: dict[str, Any] = {"scraped_at": scraped_at}
            for column, field in COLUMN_TO_FIELD.items():
                value = row.get(column) if column in df.columns else None
                entry[field] = None if value is None or pd.isna(value) else float(value)

            store[ticker] = entry
            written += 1

        _save_store(store)
        logger.info("Screener fundamentals store: persisted %d ticker(s).", written)

    except Exception as ex:
        logger.warning("Screener fundamentals store: failed to persist candidate table: %s", ex)


def get_stored_fundamentals(ticker: str) -> Optional[dict[str, Any]]:
    """Raw stored fields for `ticker`, or None if this ticker was never
    captured by a candidate-generation scrape (never scanned, or scanned
    before this store existed)."""
    formatted = ticker if ticker.endswith(".NS") else f"{ticker}.NS"
    store = _load_store()
    return store.get(formatted)


def _classify(latest, prior, up: str, down: str, flat: str) -> Optional[str]:
    """Same threshold-free comparison every existing trend classifier in
    this codebase already uses (shareholding_scraper.py's
    _classify_trend(), corporate_engine.py's _classify_margin_trend()) --
    reused via this one shared helper rather than re-implemented three
    times with the same three lines. None in, None out -- missing data
    is a real "no signal" state, not a fabricated FLAT."""
    if latest is None or prior is None:
        return None
    if latest > prior:
        return up
    if latest < prior:
        return down
    return flat


def get_roce_display(ticker: str) -> str:
    """Matches fundamental_analysis.metrics_engine.MetricsEngine.get_roce()'s
    exact old return shape: "XX.XX%" or "N/A"."""
    stored = get_stored_fundamentals(ticker)
    value = stored.get("roce_pct") if stored else None
    return "N/A" if value is None else f"{value:.2f}%"


def get_debt_to_equity_display(ticker: str) -> str:
    """Matches the old Yahoo-sourced "XX.XX%" convention
    (candidate_assembler.py's _parse_formatted_percentage() divides this
    by 100 to recover the real ratio) -- Screener's own "Debt / Eq"
    column is already a plain ratio (0.27, not "27.00%"), so it's
    multiplied by 100 here to land back on the exact scale every existing
    consumer already expects. "N/A" for a missing/unscraped value or a
    genuinely zero ratio -- an honest real 0%, not a reproduction of the
    old Yahoo "DEBT_FREE" sentinel, which nothing downstream still reads
    (the disqualifier it fed was removed -- docs/known_data_issues.md
    item #3)."""
    stored = get_stored_fundamentals(ticker)
    value = stored.get("debt_to_equity_ratio") if stored else None
    return "N/A" if value is None else f"{value * 100:.2f}%"


def get_promoter_holding_display(ticker: str) -> str:
    """Matches institutional_engine.get_shareholding_profile()'s old
    "XX.XX%" convention for promoter_holding."""
    stored = get_stored_fundamentals(ticker)
    value = stored.get("promoter_holding_pct") if stored else None
    return "UNKNOWN" if value is None else f"{value:.2f}%"


def get_promoter_trend(ticker: str) -> Optional[str]:
    """INCREASING/DECREASING/FLAT from Screener's own "Change in Prom
    Hold %" column -- a pre-computed delta, not two raw points, so this
    classifies directly off its sign against zero (the same threshold-
    free >/</else convention every other trend classifier here uses)
    rather than needing a separate "prior" value to compare against."""
    stored = get_stored_fundamentals(ticker)
    change = stored.get("promoter_holding_change_pct") if stored else None
    return _classify(change, 0.0, "INCREASING", "DECREASING", "FLAT")


def get_fii_trend(ticker: str) -> Optional[str]:
    """Same convention as get_promoter_trend(), off "Chg in FII Hold %"."""
    stored = get_stored_fundamentals(ticker)
    change = stored.get("fii_holding_change_pct") if stored else None
    return _classify(change, 0.0, "INCREASING", "DECREASING", "FLAT")


def get_dii_trend(ticker: str) -> Optional[str]:
    """Same convention as get_promoter_trend(), off "Chg in DII Hold %"."""
    stored = get_stored_fundamentals(ticker)
    change = stored.get("dii_holding_change_pct") if stored else None
    return _classify(change, 0.0, "INCREASING", "DECREASING", "FLAT")


def get_margin_trend_yoy(ticker: str) -> Optional[str]:
    """EXPANDING/CONTRACTING/FLAT from Screener's OPM Qtr % vs OPM PY
    Qtr % (same quarter, one year ago) -- the same YoY comparison window
    corporate_engine.py's old Yahoo-based margin_trend_yoy used, now
    comparing OPM (core operating margin) instead of NPM (net margin,
    noisier from tax/one-off items -- confirmed directly: HCLTECH/WIPRO/
    POWERGRID all showed the two disagreeing on trend DIRECTION, not just
    magnitude, per docs/known_data_issues.md item #4)."""
    stored = get_stored_fundamentals(ticker)
    if not stored:
        return None
    latest = stored.get("opm_latest_qtr_pct")
    prior_year = stored.get("opm_preceding_year_qtr_pct")
    return _classify(latest, prior_year, "EXPANDING", "CONTRACTING", "FLAT")
