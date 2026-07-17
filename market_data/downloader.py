
"""
Falcon AI Swing Trading Platform
Module: downloader.py

Updated to use Provider Factory.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List

import pandas as pd

from config import DEFAULT_HISTORY_YEARS

from common.logger import get_logger

from market_data.cache_manager import cache_manager
from market_data.providers.base_provider import BaseProvider
from market_data.providers.provider_factory import get_provider

logger = get_logger(__name__)


class Downloader:

    def __init__(
        self,
        provider: BaseProvider,
    ) -> None:
        self.provider = provider

    def download(
        self,
        symbols: List[str],
    ) -> Dict[str, pd.DataFrame]:

        downloads: Dict[str, pd.DataFrame] = {}

        logger.info(
            "Downloading market data for %d symbols...",
            len(symbols),
        )

        for symbol in symbols:
            try:
                df = self._download_symbol(symbol)

                if df is not None:
                    downloads[symbol] = df

            except Exception as ex:
                logger.exception(
                    "Failed downloading %s : %s",
                    symbol,
                    ex,
                )

        logger.info(
            "Download complete. Successful downloads: %d / %d",
            len(downloads),
            len(symbols),
        )

        return downloads

    def _download_symbol(
        self,
        symbol: str,
    ) -> pd.DataFrame | None:

        today = date.today()
        start_date = self._calculate_start_date(today)

        last_cached_date = None

        if cache_manager.exists(symbol):
            last_cached_date = cache_manager.last_date(symbol)

            if last_cached_date is not None:
                start_date = last_cached_date.date() + timedelta(days=1)

        if start_date >= today:
            logger.info("%s is already up to date.", symbol)
            return None

        df = self.provider.get_history(
            symbol=symbol,
            start_date=start_date,
            end_date=today,
        )

        if df.empty:
            logger.info("%s returned no new data.", symbol)
            return None

        df = self._filter_new_rows(df, last_cached_date)

        if df.empty:
            logger.info("%s is already up to date.", symbol)
            return None

        logger.info(
            "%s downloaded %d new candle(s).",
            symbol,
            len(df),
        )

        return df

    @staticmethod
    def _calculate_start_date(today: date) -> date:
        return today - timedelta(days=365 * DEFAULT_HISTORY_YEARS)

    @staticmethod
    def _filter_new_rows(
        dataframe: pd.DataFrame,
        last_cached_date,
    ) -> pd.DataFrame:

        if last_cached_date is None:
            return dataframe

        df = dataframe.copy()

        df["Date"] = (
            pd.to_datetime(df["Date"])
            .dt.tz_localize(None)
        )

        last_cached_date = (
            pd.Timestamp(last_cached_date)
            .tz_localize(None)
        )

        df = df[df["Date"] > last_cached_date]

        return df.reset_index(drop=True)


provider = get_provider()

downloader = Downloader(provider)
