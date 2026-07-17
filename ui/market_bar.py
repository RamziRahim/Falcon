"""
===============================================================================
Falcon AI Swing Trading Platform
Module  : market_bar.py
Package : ui

Purpose
-------
Displays live market indices.

Phase 1
-------
Static data (placeholder)

Phase 2
-------
Connect to Market Data Engine
===============================================================================
"""

from __future__ import annotations

import streamlit as st


DEFAULT_MARKET_DATA = [
    {
        "name": "NIFTY 50",
        "value": "24,501.15",
        "change": "+0.68%",
    },
    {
        "name": "NIFTY MIDCAP 150",
        "value": "19,186.45",
        "change": "+0.74%",
    },
    {
        "name": "NIFTY SMALLCAP 250",
        "value": "15,632.20",
        "change": "+1.02%",
    },
]


def render(
    market_data: list | None = None,
) -> None:
    """
    Render market snapshot ribbon.
    """

    if market_data is None:
        market_data = DEFAULT_MARKET_DATA

    columns = st.columns(len(market_data))

    for column, item in zip(columns, market_data):

        with column:

            change = item["change"]

            if change.startswith("-"):
                delta_color = "inverse"
            else:
                delta_color = "normal"

            st.metric(
                label=item["name"],
                value=item["value"],
                delta=change,
                delta_color=delta_color,
            )

    st.divider()