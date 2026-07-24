"""
===============================================================================
Falcon AI Swing Trading Platform — Backtest Universe Builder
===============================================================================
Script      : universe_builder.py
Package     : Backtesting

Assembles ticker universes for backtesting.py runs. Kept as a real,
reusable, named function rather than a one-off script -- future backtest
runs at a different scope are a parameter here, not a rewrite.

Distinct from scoring/universe.py::get_universe(), which returns whatever's
ALREADY locally downloaded for live RS-rating purposes. This module is
about SELECTING which tickers a backtest run should target in the first
place (before any download has necessarily happened) -- a different
concern.

-------------------------------------------------------------------------
Confirmed live, not guessed
-------------------------------------------------------------------------
nselib.capital_market.nifty50_equity_list() and niftymidcap150_equity_list()
both return a DataFrame with a 'Symbol' column (bare NSE symbols, no
'.NS' suffix -- appended here to match this codebase's ticker convention
used everywhere else, e.g. "ACUTAAS.NS").

Both lists come back ALPHABETICAL BY COMPANY NAME, not index-weight
order (confirmed by inspecting the actual rows: 360ONE, 3MINDIA, ACC,
AIAENG, APLAPOLLO, ... for midcap150 -- not remotely what weight order
would look like). This matters: taking "the first 50" from the midcap150
list is an ARBITRARY ALPHABETICAL SLICE, not a liquidity/size-weighted
selection the way the original plan hoped it might be. Flagged here
rather than silently treated as the liquidity-biased selection it isn't --
if this backtest's results need a specific liquidity/size distribution
within the midcap group, this function does not currently provide it.

The installed nselib version's niftymidcap150_equity_list() is broken:
it points at the deprecated archives.nseindia.com domain via a plain
pd.read_csv() (no session/cookies), which returns HTTP 503 -- confirmed
with 3 live retries, not a transient blip. nifty50_equity_list() already
migrated to the working nsearchives.nseindia.com domain via nselib's own
nse_urlfetch() session helper. Worked around here by fetching the same
CSV directly from the working domain via nselib.libutil.nse_urlfetch()
(the same public, documented session helper nselib uses internally),
rather than waiting on an nselib upstream fix.
===============================================================================
"""
from __future__ import annotations

from io import BytesIO

import pandas as pd
from nselib import capital_market, libutil

from common.logger import get_logger

logger = get_logger(__name__)

# nselib's niftymidcap150_equity_list() is broken in the installed version
# (points at a dead archives.nseindia.com URL) -- fetching the same CSV
# directly from the working nsearchives.nseindia.com domain instead.
_MIDCAP150_URL = "https://nsearchives.nseindia.com/content/indices/ind_niftymidcap150list.csv"

MIDCAP_TRIM_COUNT = 50


def _to_ns_symbols(symbols: list[str]) -> list[str]:
    return [f"{symbol}.NS" for symbol in symbols]


def _fetch_midcap150_symbols() -> list[str]:
    """Direct workaround for nselib's broken niftymidcap150_equity_list()
    -- see module docstring."""
    response = libutil.nse_urlfetch(_MIDCAP150_URL)

    if response.status_code != 200:
        raise ConnectionError(
            f"NIFTY Midcap 150 list fetch failed: HTTP {response.status_code}"
        )

    data = pd.read_csv(BytesIO(response.content))
    return data["Symbol"].tolist()


def build_moderate_backtest_universe(midcap_trim_count: int = MIDCAP_TRIM_COUNT) -> list[str]:
    """
    ~100 tickers: full Nifty 50 (50 tickers) + first `midcap_trim_count`
    from Nifty Midcap 150, in whatever order niftymidcap150_equity_list()
    returns them (alphabetical by company name -- see module docstring;
    NOT a liquidity/size-weighted selection).

    Returns
    -------
    list[str] : de-duplicated ".NS"-suffixed symbols, Nifty 50 first.
    """
    nifty50 = capital_market.nifty50_equity_list()
    nifty50_symbols = _to_ns_symbols(nifty50["Symbol"].tolist())

    midcap_symbols_raw = _fetch_midcap150_symbols()
    midcap_trimmed = _to_ns_symbols(midcap_symbols_raw[:midcap_trim_count])

    # De-duplicate while preserving order (a ticker could theoretically
    # appear in both lists during an index reshuffle transition window).
    seen = set()
    universe = []
    for symbol in nifty50_symbols + midcap_trimmed:
        if symbol not in seen:
            seen.add(symbol)
            universe.append(symbol)

    logger.info(
        "Assembled moderate backtest universe: %d Nifty 50 + %d Midcap 150 (trimmed) = %d total.",
        len(nifty50_symbols), len(midcap_trimmed), len(universe),
    )

    return universe
