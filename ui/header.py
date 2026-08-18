"""
===============================================================================
Falcon AI Swing Trading Platform
Module : header.py
===============================================================================
"""

from __future__ import annotations

from datetime import datetime, time

import pandas as pd
import pytz
import streamlit as st

from config import NIFTY50, NIFTY_MIDCAP_150, NIFTY_SMALLCAP_250

from common.logger import get_logger
from market_data.holiday_calendar import get_nse_holidays
from market_data.providers.yahoo_provider import market_provider
from scoring.benchmark import get_benchmark_history
from scoring.market_regime import get_market_trend_state, count_distribution_days
from decision_engine.leadership_decision_engine import get_market_regime_verdict

logger = get_logger(__name__)

# get_market_regime_verdict()'s three outputs mapped to a "+"/"-" prefix
# purely so st.metric()'s own delta_color (red for anything starting with
# "-") renders them correctly -- CAUTION has no natural sign, left
# unprefixed (renders as a neutral/positive delta).
_REGIME_VERDICT_PREFIX = {"FAVORABLE": "+", "UNFAVORABLE": "-"}

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


@st.cache_data(ttl=90)  # same freshness cadence as get_index_quotes()
def get_market_regime_snapshot() -> dict | None:
    """
    Real NIFTY trend regime state (scoring.market_regime.get_market_trend_state())
    plus the FAVORABLE/CAUTION/UNFAVORABLE verdict
    (decision_engine.leadership_decision_engine.get_market_regime_verdict())
    -- the same regime signal decision_engine.live_scorer scores every
    live candidate against, evaluated at "now" instead of a historical
    replay date. Returns None on any fetch failure (no network,
    insufficient benchmark history) -- render() shows the same "data
    unavailable" placeholder get_index_quotes() already uses for a failed
    quote, not a crash.
    """
    try:
        benchmark_history = get_benchmark_history()

        if benchmark_history is None or benchmark_history.empty or len(benchmark_history) < 2:
            return None

        trend_state = get_market_trend_state(benchmark_history)
        distribution_days = count_distribution_days(benchmark_history)

        if distribution_days is None:
            return None

        return {
            "trend_state": trend_state,
            "verdict": get_market_regime_verdict(trend_state, distribution_days),
            "distribution_days": distribution_days,
        }

    except Exception as ex:
        logger.warning("Market regime snapshot failed: %s", ex)
        return None


def format_last_scan_label(last_scan_completed_at: datetime | None) -> str:
    """Pure formatting logic, separated from render()'s widget calls so
    it's directly unit-testable without a Streamlit test harness (this
    module's existing convention -- only pure data/formatting functions
    get tested here, not render()'s own widget-drawing). Honest "never"
    state before the first scan, not a fabricated placeholder timestamp."""
    if last_scan_completed_at is None:
        return "Last scan: never"
    return f"Last scan: {last_scan_completed_at.strftime('%d %b, %H:%M')} IST"


def format_tickers_screened_label(last_scan_ticker_count: int | None) -> str | None:
    """None (not "0 tickers...") before the first scan has ever run --
    distinguishes "never scanned" from "scanned, found nothing" (both are
    real, honest states, just different ones)."""
    if last_scan_ticker_count is None:
        return None
    return f"{last_scan_ticker_count} tickers screened from Leadership query"


# Falcon's four real decision_engine categories, in display order.
CATEGORY_BREAKDOWN_ORDER = ["EXECUTE", "ALERT_WATCHLIST", "MONITOR", "AVOID"]

_CATEGORY_DISPLAY_LABEL = {
    "EXECUTE": "EXECUTE",
    "ALERT_WATCHLIST": "WATCHLIST",
    "MONITOR": "MONITOR",
    "AVOID": "AVOID",
}


def compute_category_breakdown(records_df: pd.DataFrame) -> dict[str, int]:
    """
    Counts every candidate's real decision_engine category across the
    FULL scanned universe -- same "always compute from the full universe,
    independent of candidate-tier counts" treatment already applied to the
    sector rotation panel (build_sector_view()), not gated on whether any
    candidate actually reached EXECUTE/WATCHLIST. records_df here is the
    same scan_result.records_df already stored in
    st.session_state.screener_records, post score_live_candidates() (so
    every row has a "category" column) -- an empty df or a
    pre-categorization df (missing the column) both count as all-zero
    rather than raising, since "0 of everything" is exactly what a scan
    that found nothing (or hasn't scored yet) should report.
    """
    if records_df.empty or "category" not in records_df.columns:
        return {c: 0 for c in CATEGORY_BREAKDOWN_ORDER}
    counts = records_df["category"].value_counts()
    return {c: int(counts.get(c, 0)) for c in CATEGORY_BREAKDOWN_ORDER}


def format_category_breakdown_label(
    category_counts: dict[str, int] | None,
    last_scan_ticker_count: int | None,
) -> str | None:
    """None before the first scan has ever run (mirrors
    format_tickers_screened_label()'s "never" vs "scanned, found nothing"
    distinction). Once a scan has completed, always renders the full
    EXECUTE/WATCHLIST/MONITOR/AVOID funnel even when EXECUTE and WATCHLIST
    are both 0 -- same "always visible regardless of candidate tier" fix
    already applied to the sector rotation panel, so this line doesn't
    silently disappear on exactly the quiet-market days it matters most."""
    if last_scan_ticker_count is None or category_counts is None:
        return None
    parts = " · ".join(
        f"{category_counts.get(cat, 0)} {_CATEGORY_DISPLAY_LABEL[cat]}"
        for cat in CATEGORY_BREAKDOWN_ORDER
    )
    return f"{last_scan_ticker_count} screened → {parts}"


def get_market_status(now: datetime | None = None) -> str:
    """
    Returns NSE market status from trading hours (9:15-15:30 IST, Mon-Fri)
    and the NSE equity holiday calendar (Diwali, Republic Day, etc.).
    """

    if now is None:
        now = datetime.now(IST)

    is_weekday = now.weekday() < 5
    is_trading_hours = MARKET_OPEN_TIME <= now.time() <= MARKET_CLOSE_TIME
    is_holiday = now.date() in get_nse_holidays()

    return "🟢 OPEN" if (is_weekday and is_trading_hours and not is_holiday) else "🔴 CLOSED"


def render(
    last_scan_ticker_count: int | None = None,
    last_scan_completed_at: datetime | None = None,
    last_scan_category_breakdown: dict[str, int] | None = None,
) -> bool:
    """
    Render Falcon dashboard header: greeting, market status/time, and the
    New Scan trigger.

    Dashboard rebuild note: this function previously also drew a market-
    snapshot row (indices + regime via st.metric()) below the divider --
    that content now lives in ui/dashboard.py's own market pulse strip
    (the mockup-derived embedded component), so drawing it here too would
    duplicate it. get_index_quotes()/get_market_regime_snapshot() below
    are unchanged and still the real, tested data sources ui/dashboard.py
    itself calls -- only the second, redundant Streamlit-native rendering
    of that same data was removed.

    last_scan_ticker_count / last_scan_completed_at / last_scan_category_breakdown :
    read from st.session_state by the caller (app.py), not read directly
    here -- matches this app's existing convention of passing session_state
    data into render functions explicitly (see dashboard.render(records_df))
    rather than each render function reaching into session_state itself.
    All three persist in session_state until the NEXT scan actually
    completes (app.py only updates them inside the scan-trigger block),
    not reset on every unrelated rerun/interaction.

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

        st.caption(format_last_scan_label(last_scan_completed_at))

        tickers_screened_label = format_tickers_screened_label(last_scan_ticker_count)
        if tickers_screened_label is not None:
            st.caption(tickers_screened_label)

        category_breakdown_label = format_category_breakdown_label(
            last_scan_category_breakdown, last_scan_ticker_count,
        )
        if category_breakdown_label is not None:
            st.caption(category_breakdown_label)

        st.button(
            "Market Overview",
            use_container_width=True,
        )

    st.divider()

    return new_scan