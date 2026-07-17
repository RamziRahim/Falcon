"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : bands.py
Package     : Technical Analysis / Indicators

Purpose
-------
Calculates structural volatility channels (Bollinger Bands).

===============================================================================
"""

from __future__ import annotations
import pandas as pd

try:
    import pandas_ta as ta
except ImportError as ex:
    raise ImportError("pandas-ta is required. Run: pip install pandas-ta") from ex


def calculate(dataframe: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates Bollinger Bands parameters to spot volatility squeezes.

    Parameters
    ----------
    dataframe : pd.DataFrame
        The daily stock price table.

    Returns
    -------
    pd.DataFrame
        The table with upper, middle, and lower bands added.
    """
    df = dataframe.copy()
    
    # Calculate Bollinger Bands using standard 20-period lookback and 2 standard deviations
    bbands_df = ta.bbands(close=df["Close"], length=20, std=2)
    
    if bbands_df is not None and not bbands_df.empty:
        # Map the default output index layout from pandas_ta to clean, intuitive names
        df["BB_Upper"] = bbands_df.iloc[:, 0]   # Upper Band boundary
        df["BB_Middle"] = bbands_df.iloc[:, 1]  # Simple Moving Average baseline
        df["BB_Lower"] = bbands_df.iloc[:, 2]   # Lower Band boundary
    else:
        df["BB_Upper"] = pd.NA
        df["BB_Middle"] = pd.NA
        df["BB_Lower"] = pd.NA

    return df