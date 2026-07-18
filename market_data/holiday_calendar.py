"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : holiday_calendar.py
Package     : Market Data

Purpose
-------
Caches the NSE equity trading-holiday calendar so ui/header.py's
get_market_status() can detect holidays, not just weekday + trading-hours.
Cache-then-check-staleness, mirroring scoring/sector_map.py's pattern.

nselib.trading_holiday_calendar()'s return shape was confirmed via a live
call (no docstring exists upstream): a DataFrame with a 'Product' column
(market segment -- Equities, Equity Derivatives, Currency Derivatives,
Corporate Bonds, etc., each with its own calendar) and a 'tradingDate'
column formatted like "26-Jan-2026". "Equities" is the segment nselib's own
source maps from NSE's "CM" (Capital Market) product code -- the one that
governs regular stock trading holidays.
===============================================================================
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from nselib import trading_holiday_calendar

from config import DATA_FOLDER

from common.logger import get_logger

logger = get_logger(__name__)

CACHE_PATH = Path(DATA_FOLDER) / "nse_holidays_cache.json"

# Holiday calendars are published well in advance -- no need to refetch often.
REFRESH_INTERVAL_DAYS = 30

EQUITY_PRODUCT_NAME = "Equities"

# nselib's trading_holiday_calendar() returns tradingDate as e.g. "26-Jan-2026"
DATE_FORMAT = "%d-%b-%Y"


def _load_cache_if_fresh() -> set[date] | None:

    if not CACHE_PATH.exists():
        return None

    try:

        with open(CACHE_PATH, "r", encoding="utf-8") as fh:
            cached = json.load(fh)

        fetched_at = datetime.fromisoformat(cached["fetched_at"])

        if datetime.now() - fetched_at > timedelta(days=REFRESH_INTERVAL_DAYS):
            return None

        return {date.fromisoformat(d) for d in cached["holidays"]}

    except Exception as ex:

        logger.warning("Failed to load NSE holiday cache: %s", ex)
        return None


def _save_cache(holidays: set[date]) -> None:

    try:

        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

        with open(CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "fetched_at": datetime.now().isoformat(),
                    "holidays": sorted(d.isoformat() for d in holidays),
                },
                fh,
                indent=2,
            )

    except Exception as ex:

        logger.warning("Failed to save NSE holiday cache: %s", ex)


def _parse_holiday_response(raw: pd.DataFrame) -> set[date]:
    """
    Filters to the "Equities" segment and parses tradingDate. Any shape
    mismatch (missing column, unexpected format) raises -- get_nse_holidays()
    catches it and falls back to an empty set rather than crashing.
    """

    equity_rows = raw[raw["Product"] == EQUITY_PRODUCT_NAME]

    parsed_dates = pd.to_datetime(
        equity_rows["tradingDate"],
        format=DATE_FORMAT,
        errors="coerce",
    )

    return {ts.date() for ts in parsed_dates.dropna()}


def get_nse_holidays() -> set[date]:
    """
    Returns the set of NSE equity trading holidays for the current year.

    Falls back to an empty set (holidays simply won't be detected,
    degrading to the existing weekday+hours-only check) if the fetch or
    parse fails -- this must never crash market status.
    """

    cached = _load_cache_if_fresh()

    if cached is not None:
        return cached

    try:

        raw = trading_holiday_calendar()
        holidays = _parse_holiday_response(raw)

        if not holidays:
            logger.warning(
                "NSE holiday calendar parsed to zero holidays -- "
                "confirm the '%s' Product filter still matches nselib's "
                "current response shape.",
                EQUITY_PRODUCT_NAME,
            )

        _save_cache(holidays)
        return holidays

    except Exception as ex:

        logger.warning(
            "NSE holiday calendar fetch failed, falling back to "
            "weekday-only check: %s", ex,
        )
        return set()
