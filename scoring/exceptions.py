"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : exceptions.py
Package     : Scoring

Purpose
-------
Defines custom exception classes for the Scoring package.

===============================================================================
"""

from __future__ import annotations


class ScoringError(Exception):
    """
    Base exception for all Scoring related errors.
    """
    pass


class UniverseError(ScoringError):
    """
    Raised when the comparison universe cannot be resolved.
    """
    pass


class SectorMappingError(ScoringError):
    """
    Raised when sector/industry resolution fails.
    """
    pass


class BenchmarkError(ScoringError):
    """
    Raised when benchmark index data cannot be fetched or cached.
    """
    pass


class RelativeStrengthError(ScoringError):
    """
    Raised when RS Rating calculation fails.
    """
    pass


class RelativeVolumeError(ScoringError):
    """
    Raised when Relative Volume calculation fails.
    """
    pass


class SectorRotationError(ScoringError):
    """
    Raised when sector rotation ranking fails.
    """
    pass
