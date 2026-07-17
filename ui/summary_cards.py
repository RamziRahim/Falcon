"""
===============================================================================
Falcon AI Swing Trading Platform
Module : summary_cards.py
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


@dataclass(slots=True)
class DashboardStats:

    candidates: int = 0
    breakouts: int = 0
    pullbacks: int = 0
    strong_trends: int = 0
    market_status: str = "OPEN"
    scan_duration: float = 0.0


def render(stats: DashboardStats) -> None:
    """
    Render Falcon dashboard summary cards.
    """

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    with c1:
        st.metric(
            "Candidates",
            stats.candidates,
        )

    with c2:
        st.metric(
            "Breakouts",
            stats.breakouts,
        )

    with c3:
        st.metric(
            "Pullbacks",
            stats.pullbacks,
        )

    with c4:
        st.metric(
            "Strong Trends",
            stats.strong_trends,
        )

    with c5:
        st.metric(
            "Market",
            stats.market_status,
        )

    with c6:
        st.metric(
            "Scan Time",
            f"{stats.scan_duration:.2f}s",
        )

    st.divider()