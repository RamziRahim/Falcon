"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : nse_session_client.py
Package     : Market Data / Providers

Purpose
-------
Vendored, session-reusing replacement for nselib 2.5.1's
capital_market.price_volume_and_deliverable_position_data() -- NOT a
monkeypatch of the installed package, a real local copy, because
nselib's public API gives no way to inject a pre-built requests.Session()
anywhere in its real call chain. Confirmed by reading all three levels
nselib 2.5.1 actually uses for this call:
  - nselib.libutil.nse_urlfetch() hardcodes `requests.session()`
    internally, no session parameter.
  - nselib.capital_market.get_func.get_price_volume_and_deliverable_
    position_data() calls nse_urlfetch() directly, no session parameter
    of its own to forward one through.
  - nselib.capital_market.capital_market_data.price_volume_and_
    deliverable_position_data() (the public function
    market_data/providers/nse_provider.py actually calls) has no session
    parameter either.

Why this matters: nse_urlfetch() does TWO HTTP requests per call -- an
origin-URL GET to fetch fresh cookies, then the real data GET -- and
creates a brand-new requests.Session() (fresh TCP/TLS handshake, no
connection-pool reuse) every single time it's called. For Falcon's live
scan (one call per ticker, ~50 tickers), that's 50 fresh sessions and 50
redundant cookie fetches, when one session with cookies fetched once
comfortably serves the whole batch. Falcon's own NSEProvider holds one
NseSessionClient instance for its lifetime (see nse_provider.py), so
this reuse spans an entire scan, not just one ticker.

Deliberately narrow scope: only the fetch-and-session layer is
reimplemented below. Everything else (date-range >365-day chunking,
symbol cleaning, period-to-date-range derivation, response column
cleanup) is UNCHANGED -- imported directly from nselib itself, not
duplicated, so this file can't silently drift from nselib's own logic
for anything except the one thing it exists to fix.

This does NOT touch request RATE or add concurrency -- session reuse is
strictly about eliminating redundant per-call handshake/cookie overhead,
which carries none of the IP-blocking risk unbounded parallel requests
would (see the investigation this module came out of: NSE's own
community-documented ~3 req/sec ceiling, with real reports of IP-level
blocking for scrapers that exceed it -- that risk assessment is the
reason this file exists instead of a concurrent downloader).

Vendored from nselib==2.5.1 (2026-08-18). If nselib's own historical-
data endpoint URL, payload shape, or response format ever changes
upstream, this file needs the same update applied here manually --
it will NOT pick up nselib package upgrades automatically.
===============================================================================
"""
from __future__ import annotations

import datetime as dt
import logging
from datetime import datetime
from io import StringIO

import pandas as pd
import requests

from nselib.constants import dd_mm_yyyy, price_volume_and_deliverable_position_data_columns
from nselib.errors import NSEdataNotFound
from nselib.libutil import (
    cleaning_nse_symbol,
    default_header,
    derive_from_and_to_date,
    header,
    validate_date_param,
)

logger = logging.getLogger(__name__)

_ORIGIN_URL = "https://nsewebsite-staging.nseindia.com/report-detail/eq_security"
_DATA_URL = "https://www.nseindia.com/api/historicalOR/generateSecurityWiseHistoricalData?"

_REQUEST_TIMEOUT_SECONDS = 30


class NseSessionClient:
    """One requests.Session(), cookies fetched once (lazily, on first
    use) and reused across every call made through this client instead
    of nselib's own fresh-session-and-cookies-per-call behavior.

    Cookies re-fetched automatically if a request comes back non-200 --
    same one-retry-then-recover behavior a fresh nse_urlfetch() call
    would have gotten "for free" by re-fetching cookies every time, so a
    long-running batch degrades gracefully instead of silently failing
    every remaining ticker if NSE ever expires the cookies mid-batch.
    """

    def __init__(self) -> None:
        self._session = requests.session()
        self._cookies = None

    def _prime_cookies(self) -> None:
        nse_live = self._session.get(_ORIGIN_URL, headers=default_header, timeout=_REQUEST_TIMEOUT_SECONDS)
        self._cookies = nse_live.cookies

    def _fetch(self, url: str) -> requests.Response:
        if self._cookies is None:
            self._prime_cookies()

        response = self._session.get(url, headers=header, cookies=self._cookies, timeout=_REQUEST_TIMEOUT_SECONDS)

        if response.status_code != 200:
            self._prime_cookies()
            response = self._session.get(url, headers=header, cookies=self._cookies, timeout=_REQUEST_TIMEOUT_SECONDS)

        return response

    def _get_price_volume_and_deliverable_position_data(self, symbol: str, from_date: str, to_date: str) -> pd.DataFrame:
        """Vendored from nselib.capital_market.get_func.get_price_volume_and_deliverable_position_data() (2.5.1)."""
        payload = f"from={from_date}&to={to_date}&symbol={symbol}&type=priceVolumeDeliverable&series=ALL&csv=true"
        try:
            data_text = self._fetch(_DATA_URL + payload).text
            data_text = data_text.replace("\x82", "").replace("â¹", "In Rs")
        except Exception as ex:
            logger.error("Failed to fetch data: %s", ex, exc_info=ex)
            raise NSEdataNotFound(f" Resource not available MSG: {ex}")

        data_df = pd.read_csv(StringIO(data_text))
        data_df.columns = [name.replace(" ", "") for name in data_df.columns]
        return data_df

    def price_volume_and_deliverable_position_data(
        self, symbol: str, from_date: str = None, to_date: str = None, period: str = None,
    ) -> pd.DataFrame:
        """Vendored from nselib.capital_market.capital_market_data.
        price_volume_and_deliverable_position_data() (2.5.1) -- identical
        year-chunking/column-cleanup logic, calling THIS client's own
        session-reusing fetch instead of nselib's fresh-session-per-call
        nse_urlfetch(). Same signature as the nselib function it
        replaces, so nse_provider.py's call site barely changes."""
        validate_date_param(from_date, to_date, period)
        symbol = cleaning_nse_symbol(symbol=symbol)
        from_date, to_date = derive_from_and_to_date(from_date=from_date, to_date=to_date, period=period)

        nse_df = pd.DataFrame(columns=price_volume_and_deliverable_position_data_columns)
        from_date = datetime.strptime(from_date, dd_mm_yyyy)
        to_date = datetime.strptime(to_date, dd_mm_yyyy)
        load_days = (to_date - from_date).days

        while load_days > 0:
            if load_days > 365:
                end_date = (from_date + dt.timedelta(364)).strftime(dd_mm_yyyy)
                start_date = from_date.strftime(dd_mm_yyyy)
            else:
                end_date = to_date.strftime(dd_mm_yyyy)
                start_date = from_date.strftime(dd_mm_yyyy)

            data_df = self._get_price_volume_and_deliverable_position_data(symbol=symbol, from_date=start_date, to_date=end_date)
            from_date = from_date + dt.timedelta(365)
            load_days = (to_date - from_date).days

            if not data_df.empty:
                data_df = data_df.fillna("-")
                nse_df = nse_df.fillna("-")
                data_df = data_df.dropna(axis=1, how="all")
                nse_df = nse_df.dropna(axis=1, how="all")
                if not data_df.empty:
                    nse_df = pd.concat([nse_df, data_df], ignore_index=True)

        nse_df["TotalTradedQuantity"] = pd.to_numeric(nse_df["TotalTradedQuantity"].astype(str).str.replace(",", ""), errors="coerce")
        nse_df["TurnoverInRs"] = pd.to_numeric(nse_df["TurnoverInRs"].astype(str).str.replace(",", ""), errors="coerce")
        nse_df["No.ofTrades"] = pd.to_numeric(nse_df["No.ofTrades"].astype(str).str.replace(",", ""), errors="coerce")
        nse_df["DeliverableQty"] = pd.to_numeric(nse_df["DeliverableQty"].astype(str).str.replace(",", ""), errors="coerce")
        return nse_df
