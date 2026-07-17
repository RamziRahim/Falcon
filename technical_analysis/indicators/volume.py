"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : volume.py
Package     : Technical Analysis / Indicators

Purpose
-------
Calculates volume confirmation metrics (On-Balance Volume).

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
    Calculates On-Balance Volume (OBV) trend confirmation.

    Parameters
    ----------
    dataframe : pd.DataFrame
        The daily stock price table.

    Returns
    -------
    pd.DataFrame
        The table with the OBV tracking column added.
    """
    df = dataframe.copy()
    
    # Calculate running institutional volume flow
    df["OBV"] = ta.obv(close=df["Close"], volume=df["Volume"])

    return df