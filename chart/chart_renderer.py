"""
===============================================================================
Falcon AI Swing Trading Platform
Module  : chart_renderer.py
Package : chart

Purpose
-------
Professional TradingView-inspired chart renderer.

Responsibilities
----------------
• Create Plotly figure
• Create chart layout
• Delegate drawing to registered layers
• Apply Falcon theme
• Configure interaction
• Return finished Plotly Figure

The renderer NEVER:
    • Calculates indicators
    • Reads market data
    • Reads configuration files
    • Uses Streamlit

Author : Falcon
===============================================================================
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Imports decoupled cleanly from adjacent packages
from chart.chart_models import ChartRenderOptions
from chart.layer_manager import LayerManager
from chart.layers.base_layer import BaseLayer


class ChartRenderer:
    """
    Falcon Chart Rendering Engine.

    This class assembles the chart by asking the LayerManager
    which layers are enabled and allowing each layer to render
    itself onto the Plotly figure.
    """

    # ------------------------------------------------------------------
    # Falcon Theme Configurations
    # ------------------------------------------------------------------
    PAPER_BACKGROUND = "#0A0F1D"
    PLOT_BACKGROUND = "#0A0F1D"
    GRID_COLOR = "#1F2937"
    FONT_COLOR = "#E5E7EB"
    SPIKE_COLOR = "#64748B"
    WATERMARK_COLOR = "rgba(255,255,255,0.04)"
    LAST_PRICE_COLOR = "#22C55E"

    def __init__(self, layer_manager: LayerManager) -> None:
        """
        Parameters
        ----------
        layer_manager
            Layer manager responsible for all registered chart layers.
        """
        self._layer_manager = layer_manager

    # ==================================================================
    # Public API
    # ==================================================================

    def render(
        self,
        dataframe: pd.DataFrame,
        symbol: str,
        options: ChartRenderOptions,
    ) -> go.Figure:
        """
        Render Falcon chart.
        """
        self._validate_dataframe(dataframe)

        figure = self._create_figure()

        self._render_layers(
            figure=figure,
            dataframe=dataframe,
        )

        self._configure_layout(
            figure=figure,
            dataframe=dataframe,
            symbol=symbol,
            options=options,
        )
        self._configure_interaction(
            figure,
            options,
        )
        self._finalize_figure(
            figure,
        )

        return figure

    # ==================================================================
    # Figure Creation
    # ==================================================================

    def _create_figure(self) -> go.Figure:
        """
        Create Falcon subplot layout.
        """
        return make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.02,
            row_heights=[0.78, 0.22],
            specs=[
                [{"secondary_y": False}],
                [{"secondary_y": False}],
            ],
        )

    # ==================================================================
    # Layer Rendering
    # ==================================================================

    def _render_layers(
        self,
        figure: go.Figure,
        dataframe: pd.DataFrame,
    ) -> None:
        """
        Render enabled layers.
        """
        renderers: Iterable[BaseLayer] = (
            self._layer_manager.get_enabled_renderers()
        )

        for renderer in renderers:
            renderer.draw(
                fig=figure,
                dataframe=dataframe,
            )

    # ==================================================================
    # Validation
    # ==================================================================

    @staticmethod
    def _validate_dataframe(dataframe: pd.DataFrame) -> None:
        """
        Validate required OHLCV columns.
        """
        required = {"Open", "High", "Low", "Close", "Volume"}
        missing = required - set(dataframe.columns)

        if missing:
            raise ValueError(
                f"Missing dataframe columns: {sorted(missing)}"
            )

    # ==================================================================
    # Layout Configuration
    # ==================================================================

    def _configure_layout(
        self,
        figure: go.Figure,
        dataframe: pd.DataFrame,
        symbol: str,
        options: ChartRenderOptions,
    ) -> None:
        """
        Configure TradingView-inspired layout.
        """
        figure.update_layout(
            paper_bgcolor=self.PAPER_BACKGROUND,
            plot_bgcolor=self.PLOT_BACKGROUND,
            template=None,
            hovermode="x unified",
            dragmode="pan",
            autosize=options.responsive,
            height=options.height,
            showlegend=options.show_legend,
            margin=dict(l=15, r=60, t=35, b=20),
            font=dict(
                family="Segoe UI",
                size=12,
                color=self.FONT_COLOR,
            ),
            xaxis_rangeslider_visible=False,
        )

        self._configure_price_axis(figure)
        self._configure_volume_axis(figure)
        self._configure_time_axis(figure, options)
        self._configure_hover()
        self._apply_chart_title(figure, symbol, options)

    def _configure_price_axis(self, figure: go.Figure) -> None:
        figure.update_yaxes(
            row=1,
            col=1,
            side="right",
            showgrid=True,
            gridcolor=self.GRID_COLOR,
            gridwidth=1,
            zeroline=False,
            fixedrange=False,
            ticks="outside",
            showline=False,
            mirror=False,
            title=None,
        )

    def _configure_volume_axis(self, figure: go.Figure) -> None:
        figure.update_yaxes(
            row=2,
            col=1,
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            title=None,
            fixedrange=False,
        )

    def _configure_time_axis(
        self,
        figure: go.Figure,
        options: ChartRenderOptions,
    ) -> None:
        figure.update_xaxes(
            row=1,
            col=1,
            showgrid=True,
            gridcolor=self.GRID_COLOR,
            zeroline=False,
            showline=False,
            ticks="outside",
            showspikes=options.enable_crosshair,
            spikesnap="cursor",
            spikemode="across",
            spikecolor=self.SPIKE_COLOR,
            spikethickness=1,
            rangeslider_visible=options.show_range_slider,
            fixedrange=not options.enable_zoom,
        )

        figure.update_xaxes(
            row=2,
            col=1,
            showgrid=False,
            showspikes=options.enable_crosshair,
            spikecolor=self.SPIKE_COLOR,
            fixedrange=not options.enable_zoom,
        )

    @staticmethod
    def _configure_hover() -> None:
        return

    def _apply_chart_title(
        self,
        figure: go.Figure,
        symbol: str,
        options: ChartRenderOptions,
    ) -> None:
        figure.update_layout(
            title=dict(
                text=(
                    f"<b>{symbol}</b>"
                    f"&nbsp;&nbsp;&nbsp;"
                    f"{options.timeframe.value}"
                ),
                x=0.01,
                y=0.98,
                xanchor="left",
                yanchor="top",
                font=dict(
                    size=18,
                    color=self.FONT_COLOR,
                ),
            )
        )

    # ==================================================================
    # Chart Decoration
    # ==================================================================

    def _decorate_chart(
        self,
        figure: go.Figure,
        dataframe: pd.DataFrame,
        symbol: str,
    ) -> None:
        self._add_watermark(figure, symbol)
        self._add_last_price_line(figure, dataframe)
        self._auto_scale_price_axis(figure, dataframe)

    def _add_watermark(self, figure: go.Figure, symbol: str) -> None:
        figure.add_annotation(
            x=0.5,
            y=0.55,
            xref="paper",
            yref="paper",
            text=symbol,
            showarrow=False,
            opacity=1.0,
            font=dict(
                size=78,
                color=self.WATERMARK_COLOR,
            ),
        )

    def _add_last_price_line(
        self,
        figure: go.Figure,
        dataframe: pd.DataFrame,
    ) -> None:
        last_price = float(dataframe["Close"].iloc[-1])

        figure.add_hline(
            y=last_price,
            row=1,
            col=1,
            line_width=1,
            line_dash="dot",
            line_color=self.LAST_PRICE_COLOR,
            opacity=0.70,
        )

        figure.add_annotation(
            x=1.0,
            y=last_price,
            xref="paper",
            yref="y",
            xanchor="left",
            showarrow=False,
            xshift=10,
            text=f"{last_price:,.2f}",
            bgcolor=self.LAST_PRICE_COLOR,
            bordercolor=self.LAST_PRICE_COLOR,
            borderwidth=1,
            font=dict(
                size=11,
                color="white",
            ),
        )

    @staticmethod
    def _auto_scale_price_axis(
        figure: go.Figure,
        dataframe: pd.DataFrame,
    ) -> None:
        highest = float(dataframe["High"].max())
        lowest = float(dataframe["Low"].min())
        padding = (highest - lowest) * 0.05

        figure.update_yaxes(
            row=1,
            col=1,
            range=[
                lowest - padding,
                highest + padding,
            ],
        )

    @staticmethod
    def _latest_close(dataframe: pd.DataFrame) -> float:
        return float(dataframe["Close"].iloc[-1])

    @staticmethod
    def _price_change(dataframe: pd.DataFrame) -> tuple[float, float]:
        if len(dataframe) < 2:
            return 0.0, 0.0

        previous = float(dataframe["Close"].iloc[-2])
        current = float(dataframe["Close"].iloc[-1])
        change = current - previous
        percentage = (change / previous) * 100

        return (change, percentage)

    # ==================================================================
    # Export & Figure Finalization
    # ==================================================================

    def _finalize_figure(self, figure: go.Figure) -> None:
        figure.update_layout(
            hoverlabel=dict(
                bgcolor="#111827",
                bordercolor="#374151",
                font=dict(
                    color="#F9FAFB",
                    size=12,
                ),
            ),
            modebar=dict(
                orientation="h",
            ),
        )

    def _configure_interaction(
        self,
        figure: go.Figure,
        options: ChartRenderOptions,
    ) -> None:
        if not options.enable_pan:
            figure.update_layout(
                dragmode=False,
            )

    @staticmethod
    def build_config() -> dict:
        return {
            "displaylogo": False,
            "responsive": True,
            "scrollZoom": True,
            "doubleClick": "reset",
            "showAxisDragHandles": False,
            "modeBarButtonsToRemove": [
                "lasso2d",
                "select2d",
                "autoScale2d",
                "toggleSpikelines",
            ],
        }

    @staticmethod
    def empty_figure() -> go.Figure:
        figure = go.Figure()
        figure.update_layout(
            paper_bgcolor="#0A0F1D",
            plot_bgcolor="#0A0F1D",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            annotations=[
                dict(
                    text="Select a stock to display the chart",
                    showarrow=False,
                    font=dict(
                        size=18,
                        color="#6B7280",
                    ),
                    x=0.5,
                    y=0.5,
                    xref="paper",
                    yref="paper",
                )
            ],
        )
        return figure

    @staticmethod
    def version() -> str:
        return "1.0.0"