"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : deal_activity.py
Package     : Fundamental Analysis

Purpose
-------
Checks NSE bulk/block deal data for recent large BUY-side trades on a
ticker -- a confirming signal, not a primary one.

Columns and function signatures CONFIRMED via nselib/constants.py and a
live call to capital_market.bulk_deal_data()/block_deals_data(): both
return Date, Symbol, SecurityName, ClientName, Buy/Sell, QuantityTraded,
TradePrice/Wght.Avg.Price, Remarks. QuantityTraded/TradePrice are Indian-
comma-formatted strings (e.g. "1,71,14,604") needing the same cleaning
already used elsewhere (nse_provider.py). Buy/Sell values are confirmed
(live call) to be the plain uppercase strings "BUY"/"SELL" -- not "B"/"S"
or mixed case.
===============================================================================
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
from nselib import capital_market

from common.logger import get_logger

logger = get_logger(__name__)

DATE_FORMAT = "%d-%m-%Y"


def _clean_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", ""), errors="coerce")


def _normalize_symbol(ticker: str) -> str:
    symbol = ticker.upper()
    if symbol.endswith(".NS"):
        symbol = symbol[:-3]
    return symbol


def _fetch_deals(fetch_fn, symbol: str, from_date: str, to_date: str) -> pd.DataFrame:
    try:

        raw = fetch_fn(from_date=from_date, to_date=to_date)

        if raw is None or raw.empty:
            return pd.DataFrame()

        matches = raw[raw["Symbol"].str.upper() == symbol]

        if matches.empty:
            return matches

        matches = matches.copy()
        matches["QuantityTraded"] = _clean_numeric(matches["QuantityTraded"])
        matches["Date"] = pd.to_datetime(matches["Date"], format="%d-%b-%Y", errors="coerce")

        return matches

    except Exception as ex:

        logger.warning("Deal-data fetch failed for %s: %s", symbol, ex)
        return pd.DataFrame()


def get_recent_institutional_activity(ticker: str, lookback_days: int = 30) -> dict:
    """
    Checks both bulk_deal_data and block_deals_data for `ticker` within the
    last `lookback_days` days. Returns whether any BUY-side large trade
    occurred, and its most recent date/quantity if so.

    Returns
    -------
    dict with keys: has_buy_activity (bool), latest_buy_date (str | None),
    latest_buy_quantity (float | None), source (str | None: "bulk"/"block").
    Never raises -- a fetch failure or no-activity result both come back
    as has_buy_activity=False, not an exception.
    """

    symbol = _normalize_symbol(ticker)

    to_date = dt.date.today()
    from_date = to_date - dt.timedelta(days=lookback_days)

    str_from = from_date.strftime(DATE_FORMAT)
    str_to = to_date.strftime(DATE_FORMAT)

    result = {
        "has_buy_activity": False,
        "latest_buy_date": None,
        "latest_buy_quantity": None,
        "source": None,
    }

    bulk = _fetch_deals(capital_market.bulk_deal_data, symbol, str_from, str_to)
    block = _fetch_deals(capital_market.block_deals_data, symbol, str_from, str_to)

    candidates = []

    if not bulk.empty:
        buys = bulk[bulk["Buy/Sell"].str.upper() == "BUY"]
        if not buys.empty:
            candidates.append(("bulk", buys))

    if not block.empty:
        buys = block[block["Buy/Sell"].str.upper() == "BUY"]
        if not buys.empty:
            candidates.append(("block", buys))

    if not candidates:
        return result

    # Most recent BUY across both sources
    best_source, best_row = None, None
    for source, buys in candidates:
        row = buys.sort_values("Date", ascending=False).iloc[0]
        if best_row is None or row["Date"] > best_row["Date"]:
            best_source, best_row = source, row

    result["has_buy_activity"] = True
    result["latest_buy_date"] = best_row["Date"].strftime("%Y-%m-%d") if pd.notna(best_row["Date"]) else None
    result["latest_buy_quantity"] = float(best_row["QuantityTraded"]) if pd.notna(best_row["QuantityTraded"]) else None
    result["source"] = best_source

    return result
