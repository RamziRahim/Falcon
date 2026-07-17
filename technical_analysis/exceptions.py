"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : exceptions.py
Package     : Technical Analysis

Purpose
-------
Defines exceptions used by Falcon's Technical Analysis Engine.

===============================================================================
"""

from __future__ import annotations


class TechnicalAnalysisError(Exception):
    """
    Base exception for the Technical Analysis Engine.
    """


class IndicatorCalculationError(TechnicalAnalysisError):
    """
    Raised when indicator calculation fails.
    """


class IndicatorValidationError(TechnicalAnalysisError):
    """
    Raised when calculated indicators fail validation.
    """


class IndicatorExportError(TechnicalAnalysisError):
    """
    Raised when exporting indicator data fails.
    """