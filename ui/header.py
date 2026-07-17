"""
===============================================================================
Falcon AI Swing Trading Platform
Module : header.py
===============================================================================
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st


def render() -> bool:
    """
    Render Falcon dashboard header.

    Returns
    -------
    bool
        True when New Scan is clicked.
    """

    left, right = st.columns([3.8, 2.2])

    # ------------------------------------------------------------------
    # Left
    # ------------------------------------------------------------------

    with left:

        hour = datetime.now().hour

        if hour < 12:
            greeting = "Good Morning"
        elif hour < 17:
            greeting = "Good Afternoon"
        else:
            greeting = "Good Evening"

        st.markdown(
            f"""
### {greeting}, Trader 👋

Scan markets. Find leaders. Ride the trend.
"""
        )

    # ------------------------------------------------------------------
    # Right
    # ------------------------------------------------------------------

    with right:

        c1, c2 = st.columns([1, 1])

        with c1:

            st.metric(
                "Market",
                "🟢 OPEN",
            )

        with c2:

            st.metric(
                "Time",
                datetime.now().strftime("%H:%M"),
            )

        new_scan = st.button(
            "➕ New Scan",
            use_container_width=True,
            type="primary",
        )

        st.button(
            "Market Overview",
            use_container_width=True,
        )

    st.divider()

    # ------------------------------------------------------------------
    # Market Snapshot
    # ------------------------------------------------------------------

    i1, i2, i3 = st.columns(3)

    with i1:

        st.metric(
            "NIFTY 50",
            "24,801.16",
            "+0.88%",
        )

    with i2:

        st.metric(
            "NIFTY MIDCAP 150",
            "19,186.45",
            "+0.74%",
        )

    with i3:

        st.metric(
            "NIFTY SMALLCAP 250",
            "15,832.20",
            "+1.02%",
        )

    st.divider()

    return new_scan