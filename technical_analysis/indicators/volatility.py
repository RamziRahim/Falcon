"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : volatility.py
Package     : Technical Analysis / Indicators

Purpose
-------
Calculates volatility and directional strength trends (ATR and ADX).

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
    Calculates ATR volatility and ADX trend strength profiles for Falcon.

    Parameters
    ----------
    dataframe : pd.DataFrame
        The daily raw stock price table.

    Returns
    -------
    pd.DataFrame
        The table with volatility indicator columns added.
    """
    df = dataframe.copy()
    
    high = df["High"].astype("float64")
    low = df["Low"].astype("float64")
    close = df["Close"].astype("float64")

    # 1. Calculate Average True Range (ATR) - vital for position sizing and stops
    df["ATR_14"] = ta.atr(high=high, low=low, close=close, length=14)

    # 2. Calculate Average Directional Index (ADX)
    adx_df = ta.adx(high=high, low=low, close=close, length=14)
    
    if adx_df is not None and not adx_df.empty:
        df["ADX_14"] = adx_df.iloc[:, 0]        # Trend Strength Line
        df["DI_Plus_14"] = adx_df.iloc[:, 1]    # Positive Directional Index (+DI)
        df["DI_Minus_14"] = adx_df.iloc[:, 2]   # Negative Directional Index (-DI)
    else:
        df["ADX_14"] = pd.NA
        df["DI_Plus_14"] = pd.NA
        df["DI_Minus_14"] = pd.NA

    return df