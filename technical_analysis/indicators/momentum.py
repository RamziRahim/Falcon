"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : momentum.py
Package     : Technical Analysis / Indicators

Purpose
-------
Calculates momentum oscillators (RSI and MACD).

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
    Calculates RSI and MACD oscillators for Falcon.

    Parameters
    ----------
    dataframe : pd.DataFrame
        The daily raw stock price table.

    Returns
    -------
    pd.DataFrame
        The table with momentum indicator columns added.
    """
    df = dataframe.copy()
    close_series = df["Close"].astype("float64")

    # 1. Calculate Relative Strength Index (RSI)
    df["RSI_14"] = ta.rsi(close_series, length=14)

    # 2. Calculate Moving Average Convergence Divergence (MACD)
    macd_df = ta.macd(close_series, fast=12, slow=26, signal=9)
    
    if macd_df is not None and not macd_df.empty:
        # Map pandas-ta output arrays to friendly, standard Falcon headers
        df["MACD_Line"] = macd_df.iloc[:, 0]    # MACD Line
        df["MACD_Signal"] = macd_df.iloc[:, 1]  # Signal Line
        df["MACD_Hist"] = macd_df.iloc[:, 2]    # Histogram Line
    else:
        # Fallback placeholders if dataset is too short to calculate MACD
        df["MACD_Line"] = pd.NA
        df["MACD_Signal"] = pd.NA
        df["MACD_Hist"] = pd.NA

    return df