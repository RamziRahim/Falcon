from __future__ import annotations

import streamlit as st


def render() -> None:

    with st.sidebar:

        st.title("🦅 FALCON")

        st.caption(
            "Scan markets. Find leaders. Ride the trend."
        )

        st.divider()

        st.subheader("Navigation")

        st.button(
            "🏠 Dashboard",
            use_container_width=True,
            disabled=True,
        )

        st.divider()

        st.caption("Version 2.0")
        st.caption("© Falcon")