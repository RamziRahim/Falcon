"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : exceptions.py
Package     : Market Data
Version     : 0.3.0
Author      : Ramzi Rahim

Purpose
-------
Defines custom exception classes for the Market Data package.

Responsibilities
----------------
• Provide package-specific exceptions
• Improve error readability
• Enable granular exception handling
• Isolate market data failures from other Falcon packages

Inputs
------
None

Outputs
-------
Custom exception classes

Dependencies
------------
None

Future Enhancements
-------------------
• Error codes
• Exception metadata
• Retry recommendations
• Provider-specific exception hierarchy

===============================================================================
"""


class MarketDataError(Exception):
    """
    Base exception for all Market Data related errors.
    """
    pass


class ProviderError(MarketDataError):
    """
    Raised when a market data provider fails.
    """
    pass


class DownloadError(MarketDataError):
    """
    Raised when OHLCV download fails.
    """
    pass


class CacheError(MarketDataError):
    """
    Raised when cache read/write/update/delete fails.
    """
    pass


class CacheSynchronizationError(MarketDataError):
    """
    Raised when cache synchronization fails.
    """
    pass


class DataValidationError(MarketDataError):
    """
    Raised when downloaded market data fails validation.
    """
    pass


class DataLoadError(MarketDataError):
    """
    Raised when cached market data cannot be loaded.
    """
    pass


class ProviderAuthenticationError(ProviderError):
    """
    Raised when provider authentication fails.
    """
    pass


class ProviderRateLimitError(ProviderError):
    """
    Raised when the provider rate limit is exceeded.
    """
    pass


class UnsupportedProviderError(ProviderError):
    """
    Raised when the requested provider is not supported.
    """
    pass


class InvalidSymbolError(MarketDataError):
    """
    Raised when an invalid or unsupported symbol is requested.
    """
    pass


class CorruptedDataError(DataValidationError):
    """
    Raised when cached market data is corrupted.
    """
    pass