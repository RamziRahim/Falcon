"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : universe.py
Package     : Scoring

Purpose
-------
Defines the comparison universe used for percentile-based ratings (RS Rating).

Phase 1
-------
Universe = every ticker currently present in the local pipeline (data/patterns/
falling back to data/raw/, i.e. whatever's already been downloaded through the
candidate generation + market data pipeline). Ratings are relative to the
tracked universe, not the full market.

Phase 2 (later, optional)
--------------------------
Expand to full NIFTY 500 constituents for a market-wide percentile rank. Needs
a constituents list and price history for ~500 tickers — deferred until
Phase 1 is validated.

===============================================================================
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from config import PATTERN_DATA_FOLDER, CACHE_FILE_EXTENSION

from common.logger import get_logger
from market_data.cache_manager import cache_manager
from scoring.exceptions import UniverseError

logger = get_logger(__name__)


def get_universe() -> List[str]:
    """
    Returns the current comparison universe (Phase 1: local tracked tickers).

    Swapping to Phase 2 (full market universe) only requires changing this
    function's body — calling code never needs to change.

    Returns
    -------
    List[str]
        Sorted, de-duplicated list of tracked ticker symbols.
    """

    try:

        pattern_dir = Path(PATTERN_DATA_FOLDER)

        pattern_symbols = {
            f.stem
            for f in pattern_dir.glob(f"*{CACHE_FILE_EXTENSION}")
        } if pattern_dir.exists() else set()

        raw_symbols = set(cache_manager.list_symbols())

        universe = sorted(pattern_symbols | raw_symbols)

        logger.info(
            "Resolved comparison universe: %d tickers.",
            len(universe),
        )

        return universe

    except Exception as ex:

        raise UniverseError(str(ex)) from ex
