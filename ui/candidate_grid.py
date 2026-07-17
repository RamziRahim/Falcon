"""
===============================================================================
Falcon AI Swing Trading Platform
Module  : candidate_grid.py
Package : ui

Purpose
-------
Render the Falcon Swing Candidate Grid.

Phase 1
-------
• Native Streamlit DataFrame
• Single stock selection

Phase 2
-------
• AG Grid
• Filtering
• Sorting
• Conditional formatting
• Row selection
===============================================================================
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st


DISPLAY_COLUMNS = [
    "Symbol",
    "Price",
    "Trend_State",
    "VCP_Score",
    "Status",
    "RS_Rating",
    "RS_2M",
    "RS_6M",
    "RS_12M",
    "Rel_Vol",
    "Sector",
    "ROCE",
    "YoY_Rev",
    "D_E",
]


def render(
    candidates: pd.DataFrame,
) -> Optional[str]:
    """
    Render candidate grid.

    Parameters
    ----------
    candidates
        Candidate dataframe.

    Returns
    -------
    Selected symbol or None.
    """

    st.subheader("Swing Candidates")

    if candidates.empty:

        st.info("No swing candidates available.")

        return None

    # Keep only available columns
    display_df = candidates[
        [c for c in DISPLAY_COLUMNS if c in candidates.columns]
    ].copy()

    # Display dataframe
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=350,
    )

    # Symbol selector (temporary)
    symbol = st.selectbox(
        "Select Stock",
        options=display_df["Symbol"].tolist(),
        index=0,
    )

    return symbol