"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================
Module      : market_hours.py
Package     : Market Data

Purpose
-------
Backend-side "is NSE equity trading open right now" check -- weekday +
trading hours (9:15-15:30 IST) + the real NSE holiday calendar
(market_data.holiday_calendar.get_nse_holidays()).

ui/header.py's get_market_status() already computes this same thing
inline for the dashboard's "Market Closed" badge, but that function lives
in the Streamlit UI layer. services/scan_pipeline_service.py is
deliberately kept Streamlit-free (see that module's own docstring) so it
stays directly testable without a Streamlit test harness -- importing
from ui/ there would break that boundary. This module exists so a
same-day-only backend feature (technical_analysis/vwap_reclaim.py's live
wiring) can gate on real market hours without that import. Deliberately
NOT a refactor of ui/header.py's own inline check -- that function's
existing tests patch its own module-level get_nse_holidays reference
directly, and duplicating this ~6-line check here is cheaper and safer
than restructuring an already-tested, unrelated module for it.
===============================================================================
"""
from __future__ import annotations

from datetime import datetime, time

import pytz

from market_data.holiday_calendar import get_nse_holidays

IST = pytz.timezone("Asia/Kolkata")

MARKET_OPEN_TIME = time(9, 15)
MARKET_CLOSE_TIME = time(15, 30)


def is_live_market_hours(now: datetime | None = None) -> bool:
    """
    True during real NSE trading hours: a weekday, 9:15-15:30 IST, not a
    published equity holiday. `now` defaults to the real current time
    (IST); a naive `now` is treated as already being in IST, an
    aware `now` is converted to IST first.
    """
    if now is None:
        now = datetime.now(IST)
    elif now.tzinfo is not None:
        now = now.astimezone(IST)

    is_weekday = now.weekday() < 5
    is_trading_hours = MARKET_OPEN_TIME <= now.time() <= MARKET_CLOSE_TIME
    is_holiday = now.date() in get_nse_holidays()

    return is_weekday and is_trading_hours and not is_holiday
