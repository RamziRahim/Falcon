"""
===============================================================================
Falcon AI Swing Trading Platform
Module  : moving_average_layer.py
Package : chart.layers

Purpose
-------
Render moving average overlays on the candlestick chart.

Responsibilities
----------------
• Render any moving average column
• Support SMA and EMA
• Configurable colour, width and style
• No indicator calculations

Indicator values must already exist in the dataframe.
===============================================================================
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from chart.chart_models import LayerType
from chart.layers.base_layer import BaseLayer


class MovingAverageLayer(BaseLayer):
    """
    Generic Moving Average Layer.

    One class supports all moving averages.

    Examples
    --------

    MovingAverageLayer(
        LayerType.MA20,
        "MA20",
        "#3B82F6"
    )

    MovingAverageLayer(
        LayerType.MA50,
        "MA50",
        "#F59E0B"
    )
    """

    def __init__(
        self,
        layer_type: LayerType,
        dataframe_column: str,
        colour: str,
        width: int = 2,
        dash: str = "solid",
    ) -> None:

        super().__init__(layer_type)

        self.column = dataframe_column
        self.colour = colour
        self.width = width
        self.dash = dash

    def draw(
        self,
        fig: go.Figure,
        dataframe: pd.DataFrame,
        row: int = 1,
        col: int = 1,
    ) -> None:
        """
        Render moving average.
        """

        self.validate_columns(
            dataframe,
            [self.column],
        )

        fig.add_trace(

            go.Scatter(

                x=dataframe.index,

                y=dataframe[self.column],

                mode="lines",

                name=self.column,

                line=dict(

                    color=self.colour,

                    width=self.width,

                    dash=self.dash,

                ),

                hovertemplate=(
                    "<b>%{x}</b><br>"
                    f"{self.column}: "
                    "%{y:.2f}"
                    "<extra></extra>"
                ),

            ),

            row=row,
            col=col,

        )