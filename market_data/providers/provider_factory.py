"""
Falcon AI Swing Trading Platform
Module: provider_factory.py

Creates the configured market data provider.
"""

from __future__ import annotations

from config import MARKET_DATA_PROVIDER

from market_data.exceptions import UnsupportedProviderError
from market_data.providers.base_provider import BaseProvider
from market_data.providers.nse_provider import NSEProvider
from market_data.providers.yahoo_provider import YahooProvider


def get_provider() -> BaseProvider:
    """
    Returns the configured market data provider.
    """

    provider = MARKET_DATA_PROVIDER.upper().strip()

    if provider == "NSE":
        return NSEProvider()

    if provider == "YAHOO":
        return YahooProvider()

    raise UnsupportedProviderError(
        f"Unsupported market data provider: {MARKET_DATA_PROVIDER}"
    )
