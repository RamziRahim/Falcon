"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : base_provider.py
Package     : Market Data

Purpose
-------
Defines the abstract interface for all external market data providers.

Responsibilities
----------------
• Define Falcon's provider contract
• Standardize provider capabilities
• Isolate Falcon from vendor-specific APIs

Inputs
------
None

Outputs
-------
Abstract provider interface

Dependencies
------------
• abc

Future Enhancements
-------------------
• Authentication support
• Rate limiting
• Async providers
• Provider health monitoring

===============================================================================
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Dict, Set

import pandas as pd


class BaseProvider(ABC):
    """
    Abstract base class for all Falcon data providers.
    """

    # ------------------------------------------------------------------ #
    # Provider Information
    # ------------------------------------------------------------------ #

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Provider name.
        """
        pass

    @property
    @abstractmethod
    def capabilities(self) -> Set[str]:
        """
        Supported provider capabilities.

        Example
        -------
        {
            "history",
            "company_info",
            "financials",
            "news"
        }
        """
        pass

    # ------------------------------------------------------------------ #
    # Market Data
    # ------------------------------------------------------------------ #

    @abstractmethod
    def get_history(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """
        Returns historical OHLCV data.
        """
        pass

    @abstractmethod
    def get_intraday(
        self,
        symbol: str,
        interval: str,
    ) -> pd.DataFrame:
        """
        Returns intraday market data.
        """
        pass

    # ------------------------------------------------------------------ #
    # Corporate Actions
    # ------------------------------------------------------------------ #

    @abstractmethod
    def get_dividends(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Returns dividend history.
        """
        pass

    @abstractmethod
    def get_splits(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Returns stock split history.
        """
        pass

    @abstractmethod
    def get_actions(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Returns corporate actions.
        """
        pass

    # ------------------------------------------------------------------ #
    # Company Information
    # ------------------------------------------------------------------ #

    @abstractmethod
    def get_company_info(
        self,
        symbol: str,
    ) -> Dict[str, Any]:
        """
        Returns company metadata.
        """
        pass

    # ------------------------------------------------------------------ #
    # Financial Statements
    # ------------------------------------------------------------------ #

    @abstractmethod
    def get_financials(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Returns financial statements.
        """
        pass

    @abstractmethod
    def get_balance_sheet(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Returns balance sheet.
        """
        pass

    @abstractmethod
    def get_cashflow(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Returns cash flow statement.
        """
        pass

    @abstractmethod
    def get_earnings(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Returns earnings history.
        """
        pass

    # ------------------------------------------------------------------ #
    # Ownership
    # ------------------------------------------------------------------ #

    @abstractmethod
    def get_major_holders(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Returns major shareholders.
        """
        pass

    @abstractmethod
    def get_institutional_holders(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Returns institutional holdings.
        """
        pass

    @abstractmethod
    def get_mutualfund_holders(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Returns mutual fund holdings.
        """
        pass

    # ------------------------------------------------------------------ #
    # Research
    # ------------------------------------------------------------------ #

    @abstractmethod
    def get_recommendations(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Returns analyst recommendations.
        """
        pass

    @abstractmethod
    def get_news(
        self,
        symbol: str,
    ) -> list[dict]:
        """
        Returns latest news.
        """
        pass