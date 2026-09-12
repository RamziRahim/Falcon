"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================
Module      : intraday_fetcher.py
Package     : Market Data

Purpose
-------
Fetches today's 1-minute intraday bars for a single symbol, for
technical_analysis/vwap_reclaim.py's live wiring only.

Deliberately calls yfinance directly rather than going through
market_data.providers.base_provider.BaseProvider's get_intraday() --
matches this codebase's existing, established pattern of single-purpose
fetch modules (fundamental_analysis/corporate_engine.py,
fundamental_analysis/metrics_engine.py, fundamental_analysis/
institutional_engine.py, scoring/sector_indices.py) calling yfinance
directly for data types the live scan's own configured provider
(NSEProvider, nselib-based, EOD-only -- confirmed live, 2026-09-05, that
nselib has no intraday endpoint at all) doesn't cover. Both providers'
own get_intraday() remain unimplemented stubs; this module doesn't touch
them, matching the existing precedent above rather than plumbing a new
call through the provider abstraction for one narrow use case.

Confirmed live before this module was written: fetching ~15 tickers (a
typical day's EXECUTE+WATCHLIST count) sequentially takes ~5 seconds
total via this exact call shape -- immaterial against a 28-58 minute
scan, and this is a separate Yahoo endpoint from the NSE/nselib daily-bar
path, so it adds no load to that provider's own request discipline.
===============================================================================
"""
from __future__ import annotations

import pandas as pd
import yfinance as yf

from common.logger import get_logger

logger = get_logger(__name__)

INTRADAY_INTERVAL = "1m"
INTRADAY_PERIOD = "1d"


def fetch_todays_intraday_bars(symbol: str) -> pd.DataFrame:
    """
    Returns today's (or, if fetched outside trading hours, the most
    recently completed session's) 1-minute bars for `symbol` as a
    DataFrame with columns Datetime/Open/High/Low/Close/Volume.

    Returns an empty DataFrame (never raises) on any fetch failure --
    technical_analysis.vwap_reclaim.compute_vwap_reclaim_status() already
    treats an empty/None input as its own "no_intraday_bars" fail-closed
    case, so callers don't need a second layer of error handling here.
    """
    try:
        df = yf.Ticker(symbol).history(period=INTRADAY_PERIOD, interval=INTRADAY_INTERVAL)
    except Exception as ex:
        logger.warning("Intraday fetch failed for %s: %s", symbol, ex)
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    # yfinance's intraday history() always names its DatetimeIndex
    # "Datetime" (confirmed live, 2026-09-05 -- distinct from
    # get_history()'s daily-bar "Date" index elsewhere in this codebase),
    # so reset_index() alone already produces the column name
    # compute_vwap_reclaim_status() expects.
    return df.reset_index()
