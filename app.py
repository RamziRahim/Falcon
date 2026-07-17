"""
===============================================================================
Falcon AI Swing Trading Platform
Module  : app.py
Package : root

Purpose
-------
Main application entry point. Orchestrates the high-density modular workspace
layout panels and sequences data flows exactly as mapped in the blueprint.
===============================================================================
"""

import os
import sys
import glob
from datetime import datetime
import streamlit as st
import pandas as pd

# ─── ROBUST SYS PATH INJECTION FOR BLUEPRINT IMPORTS ──────────────────────────
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# UI Module imports directly matching your folder structure
from ui.sidebar import render as render_sidebar
from ui.header import render as render_header, get_market_status
from ui.summary_cards import render as render_summary_cards, DashboardStats
from ui.chart_panel import ChartPanel
from ui.candidate_grid import render as render_candidate_grid
from ui.sector_ranking_panel import SectorRankingPanel

# Scoring Engine (RS Rating / RS vs Nifty / Relative Volume / Sector)
from scoring.scoring_engine import scoring_engine

# Fundamental Analysis (ROCE / Revenue YoY / Debt-to-Equity, cached)
from fundamental_analysis.fundamental_cache import get_fundamentals

# Internal-sentinel-to-display mapping (e.g. "DATA_GAP" -> "N/A")
from common.utils import sentinel_to_display

# Candidate Table Assembly (Phase 4 pattern data -> display-ready grid rows)
from technical_analysis.candidate_table_builder import build_candidate_table

# ─── MASTER WINDOW CONFIGURATION ──────────────────────────────────────────────
st.set_page_config(
    page_title="Falcon Workstation",
    page_icon="🦅",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Premium dark theme styling rules
st.markdown("""
<style>
    body, .main, .block-container { background-color: #0A0F1D !important; color: #E2E8F0; padding-top: 1.5rem !important; }
    [data-testid="stSidebar"] { background-color: #050810 !important; }
    .panel-box { background-color: #111827; border: 1px solid #1F2937; padding: 20px; border-radius: 12px; min-height: 480px; }
    .panel-box-ai { background-color: #111827; border-left: 3px solid #10B981; padding: 20px; border-radius: 12px; min-height: 480px; }
    .badge { padding: 4px 12px; border-radius: 6px; font-weight: 700; font-size: 12px; text-transform: uppercase; display: inline-block; }
    .badge-green { background-color: rgba(16, 185, 129, 0.15); color: #10B981; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-blue { background-color: rgba(59, 130, 246, 0.15); color: #3B82F6; border: 1px solid rgba(59, 130, 246, 0.3); }
    .info-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #1F2937; }
    .info-row:last-child { border-bottom: none; }
    .info-label { color: #9CA3AF; font-size: 14px; }
    .info-val { color: #FFFFFF; font-size: 14px; font-weight: 600; }
    .section-header { font-size: 14px; font-weight: 700; color: #9CA3AF; text-transform: uppercase; letter-spacing: 0.5px; margin: 18px 0 8px 0; }
    .txt-green { color: #10B981; }
</style>
""", unsafe_allow_html=True)

# Master session state tracking keys matching blueprint Section 8
if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = None
if "screener_records" not in st.session_state:
    st.session_state.screener_records = pd.DataFrame()
if "ai_synthesis_runs" not in st.session_state:
    st.session_state.ai_synthesis_runs = {}
if "scan_time_elapsed" not in st.session_state:
    st.session_state.scan_time_elapsed = 0.00

# 1. Render Left Sidebar Navigation (Section 4)
render_sidebar()

# 2. Render Top Control Header Ribbon (Section 4)
is_new_scan_triggered = render_header()

# Execution pipeline chain triggered dynamically from your explicit button input
if is_new_scan_triggered:
    with st.spinner("Invoking Falcon Engine Pipeline Chain..."):
        start_time = datetime.now()
        
        # ─── RUN CANDIDATE GENERATION ENGINE ────────────────────────────────
        from candidate_generation.candidate_generator import generate_candidates
        master_candidates_df = generate_candidates()
        
        if not master_candidates_df.empty and "Symbol" in master_candidates_df.columns:
            # Ensure proper suffix handling for local listings
            ticker_universe = [
                f"{sym}.NS" if not str(sym).endswith(".NS") else str(sym) 
                for sym in master_candidates_df["Symbol"].tolist()
            ]
            
            # (Your downstream Phase 3, 4, 5 and 6 pipeline triggers integrate here)
            records_df = build_candidate_table(ticker_universe)

            # ─── SCORING ENGINE: RS RATING / RS vs NIFTY / REL VOL / SECTOR ─────
            if not records_df.empty:
                scored_df = scoring_engine.score_universe(symbols=records_df["Symbol"].tolist())
                if not scored_df.empty:
                    records_df = records_df.merge(scored_df, on="Symbol", how="left")

            st.session_state.screener_records = records_df
            
        st.session_state.scan_time_elapsed = (datetime.now() - start_time).total_seconds()
        if not st.session_state.screener_records.empty:
            st.session_state.selected_symbol = st.session_state.screener_records["Symbol"].iloc[0]
        st.rerun()

# 3. Render Dashboard KPI Cards (Section 4)
active_kpis = DashboardStats(
    candidates=len(st.session_state.screener_records),
    breakouts=len(st.session_state.screener_records[st.session_state.screener_records["Status"] == "Breakout"]) if not st.session_state.screener_records.empty else 0,
    pullbacks=len(st.session_state.screener_records[st.session_state.screener_records["Status"] == "Pullback"]) if not st.session_state.screener_records.empty else 0,
    strong_trends=len(st.session_state.screener_records[st.session_state.screener_records["Status"] == "Strong Trend"]) if not st.session_state.screener_records.empty else 0,
    market_status=get_market_status(),
    scan_duration=st.session_state.scan_time_elapsed
)
render_summary_cards(active_kpis)

# 4. Main Workspace Split Panel Setup (65% Left vs 35% Right)
if not st.session_state.screener_records.empty:
    active_sym = st.session_state.selected_symbol or st.session_state.screener_records["Symbol"].iloc[0]
    row_data = st.session_state.screener_records[st.session_state.screener_records["Symbol"] == active_sym].iloc[0]
    
    left_pane, right_pane = st.columns([6.5, 3.5])
    
    # --- LEFT WORKSPACE: CHART PANEL PANEL ---
    with left_pane:
        st.markdown(f"### Chart Framework: {active_sym}")
        
        source_file_path = f"data/patterns/{active_sym}.parquet"
        if os.path.exists(source_file_path):
            full_history_df = pd.read_parquet(source_file_path)
            full_history_df["Date"] = pd.to_datetime(full_history_df.get("Date", full_history_df.index))
        else:
            st.warning(f"⚠️ MOCK CHART — no real price history found for {active_sym} yet. "
                       f"Showing a synthetic placeholder series, not real market data.")
            dates = pd.date_range(end=datetime.now(), periods=100)
            full_history_df = pd.DataFrame({
                "Date": dates, "Open": [1000 + i*15 for i in range(100)], "High": [1050 + i*15 for i in range(100)],
                "Low": [980 + i*15 for i in range(100)], "Close": [1020 + i*15 for i in range(100)], "Volume": [150000]*100,
                "EMA_20": [990 + i*15 for i in range(100)], "EMA_50": [950 + i*15 for i in range(100)], "EMA_200": [900 + i*15 for i in range(100)], "Trend_State": ["UPTREND"]*100
            })

        ChartPanel.render(active_sym, full_history_df)

    # --- RIGHT WORKSPACE: TECHNICAL PANEL (TOP) & AI PANEL (BOTTOM) ---
    with right_pane:
        last_candle_row = full_history_df.iloc[-1]
        trend_label = "STRONG UP TREND" if last_candle_row.get("Trend_State", "UNKNOWN") == "UPTREND" else "DOWN TREND"
        vcp_score_str = str(row_data["VCP_Score"])
        # Detail panel gets real, cached fundamentals for the selected symbol only
        # (table-wide fundamentals are a fast-follow — see the candidate loop above).
        active_fundamentals = get_fundamentals(active_sym)
        roce_str = sentinel_to_display(active_fundamentals.get("roce", "N/A"))
        yoy_rev_str = sentinel_to_display(active_fundamentals.get("revenue_yoy_quarterly_growth", "N/A"))
        de_str = sentinel_to_display(active_fundamentals.get("debt_to_equity", "N/A"))
        status_str = str(row_data["Status"])
        
        # HTML strings are shifted completely to the left margin to bypass Markdown's 4-space indent rules
        st.markdown(f"""
<div class="panel-box">
<h4 style="margin-top:0; font-size:15px; color:#FFFFFF;">Technical Analysis Profile: {active_sym}</h4>
<div class="section-header">Trend Matrix</div>
<div class="info-row"><span class="info-label">Trend Classification</span><span class="badge badge-green">{trend_label}</span></div>
<div class="section-header">Volatility Models</div>
<div class="info-row"><span class="info-label">VCP Pattern Score</span><span class="badge badge-blue">{vcp_score_str}%</span></div>
<div class="info-row"><span class="info-label">Setup Trigger Vector</span><span class="info-val">{status_str}</span></div>
<div class="section-header">Fundamental Metrics Layer</div>
<div class="info-row"><span class="info-label">Revenue Growth YoY</span><span class="txt-green" style="font-size:14px; font-weight:600;">{yoy_rev_str}</span></div>
<div class="info-row"><span class="info-label">ROCE / D/E %</span><span class="info-val">{roce_str} / {de_str}</span></div>
</div>
""", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # AI Control Panel Module
        st.markdown('<div class="panel-box-ai">', unsafe_allow_html=True)
        st.markdown("<h4 style='margin-top:0; font-size:15px; color:#FFFFFF;'>Falcon AI Engine Guidance</h4>", unsafe_allow_html=True)
        
        if active_sym not in st.session_state.ai_synthesis_runs:
            st.warning("AI Generation awaiting explicit request link.")
            if st.button("🧠 Generate AI Plan", use_container_width=True):
                # TODO(cleanup 2026-07-15): This does NOT call ai/synthesis_engine.py or the
                # Gemini provider at all. Every number below is derived from a fixed multiplier
                # on Price (e.g. SL = Price * 0.94), not from any AI inference. The score "88"
                # and R:R "1 : 2.6" are hardcoded constants. Wire this button to
                # ai.synthesis_engine.AISynthesisEngine before treating this as real AI output.
                st.session_state.ai_synthesis_runs[active_sym] = {
                    "score": "88", "zone": f"₹{row_data['Price']} — ₹{round(row_data['Price']*1.01, 2)}",
                    "targets": f"₹{round(row_data['Price']*1.08, 2)} / ₹{round(row_data['Price']*1.15, 2)}",
                    "sl": f"₹{round(row_data['Price']*0.94, 2)}", "rr": "1 : 2.6",
                    "is_simulated": True,
                }
                st.rerun()
        else:
            ai = st.session_state.ai_synthesis_runs[active_sym]
            ai_score_val = str(ai["score"])
            ai_zone_val = str(ai["zone"])
            ai_targets_val = str(ai["targets"])
            ai_sl_val = str(ai["sl"])
            ai_rr_val = str(ai["rr"])
            
            if ai.get("is_simulated"):
                st.error("⚠️ SIMULATED — this plan is calculated from a fixed price multiplier, "
                         "not from the Falcon AI / Gemini engine. Do not trade on this yet.")
            
            st.markdown(f"""
<div style="display:flex; align-items:baseline; margin-bottom:10px;">
<span style="font-size:32px; font-weight:800; color:#10B981; margin-right:5px;">{ai_score_val}</span>
<span style="color:#6B7280; font-size:13px; margin-right:15px;">/ 100</span>
<span class="badge badge-green">Confluence Mapped</span>
</div>
<div class="info-row"><span class="info-label">Accumulation Buy Zone</span><span class="info-val" style="color:#10B981;">{ai_zone_val}</span></div>
<div class="info-row"><span class="info-label">Targets (T1 / T2)</span><span class="info-val">{ai_targets_val}</span></div>
<div class="info-row"><span class="info-label">Stop Loss Invalidation</span><span class="info-val" style="color:#EF4444;"><b>{ai_sl_val}</b></span></div>
<div class="info-row"><span class="info-label">Risk Reward Ratio</span><span class="info-val">{ai_rr_val}</span></div>
""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 5. Render Bottom Watchlist Candidate Grid Component (Section 4)
    selected_table_row = render_candidate_grid(st.session_state.screener_records)
    if selected_table_row and selected_table_row != st.session_state.selected_symbol:
        st.session_state.selected_symbol = selected_table_row
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # 6. Render Key Insights: Sector RS Ranking Panel
    st.markdown('<div class="panel-box">', unsafe_allow_html=True)
    SectorRankingPanel.render(st.session_state.screener_records)
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.markdown("""
<div style="background-color:#111827; border:1px dashed #1F2937; padding:40px; border-radius:12px; text-align:center;">
<h4 style="color:#9CA3AF; margin:0;">Falcon Swing Workstation Standby</h4>
<p style="color:#6B7280; font-size:14px; margin:8px 0 0 0;">Select '➕ New Scan' inside the control header ribbon to activate your screening pipelines.</p>
</div>
""", unsafe_allow_html=True)