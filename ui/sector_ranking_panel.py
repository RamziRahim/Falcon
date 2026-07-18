"""
===============================================================================
Falcon AI Swing Trading Platform
Module  : sector_ranking_panel.py
Package : ui

Purpose
-------
Renders the "Key Insights" Sector RS Ranking bar chart — Phase 1 of
scoring/sector_rotation.py's sector aggregation (average composite RS Rating
per sector, ranked strongest to weakest).
===============================================================================
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from scoring.sector_rotation import rank_sectors


class SectorRankingPanel:
    @staticmethod
    def render(scored_universe: pd.DataFrame) -> None:
        """
        Renders the Sector RS Ranking bar chart from a scored candidate table.

        Parameters
        ----------
        scored_universe : pd.DataFrame
            Candidate rows with at least 'Sector' and 'RS_Rating' columns,
            as produced by scoring.scoring_engine.ScoringEngine.score_universe().
        """

        st.markdown(
            "<h4 style='margin-top:0; font-size:15px; color:#FFFFFF;'>Key Insights — Sector RS Ranking</h4>",
            unsafe_allow_html=True,
        )
        st.caption(
            "Each bar averages the RS Rating of tickers currently in that sector "
            "within your tracked universe — not the full market. Higher = "
            "relatively stronger momentum among the stocks you're tracking right "
            "now, not an absolute market-wide ranking."
        )

        ranking = rank_sectors(scored_universe)

        if ranking.empty:
            st.info("No sector rankings available yet — run a scan to populate scored candidates.")
            return

        # Ascending so the strongest sector renders at the top of the horizontal bar chart
        ranking = ranking.sort_values("Avg_RS_Rating", ascending=True)
        bar_labels = [
            f"{sector} ({int(count)})"
            for sector, count in zip(ranking.index, ranking["Ticker_Count"])
        ]

        fig = go.Figure(
            go.Bar(
                x=ranking["Avg_RS_Rating"],
                y=bar_labels,
                orientation="h",
                marker_color="#3B82F6",
                text=ranking["Avg_RS_Rating"].round(1),
                textposition="outside",
            )
        )

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=max(220, 40 * len(ranking)),
            margin=dict(l=10, r=30, t=10, b=10),
            xaxis=dict(title="Avg RS Rating", range=[0, 100]),
            showlegend=False,
        )

        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
