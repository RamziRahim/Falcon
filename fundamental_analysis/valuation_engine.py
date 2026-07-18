"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : valuation_engine.py
Package     : Fundamental Analysis

Purpose
-------
Market-wide P/E snapshot and per-ticker relative-valuation bucketing.

capital_market.pe_ratio(trade_date) fetches P/E for ALL NSE equities in one
call -- confirmed live to return a DataFrame with columns
['SYMBOL', 'SYMBOLP/E', 'ADJUSTEDP/E'] (no docstring/constants entry
existed beforehand). One fetch per day covers the whole market; filter to
the tracked universe afterward rather than calling per-ticker.

get_relative_valuation() expects pe_snapshot to already carry a 'Sector'
column for whatever subset of tickers the caller cares about (merged in
via scoring/sector_map.py at the call site) -- this module intentionally
does NOT call sector_map itself for all ~2000+ snapshot rows, since most
of those tickers are never in Falcon's tracked universe and sector_map's
own cache/fallback path can hit yfinance per ticker.
===============================================================================
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from nselib import capital_market

from config import DATA_FOLDER

from common.logger import get_logger

logger = get_logger(__name__)

PE_CACHE_DIR = Path(DATA_FOLDER) / "pe_snapshot_cache"

# capital_market.pe_ratio() expects "DD-MM-YYYY"
DATE_FORMAT = "%d-%m-%Y"

# How many calendar days back to retry when no trade_date is given --
# covers weekends and the occasional multi-day holiday stretch.
MAX_LOOKBACK_DAYS = 6

# Starting threshold, not backtested yet -- revisit once #16 (backtesting)
# has real data on whether relative valuation predicts anything here.
VALUATION_THRESHOLD = 0.20


def _cache_path_for(trade_date: str) -> Path:
    return PE_CACHE_DIR / f"{trade_date}.json"


def _load_cached_snapshot(trade_date: str) -> pd.DataFrame | None:

    cache_path = _cache_path_for(trade_date)

    if not cache_path.exists():
        return None

    try:

        with open(cache_path, "r", encoding="utf-8") as fh:
            records = json.load(fh)

        return pd.DataFrame(records)

    except Exception as ex:

        logger.warning("Failed to load PE snapshot cache for %s: %s", trade_date, ex)
        return None


def _save_snapshot_cache(trade_date: str, df: pd.DataFrame) -> None:

    try:

        PE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        with open(_cache_path_for(trade_date), "w", encoding="utf-8") as fh:
            json.dump(df.to_dict(orient="records"), fh)

    except Exception as ex:

        logger.warning("Failed to save PE snapshot cache for %s: %s", trade_date, ex)


def _clean_snapshot(raw: pd.DataFrame) -> pd.DataFrame:

    df = raw.rename(columns={
        "SYMBOL": "Symbol",
        "SYMBOLP/E": "PE",
        "ADJUSTEDP/E": "Adjusted_PE",
    }).copy()

    for col in ("PE", "Adjusted_PE"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def get_market_pe_snapshot(trade_date: str | None = None) -> pd.DataFrame:
    """
    Fetches P/E for all NSE equities as of trade_date (defaults to the
    most recent trading day, retrying backward through weekends/holidays).
    Cached per-date -- P/E snapshots don't change intraday or retroactively,
    so a cache hit for a given date is always valid, no staleness check
    needed.

    Returns an empty DataFrame (never raises) if no trading day in the
    lookback window has data available.
    """

    candidate_dates = (
        [trade_date] if trade_date is not None
        else [(date.today() - timedelta(days=i)).strftime(DATE_FORMAT) for i in range(MAX_LOOKBACK_DAYS)]
    )

    for candidate in candidate_dates:

        cached = _load_cached_snapshot(candidate)
        if cached is not None:
            return cached

        try:

            raw = capital_market.pe_ratio(candidate)

            if raw is None or raw.empty:
                continue

            df = _clean_snapshot(raw)
            _save_snapshot_cache(candidate, df)
            return df

        except Exception as ex:

            logger.warning("PE snapshot fetch failed for %s: %s", candidate, ex)
            continue

    logger.warning("No PE snapshot available in the last %d days.", MAX_LOOKBACK_DAYS)
    return pd.DataFrame(columns=["Symbol", "PE", "Adjusted_PE"])


def _normalize_symbol(ticker: str) -> str:
    symbol = ticker.upper()
    if symbol.endswith(".NS"):
        symbol = symbol[:-3]
    return symbol


def get_relative_valuation(ticker: str, sector: str, pe_snapshot: pd.DataFrame) -> dict:
    """
    Compares ticker's P/E against the average P/E of its sector peers
    within pe_snapshot (pe_snapshot must already carry a 'Sector' column
    for the relevant tickers -- see module docstring).

    Returns {'pe': float | None, 'sector_avg_pe': float | None,
    'relative': "CHEAP" | "FAIR" | "EXPENSIVE" | "UNKNOWN"}. 'UNKNOWN'
    covers every case where a confident comparison isn't possible (ticker
    missing from the snapshot, no PE reported, no sector peers) -- never
    a crash or a fabricated bucket.
    """

    result = {"pe": None, "sector_avg_pe": None, "relative": "UNKNOWN"}

    if pe_snapshot is None or pe_snapshot.empty or "Symbol" not in pe_snapshot.columns:
        return result

    symbol = _normalize_symbol(ticker)
    ticker_rows = pe_snapshot[pe_snapshot["Symbol"].astype(str).str.upper() == symbol]

    if ticker_rows.empty:
        return result

    pe = ticker_rows.iloc[0].get("PE")
    if pd.isna(pe):
        return result

    result["pe"] = float(pe)

    if not sector or "Sector" not in pe_snapshot.columns:
        return result

    # "Peers" excludes the ticker's own row -- comparing against others,
    # not a self-referential average that would dampen the signal for
    # small sectors.
    peers = pe_snapshot[
        (pe_snapshot["Sector"] == sector)
        & pe_snapshot["PE"].notna()
        & (pe_snapshot["Symbol"].astype(str).str.upper() != symbol)
    ]

    if peers.empty:
        return result

    sector_avg_pe = peers["PE"].mean()

    if pd.isna(sector_avg_pe) or sector_avg_pe == 0:
        return result

    result["sector_avg_pe"] = float(sector_avg_pe)

    relative_diff = (result["pe"] - sector_avg_pe) / sector_avg_pe

    if relative_diff > VALUATION_THRESHOLD:
        result["relative"] = "EXPENSIVE"
    elif relative_diff < -VALUATION_THRESHOLD:
        result["relative"] = "CHEAP"
    else:
        result["relative"] = "FAIR"

    return result
