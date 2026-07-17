"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : cache_manager.py
Package     : Market Data
Version     : 0.3.0
Author      : Ramzi Rahim

Purpose
-------
Provides a storage abstraction layer for Falcon market data cache.

Responsibilities
----------------
• Save market data
• Load market data
• Update existing cache
• Delete cached data
• Check cache existence
• List cached symbols
• Retrieve latest cached date

Inputs
------
• Stock Symbol
• Market Data DataFrame

Outputs
-------
• Cached market data

Dependencies
------------
• pandas
• pathlib
• config.py

Future Enhancements
-------------------
• DuckDB backend
• SQLite backend
• Compression
• Cache versioning

===============================================================================
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

import pandas as pd

from config import (
    RAW_DATA_FOLDER,
    DATE_COLUMN,
    CACHE_FILE_EXTENSION,
    FALCON_NAME,
    FALCON_VERSION,
)

from common.logger import get_logger
from market_data.exceptions import CacheError

logger = get_logger(__name__)

INVALID_FILENAME_CHARS = r'[<>:"/\\|?*]'


class CacheManager:
    """
    Manages Falcon market data cache.
    """

    def __init__(
        self,
        cache_directory: str = RAW_DATA_FOLDER,
    ) -> None:

        self.cache_dir = Path(cache_directory)

        self.cache_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ------------------------------------------------------------------ #

    def _cache_path(
        self,
        symbol: str,
    ) -> Path:
        """
        Returns cache file path.
        """

        filename = re.sub(
            INVALID_FILENAME_CHARS,
            "_",
            symbol,
        )

        return (
            self.cache_dir
            / f"{filename}{CACHE_FILE_EXTENSION}"
        )

    # ------------------------------------------------------------------ #

    def exists(
        self,
        symbol: str,
    ) -> bool:
        """
        Checks whether cache exists.
        """

        return self._cache_path(symbol).exists()

    # ------------------------------------------------------------------ #

    def save(
        self,
        symbol: str,
        dataframe: pd.DataFrame,
    ) -> None:
        """
        Saves market data.
        """

        try:

            if dataframe.empty:

                raise CacheError(
                    "Cannot cache an empty DataFrame."
                )

            path = self._cache_path(symbol)

            temp = path.with_suffix(".tmp")

            dataframe.to_parquet(
                temp,
                index=False,
            )

            temp.replace(path)

            logger.info(
                "Saved cache: %s",
                symbol,
            )

        except Exception as ex:

            raise CacheError(str(ex)) from ex

    # ------------------------------------------------------------------ #

    def load(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Loads cached market data.
        """

        try:

            return pd.read_parquet(
                self._cache_path(symbol)
            )

        except Exception as ex:

            raise CacheError(str(ex)) from ex

    # ------------------------------------------------------------------ #

    def update(
        self,
        symbol: str,
        dataframe: pd.DataFrame,
    ) -> None:
        """
        Updates cached market data.
        """

        try:

            if dataframe.empty:

                raise CacheError(
                    "Cannot update using an empty DataFrame."
                )

            if not self.exists(symbol):

                self.save(
                    symbol,
                    dataframe,
                )

                return

            current = self.load(symbol)

            merged = pd.concat(
                [current, dataframe],
                ignore_index=True,
            )

            merged.drop_duplicates(
                subset=DATE_COLUMN,
                keep="last",
                inplace=True,
            )

            merged.sort_values(
                DATE_COLUMN,
                inplace=True,
            )

            merged.reset_index(
                drop=True,
                inplace=True,
            )

            self.save(
                symbol,
                merged,
            )

            logger.info(
                "Updated cache: %s",
                symbol,
            )

        except Exception as ex:

            raise CacheError(str(ex)) from ex

    # ------------------------------------------------------------------ #

    def delete(
        self,
        symbol: str,
    ) -> None:
        """
        Deletes cached market data.
        """

        try:

            path = self._cache_path(symbol)

            if path.exists():

                path.unlink()

                logger.info(
                    "Deleted cache: %s",
                    symbol,
                )

        except Exception as ex:

            raise CacheError(str(ex)) from ex

    # ------------------------------------------------------------------ #

    def clear(self) -> None:
        """
        Deletes all cached market data.
        """

        try:

            for file in self.cache_dir.glob(
                f"*{CACHE_FILE_EXTENSION}"
            ):

                file.unlink()

            logger.info(
                "Cache cleared."
            )

        except Exception as ex:

            raise CacheError(str(ex)) from ex

    # ------------------------------------------------------------------ #

    def list_symbols(self) -> List[str]:
        """
        Lists all cached symbols.
        """

        return sorted(
            file.stem
            for file in self.cache_dir.glob(
                f"*{CACHE_FILE_EXTENSION}"
            )
        )

    # ------------------------------------------------------------------ #

    def count(self) -> int:
        """
        Returns number of cached symbols.
        """

        return len(
            self.list_symbols()
        )

    # ------------------------------------------------------------------ #

    def last_date(
        self,
        symbol: str,
    ) -> Optional[pd.Timestamp]:
        """
        Returns latest cached trading date.
        """

        if not self.exists(symbol):

            return None

        df = self.load(symbol)

        if df.empty:

            return None

        return pd.to_datetime(
            df[DATE_COLUMN],
            errors="coerce",
        ).max()


cache_manager = CacheManager()