"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : indicator_loader.py
Package     : Technical Analysis

Purpose
-------
Provides business-level access to Falcon's cached market data for the
Technical Analysis Engine.

Responsibilities
----------------
• Load market data for one symbol
• Load market data for multiple symbols
• Load all available market data

Dependencies
------------
• market_data_loader

===============================================================================
"""

from __future__ import annotations

from typing import Dict

import pandas as pd

from common.logger import get_logger
from market_data.data_loader import market_data_loader

logger = get_logger(__name__)


class IndicatorLoader:
    """
    Loads market data for indicator calculation.
    """

    def load(
        self,
        symbol: str,
    ) -> pd.DataFrame:

        logger.info(
            "Loading market data for %s",
            symbol,
        )

        return market_data_loader.load(symbol)

    # ------------------------------------------------------------------ #

    def load_many(
        self,
        symbols: list[str],
    ) -> Dict[str, pd.DataFrame]:

        logger.info(
            "Loading market data for %d symbols...",
            len(symbols),
        )

        return market_data_loader.load_many(symbols)

    # ------------------------------------------------------------------ #

    def load_all(
        self,
    ) -> Dict[str, pd.DataFrame]:

        logger.info(
            "Loading market data for all cached symbols."
        )

        return market_data_loader.load_all()


indicator_loader = IndicatorLoader()
