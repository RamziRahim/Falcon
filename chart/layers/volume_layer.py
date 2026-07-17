"""
===============================================================================
Falcon AI Swing Trading Platform
Module  : volume_layer.py
Package : chart.layers

Purpose
-------
Render the trading volume layer.

Responsibilities
----------------
• Draw volume bars
• Colour bars based on candle direction
• Support secondary subplot

This layer contains no layout or business logic.
===============================================================================
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from chart.chart_models import LayerType
from chart.layers.base_layer import BaseLayer


class VolumeLayer(BaseLayer):
    """
    Trading volume rendering layer.
    """

    UP_COLOR = "#22C55E"
    DOWN_COLOR = "#EF4444"

    BAR_OPACITY = 0.70

    def __init__(self):

        super().__init__(LayerType.VOLUME)

    def draw(
        self,
        fig: go.Figure,
        dataframe: pd.DataFrame,
        row: int = 2,
        col: int = 1,
    ) -> None:
        """
        Draw volume bars.

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
                "Close",
                "Volume",
            ],
        )

        colors = self._bar_colors(dataframe)

        fig.add_trace(

            go.Bar(

                x=dataframe.index,

                y=dataframe["Volume"],

                name="Volume",

                marker=dict(
                    color=colors,
                ),

                opacity=self.BAR_OPACITY,

                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Volume : %{y:,.0f}"
                    "<extra></extra>"
                ),

            ),

            row=row,
            col=col,

        )

    def _bar_colors(
        self,
        dataframe: pd.DataFrame,
    ) -> list[str]:
        """
        Generate candle-aligned colours.
        """

        return [

            self.UP_COLOR
            if close >= open_
            else self.DOWN_COLOR

            for open_, close in zip(
                dataframe["Open"],
                dataframe["Close"],
            )

        ]