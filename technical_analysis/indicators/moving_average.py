"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : moving_average.py
Package     : Technical Analysis / Indicators

Purpose
-------
Calculates Simple (SMA) and Exponential (EMA) Moving Averages.

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
    Calculates various SMA and EMA trend tracking lines for Falcon.

    Parameters
    ----------
    dataframe : pd.DataFrame
        The daily raw stock price table.

    Returns
    -------
    pd.DataFrame
        The table with trend indicator columns added.
    """
    df = dataframe.copy()
    close_series = df["Close"].astype("float64")

    # Calculate Simple Moving Averages (SMA)
    df["SMA_20"] = ta.sma(close_series, length=20)   # ◀── Fixed name to SMA_20 here!
    df["SMA_50"] = ta.sma(close_series, length=50)
    df["SMA_150"] = ta.sma(close_series, length=150)
    df["SMA_200"] = ta.sma(close_series, length=200)  # ◀── Naturally returns NaN if data < 200 rows!

    # Calculate Exponential Moving Averages (EMA)
    df["EMA_20"] = ta.ema(close_series, length=20)
    df["EMA_50"] = ta.ema(close_series, length=50)
    df["EMA_150"] = ta.ema(close_series, length=150)
    df["EMA_200"] = ta.ema(close_series, length=200)  # ◀── Naturally returns NaN if data < 200 rows!

    return df