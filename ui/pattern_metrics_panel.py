"""
===============================================================================
Falcon AI Swing Trading Platform
Module  : pattern_metrics_panel.py
Package : ui

Purpose
-------
Populates the space under the chart with a high-density, structured row 
of quantitative pattern recognition metrics.
===============================================================================
"""

import streamlit as st
import pandas as pd


class PatternMetricsPanel:
    @staticmethod
    def render(full_history_df: pd.DataFrame):
        """
        Renders the pattern metric card blocks cleanly below the chart view.
        """
        if full_history_df.empty:
            return

        # Fetch the absolute latest calculation vector slice
        latest = full_history_df.iloc[-1]

        # Extract real structural pattern states
        trend_state = str(latest.get("Trend_State", "UNKNOWN"))
        vcp_score = f"{latest.get('VCP_Score', 0.0):.1f}%"
        is_breakout = "ACTIVE BREAKOUT" if latest.get("Is_VCP_Breakout", False) else "CONSOLIDATING"
        is_sweep = "LIQUIDITY SWEEP" if latest.get("Is_Liquidity_Sweep", False) else "NORMAL FLUIDITY"
        
        # Calculate moving average alignments safely
        c_price = latest.get("Close", 0.0)
        ma20 = latest.get("MA20", latest.get("EMA_20", 0.0))
        ma50 = latest.get("MA50", latest.get("EMA_50", 0.0))
        
        ma_alignment = "BULLISH ALIGNED" if (c_price > ma20 > ma50) else "MIXED TRACTION"

        # Construct high-density display grids
        st.markdown("<h4 style='margin: 15px 0 5px 0; font-size:14px; color:#9CA3AF; text-transform:uppercase;'>Pattern Engine Execution Metrics</h4>", unsafe_allow_html=True)
        
        cols = st.columns(5)
        
        with cols[0]:
            st.metric(label="Trend Engine Matrix", value=trend_state)
        with cols[1]:
            st.metric(label="VCP Volatility Score", value=vcp_score)
        with cols[2]:
            st.metric(label="Structural Breakout", value=is_breakout)
        with cols[3]:
            st.metric(label="Liquidity Tractions", value=is_sweep)
        with cols[4]:
            st.metric(label="Moving Average Context", value=ma_alignment)
            
        st.markdown("<hr style='border-color: #1F2937; margin-top:10px; margin-bottom:10px;'>", unsafe_allow_html=True)