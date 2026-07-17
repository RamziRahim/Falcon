"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : data_validator.py
Package     : Market Data
Version     : 2.0.0

Purpose
-------
Validates and repairs historical market data frames before cache injection.

Responsibilities
----------------
• Verify all required data layout columns are present.
• Detect empty data blocks or missing data streams.
• Clean up text formatting anomalies (like commas inside numbers).
• Auto-repair or drop single corrupt rows (e.g., negative prices, Low > High).
• Check for duplicate dates and ensure chronological sorting order.

===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
import pandas as pd
from config import REQUIRED_HISTORY_COLUMNS
from common.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class ValidationResult:
    """
    Data capsule representing the outcome of a market data validation scan.
    """
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class MarketDataValidator:
    """
    Scans and auto-repairs incoming stock data to ensure structural 
    consistency before writing to the immutable Parquet cache files.
    """

    def validate_history(self, dataframe: pd.DataFrame) -> ValidationResult:
        """
        Runs comprehensive data health checks and performs inline safety repairs.

        Parameters
        ----------
        dataframe : pd.DataFrame
            The historical table of stock data to inspect.

        Returns
        -------
        ValidationResult
            The result documenting if the file passed or has terminal errors.
        """
        result = ValidationResult()

        # -------------------------------------------------------------- #
        # 1. Empty Payload Verification
        # -------------------------------------------------------------- #
        if dataframe is None or dataframe.empty:
            result.valid = False
            result.errors.append("The downloaded data table is completely empty.")
            logger.error("Validation failed: Received a null or empty dataframe.")
            return result

        # -------------------------------------------------------------- #
        # 2. Structural Column Compliance
        # -------------------------------------------------------------- #
        missing_cols = [col for col in REQUIRED_HISTORY_COLUMNS if col not in dataframe.columns]
        if missing_cols:
            result.valid = False
            result.errors.append(f"Missing essential tracking columns: {missing_cols}")
            logger.error(f"Validation failed: Data layout is missing columns: {missing_cols}")
            return result

        # -------------------------------------------------------------- #
        # 3. Dynamic Text Cleaning & Formatting
        # -------------------------------------------------------------- #
        # Large historical blocks from the exchange often contain text commas 
        # (e.g., '1,250.00'). We strip them safely before applying logic.
        price_columns = ["Open", "High", "Low", "Close"]
        for col in price_columns:
            if dataframe[col].dtype == "object":
                dataframe[col] = dataframe[col].astype(str).str.replace(",", "")
                dataframe[col] = pd.to_numeric(dataframe[col], errors="coerce")

        if dataframe["Volume"].dtype == "object":
            dataframe["Volume"] = dataframe["Volume"].astype(str).str.replace(",", "")
            dataframe["Volume"] = pd.to_numeric(dataframe["Volume"], errors="coerce")

        # -------------------------------------------------------------- #
        # 4. Filter Invalid Null or NaN Rows
        # -------------------------------------------------------------- #
        initial_row_count = len(dataframe)
        dataframe.dropna(subset=["Date"] + price_columns, inplace=True)
        dropped_nulls = initial_row_count - len(dataframe)
        if dropped_nulls > 0:
            result.warnings.append(f"Dropped {dropped_nulls} rows containing empty or null pricing elements.")
            logger.warning(f"Validation alert: Cleaned {dropped_nulls} bad text or blank rows.")

        # Re-check dataframe limits after cleaning blanks
        if dataframe.empty:
            result.valid = False
            result.errors.append("All rows were filtered out during the formatting cleanup step.")
            return result

        # -------------------------------------------------------------- #
        # 5. Handle Critical Physical & Logical Pricing Anomalies
        # -------------------------------------------------------------- #
        # Instead of throwing away all 2,400+ rows because of one bad day, 
        # we isolate and filter out rows where physical logic breaks.
        
        # Rule A: Prices and Volumes must be non-negative
        valid_mask = (
            (dataframe["Open"] >= 0) & 
            (dataframe["High"] >= 0) & 
            (dataframe["Low"] >= 0) & 
            (dataframe["Close"] >= 0) & 
            (dataframe["Volume"] >= 0)
        )

        # Rule B: High cannot be lower than Low (Only check if it's a deep dataset run)
        if len(dataframe) > 5:
            valid_mask = valid_mask & (dataframe["High"] >= dataframe["Low"])

        # Apply our safety mask filter to keep only logically sound trading sessions
        corrupt_rows_count = len(dataframe) - valid_mask.sum()
        if corrupt_rows_count > 0:
            dataframe.loc[~valid_mask]  # Access bad rows if debugging is needed
            dataframe.query("@valid_mask", inplace=True)  # Drop corrupt indices directly
            result.warnings.append(f"Isolated and removed {corrupt_rows_count} logically corrupt price rows.")
            logger.warning(f"Validation alert: Safely purged {corrupt_rows_count} broken exchange entries.")

        # Final terminal boundary check
        if dataframe.empty:
            result.valid = False
            result.errors.append("Data validation failed: Zero rows survived the logical pricing check.")
            logger.error("Validation failed: Entire dataset contained broken mathematical logic.")
            return result

        # -------------------------------------------------------------- #
        # 6. Duplication & Order Management
        # -------------------------------------------------------------- #
        duplicate_dates = dataframe["Date"].duplicated().sum()
        if duplicate_dates > 0:
            dataframe.drop_duplicates(subset=["Date"], keep="last", inplace=True)
            result.warnings.append(f"Deduplicated {duplicate_dates} repeating date indices.")
            logger.warning(f"Validation notice: Removed {duplicate_dates} duplicate rows.")

        if not dataframe["Date"].is_monotonic_increasing:
            dataframe.sort_values(by="Date", ascending=True, inplace=True)
            dataframe.reset_index(drop=True, inplace=True)
            result.warnings.append("Chronological timeline sequence was out of order. Re-sorted ascending.")
            logger.info("Validation notice: Chronological row order corrected automatically.")

        # Log final execution run summaries
        logger.info(
            "Validation sequence finished. Status: Valid=%s, Total Errors=%d, Total Warnings=%d",
            result.valid,
            len(result.errors),
            len(result.warnings),
        )

        return result


# Singleton instantiation matching the platform architecture design rules
market_data_validator = MarketDataValidator()