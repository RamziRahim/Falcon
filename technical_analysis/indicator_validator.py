"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : indicator_validator.py
Package     : Technical Analysis

Purpose
-------
Validates market data before and after technical indicators are calculated.

===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
import pandas as pd
from common.logger import get_logger
from technical_analysis.exceptions import IndicatorValidationError

logger = get_logger(__name__)


@dataclass(slots=True)
class ValidationResult:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class IndicatorValidator:
    """
    Validates input market data and output indicators for Falcon.
    """

    # Changed from 30 to 200 to support SMA_200 and EMA_200 lookbacks safely
    MINIMUM_ROWS = 20

    def validate(self, dataframe: pd.DataFrame) -> ValidationResult:
        result = ValidationResult()

        if dataframe.empty:
            result.valid = False
            result.errors.append("Market data is empty.")
            return result

        if len(dataframe) < self.MINIMUM_ROWS:
            result.valid = False
            result.errors.append(
                f"Minimum {self.MINIMUM_ROWS} candles required for long-term indicators."
            )

        if dataframe.columns.duplicated().any():
            result.valid = False
            result.errors.append("Duplicate column names detected.")

        if dataframe.index.duplicated().any():
            result.warnings.append("Duplicate index values detected.")

        if dataframe.isna().all().any():
            result.valid = False
            result.errors.append(
                "One or more columns contain only missing values."
            )

        logger.info(
            "Indicator validation complete. Valid=%s Errors=%d Warnings=%d",
            result.valid,
            len(result.errors),
            len(result.warnings),
        )

        return result

    def validate_indicators(self, dataframe: pd.DataFrame) -> ValidationResult:
        """
        Verifies that all required technical indicator columns were calculated
        and exist in the final data sheet.
        """
        result = self.validate(dataframe)
        if not result.valid:
            return result

        # The master list of expected columns (SMA_20 updated here!)
        expected_columns = {
            "Date", "Open", "High", "Low", "Close", "Volume",
            "SMA_20", "SMA_50", "SMA_150", "SMA_200",  # Updated from SMA_25 to SMA_20
            "EMA_20", "EMA_50", "EMA_150", "EMA_200",
            "RSI_14", "MACD_Line", "MACD_Signal", "MACD_Hist",
            "ATR_14", "ADX_14", "DI_Plus_14", "DI_Minus_14",
            "OBV", "BB_Upper", "BB_Middle", "BB_Lower"
        }

        missing_cols = [col for col in expected_columns if col not in dataframe.columns]
        if missing_cols:
            result.valid = False
            result.errors.append(f"Missing calculated indicators: {missing_cols}")

        return result

    def ensure_valid(self, dataframe: pd.DataFrame) -> None:
        result = self.validate(dataframe)

        if not result.valid:
            raise IndicatorValidationError(
                "; ".join(result.errors)
            )


indicator_validator = IndicatorValidator()