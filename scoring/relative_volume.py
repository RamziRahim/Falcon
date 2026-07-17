"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : relative_volume.py
Package     : Scoring

Purpose
-------
Calculates Relative Volume (RVOL) — today's volume against its trailing
average, excluding today from the average itself.

===============================================================================
"""

from __future__ import annotations

import pandas as pd

from config import VOLUME_COLUMN


def calculate(dataframe: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    """
    Calculates Relative Volume (RVOL) against the trailing average volume.

    Parameters
    ----------
    dataframe : pd.DataFrame
        The daily stock price table.
    lookback : int
        Rolling window size for the average volume baseline.

    Returns
    -------
    pd.DataFrame
        The table with Avg_Volume_20 and Rel_Vol columns added.
    """

    df = dataframe.copy()

    # Shifted by 1 so today's volume never dilutes its own baseline
    df[f"Avg_Volume_{lookback}"] = (
        df[VOLUME_COLUMN].rolling(lookback).mean().shift(1)
    )

    df["Rel_Vol"] = df[VOLUME_COLUMN] / df[f"Avg_Volume_{lookback}"]

    return df
