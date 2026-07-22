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

Avg_RS_Rating is now sector-index-anchored (scoring.scoring_engine.ScoringEngine.score_universe()
computes it via scoring.sector_index_rs.compute_sector_index_rs(), not the
old small-universe peer-percentile rank) -- rank_sectors() itself needed no
change, since it's a pure aggregator of whatever RS_Rating values it's
given. Each bar additionally shows that sector's own real NSE index trend
(scoring.sector_indices.get_sector_index_trend(), already computed once by
score_universe() and passed through as the Sector_Index_Trend column --
no separate fetch here), matching what backtesting/replay_engine.py's
sector health verdict now uses alongside the breadth metrics.
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
            An optional 'Sector_Index_Trend' column (also produced by
            score_universe()) is shown alongside each bar when present --
            omitted gracefully (no trend label) for older callers that
            don't supply it.
        """

        st.markdown(
            "<h4 style='margin-top:0; font-size:15px; color:#FFFFFF;'>Key Insights — Sector RS Ranking</h4>",
            unsafe_allow_html=True,
        )
        st.caption(
            "Each bar averages the sector-index-anchored RS Rating of tickers "
            "currently in that sector within your tracked universe, against "
            "that sector's own real NSE index trend — not the full market."
        )

        ranking = rank_sectors(scored_universe)

        if ranking.empty:
            st.info("No sector rankings available yet — run a scan to populate scored candidates.")
            return

        # Real per-sector index trend, one value per Sector (score_universe()
        # attaches the same Sector_Index_Trend value to every ticker row in
        # a sector, so .first() per group recovers it without averaging
        # anything meaningless across rows).
        if "Sector_Index_Trend" in scored_universe.columns:
            trend_by_sector = scored_universe.groupby("Sector")["Sector_Index_Trend"].first()
        else:
            trend_by_sector = pd.Series(dtype=object)

        # Ascending so the strongest sector renders at the top of the horizontal bar chart
        ranking = ranking.sort_values("Avg_RS_Rating", ascending=True)
        bar_labels = [
            f"{sector} ({int(count)}) — {trend_by_sector.get(sector) or 'N/A'}"
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
