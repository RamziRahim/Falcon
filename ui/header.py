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
    regime = get_market_regime_snapshot()

    snapshot_columns = st.columns(4)

    for column, (label, _symbol) in zip(snapshot_columns[:3], INDEX_SYMBOLS):

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

    with snapshot_columns[3]:

        if regime:
            verdict_prefix = _REGIME_VERDICT_PREFIX.get(regime["verdict"], "")
            st.metric(
                "Market Regime",
                regime["trend_state"],
                f"{verdict_prefix}{regime['verdict']}",
            )
        else:
            st.metric("Market Regime", "—", "data unavailable")

    st.divider()

    return new_scan