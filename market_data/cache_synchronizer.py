"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : cache_synchronizer.py
Package     : Market Data

Purpose
-------
Synchronizes Falcon's local market data cache with the latest candidate universe.

Responsibilities
----------------
• Compare current candidates with cached symbols
• Remove obsolete cache
• Identify newly added symbols
• Report synchronization summary

Inputs
------
• Current candidate symbols

Outputs
-------
• SynchronizationResult

Dependencies
------------
• cache_manager.py

Future Enhancements
-------------------
• Dry-run mode
• Archive removed cache
• Synchronization reports
• Multi-cache support

===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Set

from common.logger import get_logger
from market_data.cache_manager import cache_manager
from market_data.exceptions import CacheSynchronizationError

logger = get_logger(__name__)


@dataclass(slots=True)
class SynchronizationResult:
    """
    Result of cache synchronization.
    """

    added: List[str] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)
    retained: List[str] = field(default_factory=list)

    @property
    def added_count(self) -> int:
        return len(self.added)

    @property
    def removed_count(self) -> int:
        return len(self.removed)

    @property
    def retained_count(self) -> int:
        return len(self.retained)


class CacheSynchronizer:
    """
    Synchronizes Falcon cache with current candidate universe.
    """

    def synchronize(
        self,
        candidate_symbols: List[str],
    ) -> SynchronizationResult:
        """
        Synchronize local cache with candidate universe.

        Parameters
        ----------
        candidate_symbols : List[str]

        Returns
        -------
        SynchronizationResult
        """

        try:

            candidate_set: Set[str] = set(candidate_symbols)

            cache_set: Set[str] = set(
                cache_manager.list_symbols()
            )

            added = sorted(
                candidate_set - cache_set
            )

            removed = sorted(
                cache_set - candidate_set
            )

            retained = sorted(
                candidate_set & cache_set
            )

            # Remove obsolete cache files
            for symbol in removed:

                cache_manager.delete(symbol)

            result = SynchronizationResult(
                added=added,
                removed=removed,
                retained=retained,
            )

            logger.info(
                "Cache synchronization complete. "
                "Added=%d, Removed=%d, Retained=%d",
                result.added_count,
                result.removed_count,
                result.retained_count,
            )

            return result

        except Exception as ex:

            raise CacheSynchronizationError(
                str(ex)
            ) from ex


cache_synchronizer = CacheSynchronizer()