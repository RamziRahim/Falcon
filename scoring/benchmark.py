"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : benchmark.py
Package     : Scoring

Purpose
-------
Fetches and caches NIFTY 50 index history (^NSEI) for use as the benchmark in
relative-strength comparisons and (later) sector rotation (RRG).

Uses YahooProvider.get_history() directly (not the provider factory) because
^NSEI is a Yahoo-specific index symbol format, independent of the configured
per-stock market data provider. Follows the same incremental cache-then-fetch
pattern as market_data/downloader.py, just pinned to a single fixed symbol.

===============================================================================
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from config import NIFTY50, DEFAULT_HISTORY_YEARS

from common.logger import get_logger
from market_data.cache_manager import cache_manager
from market_data.providers.yahoo_provider import market_provider
from scoring.exceptions import BenchmarkError

logger = get_logger(__name__)

BENCHMARK_SYMBOL = NIFTY50


def _refresh_cache() -> None:
    """
    Downloads any benchmark candles missing since the last cached date.
    """

    today = date.today()

    start_date = today - timedelta(days=365 * DEFAULT_HISTORY_YEARS)

    if cache_manager.exists(BENCHMARK_SYMBOL):

        last_cached_date = cache_manager.last_date(BENCHMARK_SYMBOL)

        if last_cached_date is not None:
            start_date = last_cached_date.date() + timedelta(days=1)

    if start_date >= today:
        return

    df = market_provider.get_history(
        symbol=BENCHMARK_SYMBOL,
        start_date=start_date,
        end_date=today,
    )

    if df.empty:
        return

    cache_manager.update(BENCHMARK_SYMBOL, df)


def get_benchmark_history(force_refresh: bool = False) -> pd.DataFrame:
    """
    Returns cached NIFTY 50 index history, refreshing missing days first.

    Parameters
    ----------
    force_refresh : bool
        When True, always attempts a refresh even if a cache entry exists.

    Returns
    -------
    pd.DataFrame
    """

    try:

        if force_refresh or not cache_manager.exists(BENCHMARK_SYMBOL):

            _refresh_cache()

        else:

            try:

                _refresh_cache()

            except Exception as ex:

                logger.warning(
                    "Benchmark refresh failed, serving cached data: %s",
                    ex,
                )

        if not cache_manager.exists(BENCHMARK_SYMBOL):

            raise BenchmarkError(
                f"No benchmark history available for {BENCHMARK_SYMBOL}."
            )

        return cache_manager.load(BENCHMARK_SYMBOL)

    except BenchmarkError:

        raise

    except Exception as ex:

        raise BenchmarkError(str(ex)) from ex
