"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : data_collection_engine.py
Package     : Market Data

Purpose
-------
Orchestrates Falcon's market data collection pipeline.

Responsibilities
----------------
• Synchronize cache
• Download market data
• Validate downloaded data
• Update local cache
• Produce execution summary

Inputs
------
• List of stock symbols

Outputs
-------
• DataCollectionResult

Dependencies
------------
• cache_synchronizer.py
• downloader.py
• data_validator.py
• cache_manager.py

Future Enhancements
-------------------
• Parallel execution
• Progress reporting
• Execution metrics
• Notifications

===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass

from common.logger import get_logger

from market_data.cache_manager import cache_manager
from market_data.cache_synchronizer import cache_synchronizer
from market_data.downloader import downloader
from market_data.data_validator import market_data_validator

logger = get_logger(__name__)


# =============================================================================
# Result
# =============================================================================


@dataclass(slots=True)
class DataCollectionResult:

    downloaded: int = 0

    updated: int = 0

    failed: int = 0

    warnings: int = 0


# =============================================================================
# Engine
# =============================================================================


class DataCollectionEngine:
    """
    Executes Falcon's market data collection pipeline.
    """

    def run(
        self,
        symbols: list[str],
    ) -> DataCollectionResult:
        """
        Execute data collection pipeline.

        Parameters
        ----------
        symbols : list[str]

        Returns
        -------
        DataCollectionResult
        """

        logger.info(
            "Starting Data Collection Engine..."
        )

        result = DataCollectionResult()

        # ---------------------------------------------------------- #
        # Synchronize Cache
        # ---------------------------------------------------------- #

        sync = cache_synchronizer.synchronize(
            symbols
        )

        logger.info(
            "Synchronization complete "
            "(Added=%d Retained=%d Removed=%d)",
            sync.added_count,
            sync.retained_count,
            sync.removed_count,
        )

        # ---------------------------------------------------------- #
        # Download Data
        # ---------------------------------------------------------- #

        working_symbols = (
        sync.added +
        sync.retained
        )

        datasets = downloader.download(working_symbols)

        result.downloaded = len(datasets)

        # ---------------------------------------------------------- #
        # Validate + Cache
        # ---------------------------------------------------------- #

        for symbol, dataframe in datasets.items():

            validation = (
                market_data_validator
                .validate_history(dataframe)
            )

            if not validation.valid:

                logger.error(
                    "Validation failed for %s",
                    symbol,
                )

                result.failed += 1

                continue

            if validation.warnings:

                result.warnings += len(
                    validation.warnings
                )

                logger.warning(
                    "%s validation warnings: %s",
                    symbol,
                    validation.warnings,
                )

            cache_manager.update(
                symbol,
                dataframe,
            )

            result.updated += 1

        logger.info(
            "Data Collection Complete "
            "(Downloaded=%d Updated=%d Failed=%d Warnings=%d)",
            result.downloaded,
            result.updated,
            result.failed,
            result.warnings,
        )

        return result


market_data_engine = DataCollectionEngine()