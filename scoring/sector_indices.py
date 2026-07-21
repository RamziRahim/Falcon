"""
===============================================================================
Falcon AI Swing Trading Platform — Real Sector Index Trend
===============================================================================
Script      : sector_indices.py
Package     : Scoring

Replaces the small-sample Pct_Uptrend proxy (breadth within Falcon's own
~100-167 tracked tickers, not a sector's real constituents) with a genuine
sector-index trend read: NIFTY IT, NIFTY AUTO, NIFTY PHARMA, etc. run
through the same market_structure_engine already used per-stock and for
NIFTY 50's own regime signal (scoring.market_regime.get_market_trend_state()).
Same reuse pattern, different input series.

-------------------------------------------------------------------------
Confirmed live, not guessed
-------------------------------------------------------------------------
Both sides of SECTOR_INDEX_MAP verified directly, not assumed:
- Yahoo sector labels (the LHS, what sector_map.py actually returns) --
  confirmed against 10 real NSE tickers (TCS, HDFCBANK, SUNPHARMA, MARUTI,
  HINDUNILVR, TATASTEEL, LT, RELIANCE, DLF, BHARTIARTL) via yf.Ticker().info,
  all matching exactly: Technology, Financial Services, Healthcare,
  Consumer Cyclical, Consumer Defensive, Basic Materials, Industrials,
  Energy, Real Estate, Communication Services.
- NSE index name strings (the RHS, the `index` argument to
  capital_market.index_data()) -- confirmed all 10 resolve with real data.
  Note: the query string and the RETURNED INDEX_NAME column value can
  differ (NSE's own internal abbreviation) -- e.g. querying
  "NIFTY FINANCIAL SERVICES" returns rows labeled "NIFTY FIN SERVICE",
  and "NIFTY INDIA MANUFACTURING" returns "NIFTY INDIA MFG". This doesn't
  affect querying (the input string is what matters), just don't expect
  the two to match if something downstream ever reads INDEX_NAME back.

capital_market.index_data() hits a live www.nseindia.com API endpoint
(not a static archive CSV like the equity-list functions) -- confirmed
working after one transient DNS failure that resolved on retry.

CONFIRMED REAL LIMITATION: index_data() does its own internal chunking
for ranges over 365 days, but a request for 2024-01-01 to 2026-07-20
(a live test, ~2.5 years) silently returned data only through
2026-04-15 -- about 3 months short of what was asked, with no exception
raised. Callers must check the actual returned Date range rather than
assume the request was fully honored; get_sector_index_trend() below
already degrades to CHOPPY on insufficient truncated history for exactly
this reason, but anything computing recency (e.g. "as of today") off
this data should verify coverage first.
===============================================================================
"""
from __future__ import annotations

import pandas as pd
from nselib import capital_market

from common.logger import get_logger

logger = get_logger(__name__)

# Yahoo sector label (sector_map.py's real output) -> NSE index name (the
# `index` argument capital_market.index_data() accepts). Confirmed live,
# see module docstring.
SECTOR_INDEX_MAP = {
    "Technology": "NIFTY IT",
    "Financial Services": "NIFTY FINANCIAL SERVICES",
    "Healthcare": "NIFTY PHARMA",
    "Consumer Cyclical": "NIFTY AUTO",
    "Consumer Defensive": "NIFTY FMCG",
    "Basic Materials": "NIFTY METAL",
    "Industrials": "NIFTY INDIA MANUFACTURING",
    "Energy": "NIFTY ENERGY",
    "Real Estate": "NIFTY REALTY",
    "Communication Services": "NIFTY MEDIA",
    # Any other sector (including "Unknown") has no real index mapping --
    # get_sector_index_history() returns None gracefully for these, and
    # get_sector_index_trend() falls back to CHOPPY (honestly-unknown),
    # not a crash or a fabricated verdict.
}

MIN_TREND_STATE_ROWS = 20  # same floor used throughout the pipeline


def get_sector_index_history(sector: str, from_date: str, to_date: str) -> pd.DataFrame | None:
    """
    Fetches a sector's real NSE index OHLCV history via
    capital_market.index_data(). Returns None gracefully (not a crash) if
    the sector isn't in SECTOR_INDEX_MAP or the fetch fails -- callers
    should treat None as "no real sector index data available," same
    convention as scoring.market_regime.get_vix_history().

    Parameters
    ----------
    sector : Falcon's Sector label (scoring.sector_map.sector_map.get_sector()'s
        output), not the NSE index name directly.
    from_date, to_date : 'dd-mm-YYYY', nselib's own date format.
    """
    index_name = SECTOR_INDEX_MAP.get(sector)

    if index_name is None:
        return None

    try:

        raw = capital_market.index_data(index=index_name, from_date=from_date, to_date=to_date)

        if raw is None or raw.empty:
            return None

        result = pd.DataFrame({
            "Date": pd.to_datetime(raw["TIMESTAMP"], format="%d-%b-%Y"),
            "Open": raw["OPEN_INDEX_VAL"].astype(float),
            "High": raw["HIGH_INDEX_VAL"].astype(float),
            "Low": raw["LOW_INDEX_VAL"].astype(float),
            "Close": raw["CLOSE_INDEX_VAL"].astype(float),
            "Volume": raw["TRADED_QTY"].astype(float),
        }).sort_values("Date").reset_index(drop=True)

        return result

    except Exception as ex:

        logger.warning("Sector index fetch failed for %s (%s): %s", sector, index_name, ex)
        return None


def get_sector_index_trend(sector_name: str, as_of_date, history_cache: dict) -> str:
    """
    Runs market_structure_engine against the sector's real index history --
    same reuse pattern as scoring.market_regime.get_market_trend_state(),
    just a different input series. Returns UPTREND / DOWNTREND / CHOPPY
    for the sector itself, not a small-sample proxy.

    Parameters
    ----------
    sector_name : Falcon's Sector label.
    as_of_date : truncation point -- history_cache's entry for this
        sector is truncated to <= as_of_date before running detection,
        same point-in-time discipline as everywhere else in backtesting.
    history_cache : dict[Sector label -> full sector index history],
        pre-fetched by the caller (e.g. once per backtest run via
        get_sector_index_history(), mirroring how vix_history/
        benchmark_history are fetched once and passed through) -- this
        function does no fetching itself.

    Falls back to CHOPPY (honestly-unknown, matching
    market_structure_engine's own default) when the sector isn't in
    history_cache or there's insufficient truncated history -- not a
    crash, not a fabricated UPTREND/DOWNTREND.
    """
    from technical_analysis.pattern_engine import macro_swing_detector
    from technical_analysis.pattern_system.market_structure import market_structure_engine

    history = history_cache.get(sector_name)

    if history is None:
        return "CHOPPY"

    truncated = history[history["Date"] <= as_of_date]

    if len(truncated) < MIN_TREND_STATE_ROWS:
        return "CHOPPY"

    macro_pivots = macro_swing_detector.detect_swings(truncated)
    return market_structure_engine.analyze_structure(truncated, macro_pivots)["trend_state"]
