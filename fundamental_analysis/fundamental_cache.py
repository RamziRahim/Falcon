"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : fundamental_cache.py
Package     : Fundamental Analysis

Purpose
-------
Caches fundamental_engine.get_complete_data_packet() results per ticker.
Without this, every scan of a 20-50 ticker candidate table would fire
~3 separate live yfinance calls per row (corporate_engine, metrics_engine,
institutional_engine each hit yf.Ticker() independently) — a real
rate-limit/latency risk.

Mirrors scoring/sector_map.py's cache-then-check-staleness pattern.

===============================================================================
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

from config import DATA_FOLDER

from common.logger import get_logger
from fundamental_analysis.fundamental_engine import fundamental_engine
from fundamental_analysis.metrics_engine import metrics_engine

logger = get_logger(__name__)

CACHE_PATH = Path(DATA_FOLDER) / "fundamentals_cache.json"

# Fundamentals move slowly; quarterly data doesn't need daily refetching,
# but earnings dates do shift — 7 days balances freshness vs. API load.
REFRESH_INTERVAL_DAYS = 7

NA_PACKET = {
    "roce": "N/A",
    "revenue_yoy_quarterly_growth": "DATA_GAP",
    "debt_to_equity": "N/A",
}


class FundamentalCache:
    """
    Cache-then-check-staleness wrapper around
    fundamental_engine.get_complete_data_packet(), flattened to the fields
    the UI actually consumes.
    """

    def __init__(self) -> None:

        self._cache = self._load_cache()

    # ------------------------------------------------------------------ #

    def _load_cache(self) -> Dict[str, Dict[str, Any]]:

        if not CACHE_PATH.exists():
            return {}

        try:

            with open(CACHE_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)

        except Exception as ex:

            logger.warning("Failed to load fundamentals cache: %s", ex)
            return {}

    # ------------------------------------------------------------------ #

    def _save_cache(self) -> None:

        try:

            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

            with open(CACHE_PATH, "w", encoding="utf-8") as fh:
                json.dump(self._cache, fh, indent=2)

        except Exception as ex:

            logger.warning("Failed to save fundamentals cache: %s", ex)

    # ------------------------------------------------------------------ #

    def _is_stale(self, entry: Dict[str, Any]) -> bool:

        fetched_at = entry.get("fetched_at")

        if not fetched_at:
            return True

        try:
            fetched = datetime.fromisoformat(fetched_at)
        except ValueError:
            return True

        return datetime.now() - fetched > timedelta(days=REFRESH_INTERVAL_DAYS)

    # ------------------------------------------------------------------ #

    def get_fundamentals(self, ticker: str, force_refresh: bool = False) -> dict:
        """
        Returns a flattened fundamentals dict for a ticker: roce,
        revenue_yoy_quarterly_growth, debt_to_equity.

        1. Fresh cache entry -> return it.
        2. Stale or missing -> fetch via fundamental_engine +
           metrics_engine.get_roce(), cache with a fetched_at timestamp,
           return it.
        3. Fetch failure -> serve stale cache if one exists, else an
           explicit "N/A" packet (never a silently fabricated number).
        """

        cached = self._cache.get(ticker)

        if not force_refresh and cached and not self._is_stale(cached):
            return cached["data"]

        try:

            packet = fundamental_engine.get_complete_data_packet(ticker)

            data = {
                "roce": metrics_engine.get_roce(ticker),
                "revenue_yoy_quarterly_growth": packet["quarterly_financials"].get(
                    "revenue_yoy_quarterly_growth", "DATA_GAP"
                ),
                "debt_to_equity": packet["balance_sheet_vitals"].get(
                    "debt_to_equity", "N/A"
                ),
            }

            self._cache[ticker] = {
                "data": data,
                "fetched_at": datetime.now().isoformat(),
            }

            self._save_cache()

            return data

        except Exception as ex:

            logger.warning("Fundamentals fetch failed for %s: %s", ticker, ex)

            if cached:
                return cached["data"]

            return dict(NA_PACKET)


fundamental_cache = FundamentalCache()


def get_fundamentals(ticker: str, force_refresh: bool = False) -> dict:
    """Module-level convenience wrapper around the shared FundamentalCache instance."""
    return fundamental_cache.get_fundamentals(ticker, force_refresh=force_refresh)
