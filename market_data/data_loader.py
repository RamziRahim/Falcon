"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : data_loader.py
Package     : Market Data

Purpose
-------
Provides business-level access to Falcon's cached market data.

Responsibilities
----------------
• Load market data for a symbol
• Load market data for multiple symbols
• Load all cached market data

Inputs
------
• Stock Symbol(s)

Outputs
-------
• Pandas DataFrame(s)

Dependencies
------------
• CacheManager

Future Enhancements
-------------------
• Load by sector
• Load by strategy
• Load by date range
• Load latest N candles

===============================================================================
"""

from __future__ import annotations

from typing import Dict, List

import pandas as pd

from common.logger import get_logger

from market_data.cache_manager import cache_manager

logger = get_logger(__name__)


class MarketDataLoader:
    """
    Loads market data from Falcon cache.
    """

    # ------------------------------------------------------------------ #

    def load(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Loads market data for a single symbol.

        Parameters
        ----------
        symbol : str

        Returns
        -------
        pandas.DataFrame
        """

        logger.info(
            "Loading market data: %s",
            symbol,
        )

        return cache_manager.load(symbol)

    # ------------------------------------------------------------------ #

    def load_many(
        self,
        symbols: List[str],
    ) -> Dict[str, pd.DataFrame]:
        """
        Loads market data for multiple symbols.

        Parameters
        ----------
        symbols : List[str]

        Returns
        -------
        Dict[str, pandas.DataFrame]
        """

        datasets: Dict[str, pd.DataFrame] = {}

        for symbol in symbols:

            try:

                datasets[symbol] = self.load(symbol)

            except Exception as ex:

                logger.exception(
                    "Failed loading %s : %s",
                    symbol,
                    ex,
                )

        return datasets

    # ------------------------------------------------------------------ #

    def load_all(
        self,
    ) -> Dict[str, pd.DataFrame]:
        """
        Loads all cached market data.

        Returns
        -------
        Dict[str, pandas.DataFrame]
        """

        logger.info(
            "Loading all cached market data..."
        )

        symbols = cache_manager.list_symbols()

        return self.load_many(symbols)


market_data_loader = MarketDataLoader()