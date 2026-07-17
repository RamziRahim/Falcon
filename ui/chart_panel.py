"""
===============================================================================
Falcon AI Swing Trading Platform
Module  : chart_panel.py
Package : ui

Purpose
-------
Renders the chart framework layout container, manages interactive overlay toggles,
sets up registries, and delegates execution to the core ChartRenderer engine.
===============================================================================
"""

import streamlit as st
import pandas as pd

# Core Engine Imports directly from your chart package
from chart.chart_models import ChartRenderOptions, LayerType, TimeFrame, ChartMode
from chart.layer_manager import LayerManager
from chart.chart_renderer import ChartRenderer

# Concrete Layer Imports
from chart.layers.candlestick_layer import CandlestickLayer
from chart.layers.volume_layer import VolumeLayer
from chart.layers.moving_average_layer import MovingAverageLayer


class ChartPanel:
    @staticmethod
    def render(active_sym: str, full_history_df: pd.DataFrame):
        """
        Main interface entry point. Renders layer toggles and draws the active chart.
        """
        # ─── STEP 1: PREPARE TIME-SERIES DATAFRAME INDEX FOR RENDER LAYERS ───
        # Your layers use `dataframe.index` as X-axis coordinates.
        render_df = full_history_df.copy()
        if "Date" in render_df.columns:
            render_df["Date"] = pd.to_datetime(render_df["Date"])
            render_df.set_index("Date", inplace=True)
        elif not isinstance(render_df.index, pd.DatetimeIndex):
            render_df.index = pd.to_datetime(render_df.index)

        # Ensure column names match what the MovingAverageLayer expects
        for val in [20, 50, 200]:
            if f"EMA_{val}" in render_df.columns and f"MA{val}" not in render_df.columns:
                render_df[f"MA{val}"] = render_df[f"EMA_{val}"]

        # ─── STEP 2: INITIALIZE LAYER MANAGER & REGISTER RENDERERS ───
        manager = LayerManager()
        
        # Register concrete layers with the manager registry
        manager.register_renderer(LayerType.CANDLESTICK, CandlestickLayer())
        manager.register_renderer(LayerType.VOLUME, VolumeLayer())
        manager.register_renderer(
            LayerType.MA20, 
            MovingAverageLayer(LayerType.MA20, "MA20", colour="#EAB308", width=2)
        )
        manager.register_renderer(
            LayerType.MA50, 
            MovingAverageLayer(LayerType.MA50, "MA50", colour="#3B82F6", width=2)
        )
        manager.register_renderer(
            LayerType.MA200, 
            MovingAverageLayer(LayerType.MA200, "MA200", colour="#EF4444", width=2)
        )

        # ─── STEP 3: RENDER THE DYNAMIC CHECKBOX TOGGLE RIBBON ───
        st.markdown("##### Indicator Overlays")
        cb_cols = st.columns(3)
        with cb_cols[0]:
            show_ma20 = st.checkbox("MA 20 (Yellow)", value=True, key=f"{active_sym}_opt_ma_20")
        with cb_cols[1]:
            show_ma50 = st.checkbox("MA 50 (Blue)", value=True, key=f"{active_sym}_opt_ma_50")
        with cb_cols[2]:
            show_ma200 = st.checkbox("MA 200 (Red)", value=False, key=f"{active_sym}_opt_ma_200")

        # Sync checkboxes to LayerManager state
        if show_ma20:
            manager.enable(LayerType.MA20)
        else:
            manager.disable(LayerType.MA20)

        if show_ma50:
            manager.enable(LayerType.MA50)
        else:
            manager.disable(LayerType.MA50)

        if show_ma200:
            manager.enable(LayerType.MA200)
        else:
            manager.disable(LayerType.MA200)

        # ─── STEP 4: ASSEMBLE OPTIONS AND TRIGGER THE CORE RENDERER ───
        renderer = ChartRenderer(layer_manager=manager)
        options = ChartRenderOptions(
            mode=ChartMode.DASHBOARD,
            timeframe=TimeFrame.DAILY,
            height=440,
            show_legend=False,
            enable_crosshair=True
        )

        fig = renderer.render(
            dataframe=render_df,
            symbol=active_sym,
            options=options
        )

        # ─── STEP 5: DISPLAY PLOTLY INSIDE STREAMLIT ───
        st.plotly_chart(
            fig, 
            use_container_width=True, 
            config=ChartRenderer.build_config()
        )