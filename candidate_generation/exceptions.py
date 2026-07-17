"""
Falcon - Candidate Generation
Module: exceptions.py
Version: 1.1.0

Custom exceptions used by the Candidate Generation package.
"""


class CandidateGenerationError(Exception):
    """Base exception for all candidate generation errors."""
    pass


class AuthenticationError(CandidateGenerationError):
    """Authentication failed."""
    pass


class SessionExpiredError(AuthenticationError):
    """Authenticated session is no longer valid."""
    pass


class StrategyError(CandidateGenerationError):
    """Base exception for strategy-related failures."""
    pass


class StrategyNotFoundError(StrategyError):
    """Requested strategy folder or configuration was not found."""
    pass


class InvalidStrategyError(StrategyError):
    """Strategy configuration is invalid."""
    pass


class QueryLoadError(StrategyError):
    """Unable to load the strategy query."""
    pass


class SourceExecutionError(CandidateGenerationError):
    """Failed while executing a candidate source."""
    pass


class QueryExecutionError(SourceExecutionError):
    """Screen/query execution failed."""
    pass


class TableParsingError(SourceExecutionError):
    """Unable to parse the result table."""
    pass


class SymbolExtractionError(SourceExecutionError):
    """Unable to extract ticker symbols."""
    pass


class DataNormalizationError(SourceExecutionError):
    """Failed while normalizing candidate data."""
    pass


class ConsolidationError(CandidateGenerationError):
    """Failed while consolidating multiple candidate lists."""
    pass


class ExportError(CandidateGenerationError):
    """Failed while exporting the master watchlist."""
    pass
