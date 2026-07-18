"""
===============================================================================
Falcon AI Swing Trading Platform
Module  : candlestick_layer.py
Package : chart.layers

Purpose
-------
Render the candlestick layer.

Responsibilities
----------------
• Draw OHLC candlesticks
• Configure hover information
• Apply Falcon colour scheme

This layer does not create the Plotly figure.
It only adds candlesticks to an existing figure.
===============================================================================
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

# Clean architectural imports matching parent packages
from chart.chart_models import LayerType
from chart.layers.base_layer import BaseLayer


class CandlestickLayer(BaseLayer):
    """
    Candlestick rendering layer.
    """

    def __init__(self):
        super().__init__(LayerType.CANDLESTICK)

    # Falcon Theme Colours
    INCREASING = "#22C55E"
    DECREASING = "#EF4444"

    WICK_UP = "#22C55E"
    WICK_DOWN = "#EF4444"

    def draw(
        self,
        fig: go.Figure,
        dataframe: pd.DataFrame,
        row: int = 1,
        col: int = 1,
    ) -> None:
        """
        Add candlesticks to the supplied figure.

        Parameters
        ----------
        fig
            Plotly figure.

        dataframe
            OHLCV dataframe.

        row
            Target subplot row.

        col
            Target subplot column.
        """
        self.validate_columns(
            dataframe,
            [
                 "Open",
                "High",
                 "Low",
                "Close",
            ],     
        )

        has_volume = "Volume" in dataframe.columns

        hovertemplate = (
            "<b>%{x}</b><br>"
            "Open : %{open:.2f}<br>"
            "High : %{high:.2f}<br>"
            "Low : %{low:.2f}<br>"
            "Close : %{close:.2f}"
        )
        if has_volume:
            hovertemplate += "<br>Volume : %{customdata:,.0f}"
        hovertemplate += "<extra></extra>"

        fig.add_trace(
            go.Candlestick(
                x=dataframe.index,
                open=dataframe["Open"],
                high=dataframe["High"],
                low=dataframe["Low"],
                close=dataframe["Close"],
                name="Price",
                customdata=dataframe["Volume"] if has_volume else None,
                increasing=dict(
                    fillcolor=self.INCREASING,
                    line=dict(
                        color=self.WICK_UP,
                        width=1,
                    ),
                ),
                decreasing=dict(
                    fillcolor=self.DECREASING,
                    line=dict(
                        color=self.WICK_DOWN,
                        width=1,
                    ),
                ),
                hovertemplate=hovertemplate,
            ),
            row=row,
            col=col,
        )

    @staticmethod
    def _validate_dataframe(
        dataframe: pd.DataFrame,
    ) -> None:
        """
        Validate required OHLC columns.
        """
        required = {
            "Open",
            "High",
            "Low",
            "Close",
        }

        missing = required - set(dataframe.columns)

        if missing:
            raise ValueError(
                f"Missing OHLC columns: {sorted(missing)}"
            )