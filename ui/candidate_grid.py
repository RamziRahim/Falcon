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
from streamlit.errors import StreamlitAPIException


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


def _render_selectable_grid(display_df: pd.DataFrame):
    """
    Renders the grid with row-click selection, preferring
    "single-row-required" (always keeps exactly one row highlighted --
    the nicer UX, closer to a radio button) and falling back to
    "single-row" on Streamlit versions too old to support it.
    """

    try:
        return st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            height=350,
            key="candidate_grid_selection",
            on_select="rerun",
            selection_mode="single-row-required",
        )
    except StreamlitAPIException:
        return st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            height=350,
            key="candidate_grid_selection",
            on_select="rerun",
            selection_mode="single-row",
        )


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

    if candidates.empty:

        st.subheader("Swing Candidates")
        st.info("No swing candidates available.")

        return None

    # Keep only available columns
    display_df = candidates[
        [c for c in DISPLAY_COLUMNS if c in candidates.columns]
    ].copy()

    st.subheader(f"Swing Candidates ({len(display_df)})")

    # Row click selects the ticker directly -- no separate dropdown needed.
    event = _render_selectable_grid(display_df)

    selected_rows = event.selection.rows if event and event.selection else []

    if selected_rows:
        return display_df.iloc[selected_rows[0]]["Symbol"]

    return None