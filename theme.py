"""
===============================================================================
Falcon AI Swing Trading Platform
Module : theme.py
Package: ui
Purpose: Centralized Falcon UI theme and styling
===============================================================================
"""

from __future__ import annotations

import streamlit as st


# -----------------------------------------------------------------------------
# Falcon Color Palette
# -----------------------------------------------------------------------------

BACKGROUND = "#0A0F1D"
SIDEBAR = "#050810"

CARD = "#111827"
CARD_BORDER = "#1F2937"

TEXT = "#F8FAFC"
TEXT_SECONDARY = "#9CA3AF"

GREEN = "#10B981"
RED = "#EF4444"
BLUE = "#3B82F6"
YELLOW = "#FBBF24"

HOVER = "#172033"


# -----------------------------------------------------------------------------
# Theme Loader
# -----------------------------------------------------------------------------

def apply_theme() -> None:
    """
    Apply Falcon's global UI theme.

    Call this once at the top of app.py immediately after
    st.set_page_config().
    """

    st.markdown(
        f"""
<style>

/* ============================================================================
   GLOBAL
============================================================================ */

html, body, [class*="css"] {{
    background-color: {BACKGROUND};
    color: {TEXT};
    font-family: Inter, Segoe UI, sans-serif;
}}

.main {{
    background-color: {BACKGROUND};
}}

.block-container {{
    padding-top: 1.0rem;
    padding-left: 1.5rem;
    padding-right: 1.5rem;
    max-width: 100%;
}}


/* ============================================================================
   SIDEBAR
============================================================================ */

[data-testid="stSidebar"] {{
    background-color: {SIDEBAR};
    border-right: 1px solid {CARD_BORDER};
}}

[data-testid="stSidebar"] * {{
    color: {TEXT};
}}


/* ============================================================================
   HEADERS
============================================================================ */

h1 {{
    font-size: 2rem;
    font-weight: 700;
}}

h2 {{
    font-size: 1.45rem;
}}

h3 {{
    font-size: 1.1rem;
}}


/* ============================================================================
   CARDS
============================================================================ */

.falcon-card {{

    background-color: {CARD};

    border: 1px solid {CARD_BORDER};

    border-radius: 14px;

    padding: 18px;

}}

.falcon-card:hover {{

    border-color: {BLUE};

}}


/* ============================================================================
   METRIC CARDS
============================================================================ */

.metric-title {{

    color: {TEXT_SECONDARY};

    font-size: 12px;

    text-transform: uppercase;

    letter-spacing: .5px;

}}

.metric-value {{

    font-size: 30px;

    font-weight: 700;

    color: {TEXT};

}}

.metric-positive {{

    color: {GREEN};

}}

.metric-negative {{

    color: {RED};

}}


/* ============================================================================
   PANELS
============================================================================ */

.falcon-panel {{

    background-color: {CARD};

    border: 1px solid {CARD_BORDER};

    border-radius: 14px;

    padding: 20px;

    height: 100%;

}}

.panel-title {{

    font-size: 15px;

    font-weight: 700;

    color: {TEXT};

    margin-bottom: 15px;

}}


/* ============================================================================
   BADGES
============================================================================ */

.badge-green {{

    background: rgba(16,185,129,.15);

    color: {GREEN};

    border: 1px solid rgba(16,185,129,.35);

    border-radius: 8px;

    padding: 4px 10px;

    font-size: 12px;

    font-weight: 700;

}}

.badge-red {{

    background: rgba(239,68,68,.15);

    color: {RED};

    border: 1px solid rgba(239,68,68,.35);

    border-radius: 8px;

    padding: 4px 10px;

    font-size: 12px;

    font-weight: 700;

}}

.badge-blue {{

    background: rgba(59,130,246,.15);

    color: {BLUE};

    border: 1px solid rgba(59,130,246,.35);

    border-radius: 8px;

    padding: 4px 10px;

    font-size: 12px;

    font-weight: 700;

}}


/* ============================================================================
   BUTTONS
============================================================================ */

.stButton > button {{

    width: 100%;

    border-radius: 10px;

    border: none;

    background-color: {BLUE};

    color: white;

    font-weight: 600;

    height: 42px;

}}

.stButton > button:hover {{

    background-color: #2563EB;

}}


/* ============================================================================
   DATAFRAME
============================================================================ */

[data-testid="stDataFrame"] {{

    border: 1px solid {CARD_BORDER};

    border-radius: 12px;

}}


/* ============================================================================
   PLOTLY
============================================================================ */

.js-plotly-plot {{

    border-radius: 12px;

}}


/* ============================================================================
   SCROLLBAR
============================================================================ */

::-webkit-scrollbar {{

    width: 10px;

}}

::-webkit-scrollbar-thumb {{

    background: #2D3748;

    border-radius: 8px;

}}

::-webkit-scrollbar-track {{

    background: {BACKGROUND};

}}

</style>
""",
        unsafe_allow_html=True,
    )