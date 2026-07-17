"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : yahoo_provider.py
Package     : Market Data

Purpose
-------
Yahoo Finance implementation of Falcon's market data provider.

Responsibilities
----------------
• Download historical OHLCV data
• Retrieve company information
• Retrieve corporate actions
• Retrieve financial statements
• Retrieve ownership data
• Retrieve analyst recommendations
• Retrieve news

Inputs
------
• Stock Symbol

Outputs
-------
• Pandas DataFrames
• Dictionaries
• Lists

Dependencies
------------
• yfinance
• pandas
• base_provider.py
• config.py

Future Enhancements
-------------------
• Retry logic
• Request throttling
• Async downloads
• Provider health monitoring

===============================================================================
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import yfinance as yf

from config import (
    YFINANCE_AUTO_ADJUST,
    YFINANCE_PROGRESS,
)

from common.logger import get_logger

from market_data.exceptions import (
    DownloadError,
    MarketDataError,
    ProviderError,
)

from market_data.providers.base_provider import BaseProvider

logger = get_logger(__name__)


class YahooProvider(BaseProvider):

    @property
    def name(self) -> str:
        return "Yahoo Finance"

    @property
    def capabilities(self) -> set[str]:

        return {
            "history",
            "company_info",
            "financials",
            "balance_sheet",
            "cashflow",
            "earnings",
            "dividends",
            "splits",
            "actions",
            "major_holders",
            "institutional_holders",
            "mutualfund_holders",
            "recommendations",
            "news",
        }

    # ------------------------------------------------------------------ #
    # Market Data
    # ------------------------------------------------------------------ #

    def get_history(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """
        Download historical OHLCV data.
        """

        try:

            ticker = yf.Ticker(symbol)

            df = ticker.history(
                start=start_date,
                end=end_date,
                auto_adjust=YFINANCE_AUTO_ADJUST,
                actions=False,
            )

            if df.empty:

                raise DownloadError(
                    f"No historical data returned for '{symbol}'."
                )

            df.reset_index(inplace=True)

            logger.info(
                "Downloaded %d candles for %s",
                len(df),
                symbol,
            )

            return df

        except DownloadError:

            raise

        except Exception as ex:

            raise ProviderError(str(ex)) from ex

    def get_intraday(
        self,
        symbol: str,
        interval: str,
    ) -> pd.DataFrame:

        raise NotImplementedError()

    def get_quote(self, symbol: str) -> dict:
        """
        Returns {'last_price', 'previous_close', 'change_pct'} using
        yfinance's fast_info — a lightweight current-price snapshot,
        not a full OHLC history download.
        """

        try:

            ticker = yf.Ticker(symbol)

            info = ticker.fast_info

            last = info.get("last_price")
            prev_close = info.get("previous_close")

        except Exception as ex:

            raise ProviderError(str(ex)) from ex

        if last is None or prev_close is None or prev_close == 0:

            raise MarketDataError(f"Incomplete quote data for {symbol}")

        change_pct = ((last - prev_close) / prev_close) * 100

        return {
            "last_price": last,
            "previous_close": prev_close,
            "change_pct": change_pct,
        }

    # ------------------------------------------------------------------ #
    # Company Information
    # ------------------------------------------------------------------ #

    def get_company_info(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """
        Retrieve company sector/industry metadata.
        """

        try:

            info = yf.Ticker(symbol).info

            return {
                "sector": info.get("sector", "Unknown"),
                "industry": info.get("industry", "Unknown"),
            }

        except Exception as ex:

            raise ProviderError(str(ex)) from ex

    # ------------------------------------------------------------------ #
    # Corporate Actions
    # ------------------------------------------------------------------ #

    def get_dividends(
        self,
        symbol: str,
    ) -> pd.DataFrame:

        raise NotImplementedError()

    def get_splits(
        self,
        symbol: str,
    ) -> pd.DataFrame:

        raise NotImplementedError()

    def get_actions(
        self,
        symbol: str,
    ) -> pd.DataFrame:

        raise NotImplementedError()

    # ------------------------------------------------------------------ #
    # Financial Statements
    # ------------------------------------------------------------------ #

    def get_financials(
        self,
        symbol: str,
    ) -> pd.DataFrame:

        raise NotImplementedError()

    def get_balance_sheet(
        self,
        symbol: str,
    ) -> pd.DataFrame:

        raise NotImplementedError()

    def get_cashflow(
        self,
        symbol: str,
    ) -> pd.DataFrame:

        raise NotImplementedError()

    def get_earnings(
        self,
        symbol: str,
    ) -> pd.DataFrame:

        raise NotImplementedError()

    # ------------------------------------------------------------------ #
    # Ownership
    # ------------------------------------------------------------------ #

    def get_major_holders(
        self,
        symbol: str,
    ) -> pd.DataFrame:

        raise NotImplementedError()

    def get_institutional_holders(
        self,
        symbol: str,
    ) -> pd.DataFrame:

        raise NotImplementedError()

    def get_mutualfund_holders(
        self,
        symbol: str,
    ) -> pd.DataFrame:

        raise NotImplementedError()

    # ------------------------------------------------------------------ #
    # Research
    # ------------------------------------------------------------------ #

    def get_recommendations(
        self,
        symbol: str,
    ) -> pd.DataFrame:

        raise NotImplementedError()

    def get_news(
        self,
        symbol: str,
    ) -> list[dict]:

        raise NotImplementedError()


market_provider = YahooProvider()