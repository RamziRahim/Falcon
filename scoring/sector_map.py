"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : sector_map.py
Package     : Scoring

Purpose
-------
Resolves and caches sector/industry classification per ticker.

Responsibilities
----------------
• Check manual overrides (scoring/sector_overrides.csv) first
• Fall back to a long-cycle local cache (data/sector_map.json)
• Fall back to YahooProvider.get_company_info() when cache is missing/stale

===============================================================================
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from config import DATA_FOLDER

from common.logger import get_logger
from market_data.providers.yahoo_provider import market_provider
from scoring.exceptions import SectorMappingError

logger = get_logger(__name__)

SECTOR_MAP_PATH = Path(DATA_FOLDER) / "sector_map.json"

OVERRIDES_PATH = Path(__file__).resolve().parent / "sector_overrides.csv"

# Sector classification rarely changes — refresh on a long cycle, not per scan
REFRESH_INTERVAL_DAYS = 30

UNKNOWN_SECTOR = "Unknown"
UNKNOWN_INDUSTRY = "Unknown"


class SectorMap:
    """
    Resolves sector/industry per ticker with manual-override + cache-then-Yahoo fallback.
    """

    def __init__(self) -> None:

        self._overrides = self._load_overrides()
        self._cache = self._load_cache()

    # ------------------------------------------------------------------ #

    def _load_overrides(self) -> Dict[str, str]:

        if not OVERRIDES_PATH.exists():
            return {}

        try:

            df = pd.read_csv(OVERRIDES_PATH)

        except Exception as ex:

            logger.warning("Failed to load sector overrides: %s", ex)
            return {}

        if df.empty or "Symbol" not in df.columns or "Sector" not in df.columns:
            return {}

        return dict(zip(df["Symbol"], df["Sector"]))

    # ------------------------------------------------------------------ #

    def _load_cache(self) -> Dict[str, Dict[str, Any]]:

        if not SECTOR_MAP_PATH.exists():
            return {}

        try:

            with open(SECTOR_MAP_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)

        except Exception as ex:

            logger.warning("Failed to load sector map cache: %s", ex)
            return {}

    # ------------------------------------------------------------------ #

    def _save_cache(self) -> None:

        try:

            SECTOR_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)

            with open(SECTOR_MAP_PATH, "w", encoding="utf-8") as fh:
                json.dump(self._cache, fh, indent=2)

        except Exception as ex:

            raise SectorMappingError(str(ex)) from ex

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

    def get_sector(self, symbol: str) -> str:
        """
        Resolves the sector for a ticker.
        """

        return self._resolve(symbol)["sector"]

    # ------------------------------------------------------------------ #

    def get_industry(self, symbol: str) -> str:
        """
        Resolves the industry for a ticker.
        """

        return self._resolve(symbol)["industry"]

    # ------------------------------------------------------------------ #

    def _resolve(self, symbol: str) -> Dict[str, str]:

        # 1. Manual overrides always win — Yahoo is frequently wrong for small caps
        if symbol in self._overrides:
            return {
                "sector": self._overrides[symbol],
                "industry": UNKNOWN_INDUSTRY,
            }

        # 2. Fresh cache entry
        cached = self._cache.get(symbol)

        if cached and not self._is_stale(cached):
            return {
                "sector": cached.get("sector", UNKNOWN_SECTOR),
                "industry": cached.get("industry", UNKNOWN_INDUSTRY),
            }

        # 3. Fall back to Yahoo, refreshing the cache entry
        try:

            info = market_provider.get_company_info(symbol)

        except Exception as ex:

            logger.warning("Sector lookup failed for %s: %s", symbol, ex)

            # Serve a stale cache entry rather than nothing, if one exists
            if cached:
                return {
                    "sector": cached.get("sector", UNKNOWN_SECTOR),
                    "industry": cached.get("industry", UNKNOWN_INDUSTRY),
                }

            return {"sector": UNKNOWN_SECTOR, "industry": UNKNOWN_INDUSTRY}

        resolved = {
            "sector": info.get("sector", UNKNOWN_SECTOR),
            "industry": info.get("industry", UNKNOWN_INDUSTRY),
            "fetched_at": datetime.now().isoformat(),
        }

        self._cache[symbol] = resolved

        self._save_cache()

        return {"sector": resolved["sector"], "industry": resolved["industry"]}


sector_map = SectorMap()
