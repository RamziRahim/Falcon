"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : indicator_exporter.py
Package     : Technical Analysis

Purpose
-------
Exports enriched technical analysis data to Falcon's technical cache.

Responsibilities
----------------
• Save technical datasets
• Load technical datasets
• Delete technical datasets
• Check dataset existence

===============================================================================
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from config import TECHNICAL_DATA_FOLDER

from common.logger import get_logger
from technical_analysis.exceptions import IndicatorExportError

logger = get_logger(__name__)

EXPORT_DIR = Path(TECHNICAL_DATA_FOLDER)


class IndicatorExporter:
    """
    Handles storage of enriched technical datasets.
    """

    def __init__(self) -> None:

        EXPORT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ------------------------------------------------------------------ #

    def _path(
        self,
        symbol: str,
    ) -> Path:

        filename = symbol.replace("/", "_")

        return EXPORT_DIR / f"{filename}.parquet"

    # ------------------------------------------------------------------ #

    def exists(
        self,
        symbol: str,
    ) -> bool:

        return self._path(symbol).exists()

    # ------------------------------------------------------------------ #

    def save(
        self,
        symbol: str,
        dataframe: pd.DataFrame,
    ) -> None:

        try:

            path = self._path(symbol)

            temp = path.with_suffix(".tmp")

            dataframe.to_parquet(
                temp,
                index=False,
            )

            temp.replace(path)

            logger.info(
                "Technical data exported: %s",
                symbol,
            )

        except Exception as ex:

            raise IndicatorExportError(
                str(ex)
            ) from ex

    # ------------------------------------------------------------------ #

    def load(
        self,
        symbol: str,
    ) -> pd.DataFrame:

        try:

            return pd.read_parquet(
                self._path(symbol)
            )

        except Exception as ex:

            raise IndicatorExportError(
                str(ex)
            ) from ex

    # ------------------------------------------------------------------ #

    def delete(
        self,
        symbol: str,
    ) -> None:

        path = self._path(symbol)

        if path.exists():

            path.unlink()

            logger.info(
                "Deleted technical dataset: %s",
                symbol,
            )


indicator_exporter = IndicatorExporter()
