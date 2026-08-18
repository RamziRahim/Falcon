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

# Several engines (indicator_engine.py, pattern_engine.py) print Unicode
# console-dashboard output (arrows, emoji) meant for direct CLI runs. On
# Windows, Streamlit's process stdout defaults to the system codepage
# (cp1252), not UTF-8 -- those prints crash the whole app the moment New
# Scan actually invokes those engines. Reconfigure once, here, at the real
# process entry point, rather than touching every engine's print calls.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ─── ROBUST SYS PATH INJECTION FOR BLUEPRINT IMPORTS ──────────────────────────
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# UI Module imports directly matching your folder structure
from ui.sidebar import render as render_sidebar
from ui.header import IST, compute_category_breakdown, render as render_header
import ui.dashboard as dashboard

# New Scan pipeline orchestration (Phase 3 data collection -> Phase 4 -> Phase 5)
from services.scan_pipeline_service import run_new_scan_pipeline
from ui.scan_warnings import render as render_scan_warnings

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
    [data-testid="stMetricLabel"] { color: #9CA3AF !important; }
    [data-testid="stMetricValue"] { color: #FFFFFF !important; font-weight: 600 !important; }
    [data-testid="stMetricDelta"] { color: #10B981 !important; }
</style>
""", unsafe_allow_html=True)

# Master session state -- selected_symbol/ai_synthesis_runs/scan_time_elapsed
# were the OLD Streamlit-native UI's own selection/AI-panel/KPI-card state;
# the dashboard rebuild's interactivity (candidate selection, tab
# switching, chart range) lives client-side inside the embedded component
# instead (ui/dashboard.py), and the AI panel is disabled -- neither is
# read anywhere anymore, so removed rather than kept as unused state.
if "screener_records" not in st.session_state:
    st.session_state.screener_records = pd.DataFrame()
# Both None until the first scan ever completes -- render_header() shows
# an honest "Last scan: never" state for None, not a fabricated
# timestamp/count. Only updated inside the scan-trigger block below (not
# reset on every unrelated rerun/interaction), so they persist until the
# NEXT scan actually runs.
if "last_scan_ticker_count" not in st.session_state:
    st.session_state.last_scan_ticker_count = None
if "last_scan_completed_at" not in st.session_state:
    st.session_state.last_scan_completed_at = None
if "last_scan_category_breakdown" not in st.session_state:
    st.session_state.last_scan_category_breakdown = None

# 1. Render Left Sidebar Navigation (Section 4)
render_sidebar()

# 2. Render Top Control Header Ribbon (Section 4)
is_new_scan_triggered = render_header(
    last_scan_ticker_count=st.session_state.last_scan_ticker_count,
    last_scan_completed_at=st.session_state.last_scan_completed_at,
    last_scan_category_breakdown=st.session_state.last_scan_category_breakdown,
)

# Execution pipeline chain triggered dynamically from your explicit button input
if is_new_scan_triggered:
    with st.spinner("Invoking Falcon Engine Pipeline Chain..."):
        # ─── RUN CANDIDATE GENERATION ENGINE ────────────────────────────────
        # progress_placeholder created here (not just inside the pipeline
        # call below) so "Fetching candidates..." is a real stage message
        # too, not a silent gap before the pipeline's own stage messages
        # start -- candidate generation happens upstream of ticker_universe
        # even existing, so run_new_scan_pipeline() itself can't emit it.
        progress_placeholder = st.empty()
        progress_placeholder.info("Fetching candidates from Screener...")

        from candidate_generation.candidate_generator import generate_candidates
        master_candidates_df = generate_candidates()

        if not master_candidates_df.empty and "Symbol" in master_candidates_df.columns:
            # Ensure proper suffix handling for local listings
            ticker_universe = [
                f"{sym}.NS" if not str(sym).endswith(".NS") else str(sym)
                for sym in master_candidates_df["Symbol"].tolist()
            ]

            # ─── PHASE 3-5: MARKET DATA -> INDICATORS -> PATTERNS -> CANDIDATE TABLE ─
            scan_result = run_new_scan_pipeline(ticker_universe, on_stage=progress_placeholder.info)
            progress_placeholder.empty()

            render_scan_warnings(scan_result.collection_result, scan_result.indicator_result)

            st.session_state.screener_records = scan_result.records_df
            st.session_state.last_scan_ticker_count = len(ticker_universe)
            st.session_state.last_scan_category_breakdown = compute_category_breakdown(scan_result.records_df)
        else:
            # Candidate generation itself found nothing (Screener query
            # returned zero rows) -- the scan still genuinely ran, just
            # screened 0 tickers, distinct from "never scanned" (None).
            progress_placeholder.empty()
            st.session_state.last_scan_ticker_count = 0
            st.session_state.last_scan_category_breakdown = compute_category_breakdown(pd.DataFrame())

        st.session_state.last_scan_completed_at = datetime.now(IST)

        st.rerun()

# 3. Render the dashboard -- one embedded component built from the
# reference mockup's own markup (ui/dashboard_template.html), fed real
# data (ui/dashboard_data.py) from st.session_state.screener_records --
# decision_engine.live_scorer.score_live_candidates()'s own output
# (category/predicted_p/model_version/entry/stop_loss/target/.../
# RS_Rating/Sector), no placeholder fields.
dashboard.render(st.session_state.screener_records)