"""
===============================================================================
Falcon AI Swing Trading Platform
Module : header.py
===============================================================================
"""

from __future__ import annotations

from datetime import datetime, time

import pytz
import streamlit as st

from config import NIFTY50, NIFTY_MIDCAP_150, NIFTY_SMALLCAP_250

from common.logger import get_logger
from market_data.providers.yahoo_provider import market_provider

logger = get_logger(__name__)

IST = pytz.timezone("Asia/Kolkata")

MARKET_OPEN_TIME = time(9, 15)
MARKET_CLOSE_TIME = time(15, 30)

INDEX_SYMBOLS = [
    ("NIFTY 50", NIFTY50),
    ("NIFTY MIDCAP 150", NIFTY_MIDCAP_150),
    ("NIFTY SMALLCAP 250", NIFTY_SMALLCAP_250),
]


@st.cache_data(ttl=90)  # fresh enough to feel live, not hammering Yahoo on every rerun
def get_index_quotes() -> dict[str, dict | None]:
    """
    Returns a quote dict per index label, or None where the fetch failed.
    """

    quotes: dict[str, dict | None] = {}

    for label, symbol in INDEX_SYMBOLS:

        try:

            quotes[label] = market_provider.get_quote(symbol)

        except Exception as ex:

            logger.warning("Quote fetch failed for %s: %s", symbol, ex)
            quotes[label] = None

    return quotes


def get_market_status(now: datetime | None = None) -> str:
    """
    Returns NSE market status from trading hours (9:15-15:30 IST, Mon-Fri).

    Known limitation: does not account for NSE holidays (Diwali, Republic
    Day, etc.) — will incorrectly show OPEN on a weekday holiday.
    """

    if now is None:
        now = datetime.now(IST)

    is_weekday = now.weekday() < 5
    is_trading_hours = MARKET_OPEN_TIME <= now.time() <= MARKET_CLOSE_TIME

    return "🟢 OPEN" if (is_weekday and is_trading_hours) else "🔴 CLOSED"


def render() -> bool:
    """
    Render Falcon dashboard header.

    Returns
    -------
    bool
        True when New Scan is clicked.
    """

    left, right = st.columns([3.8, 2.2])

    # ------------------------------------------------------------------
    # Left
    # ------------------------------------------------------------------

    with left:

        hour = datetime.now().hour

        if hour < 12:
            greeting = "Good Morning"
        elif hour < 17:
            greeting = "Good Afternoon"
        else:
            greeting = "Good Evening"

        st.markdown(
            f"""
### {greeting}, Trader 👋

Scan markets. Find leaders. Ride the trend.
"""
        )

    # ------------------------------------------------------------------
    # Right
    # ------------------------------------------------------------------

    with right:

        c1, c2 = st.columns([1, 1])

        with c1:

            st.metric(
                "Market",
                get_market_status(),
            )

        with c2:

            st.metric(
                "Time",
                datetime.now().strftime("%H:%M"),
            )

        new_scan = st.button(
            "➕ New Scan",
            use_container_width=True,
            type="primary",
        )

        st.button(
            "Market Overview",
            use_container_width=True,
        )

    st.divider()

    # ------------------------------------------------------------------
    # Market Snapshot
    # ------------------------------------------------------------------

    quotes = get_index_quotes()

    for column, (label, _symbol) in zip(st.columns(3), INDEX_SYMBOLS):

        with column:

            q = quotes.get(label)

            if q:
                st.metric(
                    label,
                    f"{q['last_price']:,.2f}",
                    f"{q['change_pct']:+.2f}%",
                )
            else:
                st.metric(label, "—", "data unavailable")

    st.divider()

    return new_scan