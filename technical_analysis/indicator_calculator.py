"""
===============================================================================
Module      : indicator_calculator.py
Package     : Technical Analysis

Purpose     : Routes market data through all active indicator calculation tasks.
===============================================================================
"""
from __future__ import annotations
import pandas as pd

# Import your entire indicator toolkit smoothly
from technical_analysis.indicators.moving_average import calculate as calculate_ma
from technical_analysis.indicators.momentum import calculate as calculate_momentum
from technical_analysis.indicators.volatility import calculate as calculate_volatility
from technical_analysis.indicators.volume import calculate as calculate_volume
from technical_analysis.indicators.bands import calculate as calculate_bands


class IndicatorCalculator:
    """
    Passes market datasets through our functional technical indicator stack.
    """

    def calculate(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        df = dataframe.copy()

        # The complete algorithmic assembly sequence
        indicator_pipeline = [
            calculate_ma,
            calculate_momentum,
            calculate_volatility,
            calculate_volume,  # Computes OBV institutional tracking numbers
            calculate_bands    # Computes Bollinger Volatility Channel models
        ]

        for run_calculation in indicator_pipeline:
            df = run_calculation(df)

        return df

indicator_calculator = IndicatorCalculator()   