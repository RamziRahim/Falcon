"""
Tests for ui/sector_ranking_panel.py -- ticker count per bar label and the
"relative to your tracked universe, not the full market" interpretation
caption.
"""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd

import ui.sector_ranking_panel as sector_ranking_panel
from ui.sector_ranking_panel import SectorRankingPanel


def _scored_universe() -> pd.DataFrame:
    return pd.DataFrame({
        "Symbol": ["A.NS", "B.NS", "C.NS", "D.NS"],
        "Sector": ["Technology", "Technology", "Technology", "Healthcare"],
        "RS_Rating": [80, 90, 70, 50],
    })


class TestTickerCountInLabel:

    def test_bar_labels_include_ticker_count(self):
        # No Sector_Index_Trend column in this fixture -- degrades to the
        # documented "N/A" placeholder rather than crashing or omitting
        # the trend segment inconsistently.
        with patch.object(sector_ranking_panel, "st") as mock_st:
            SectorRankingPanel.render(_scored_universe())

            fig = mock_st.plotly_chart.call_args[0][0]
            labels = list(fig.data[0].y)
            assert "Technology (3) — N/A" in labels
            assert "Healthcare (1) — N/A" in labels

    def test_bar_labels_include_real_sector_index_trend_when_present(self):
        universe = _scored_universe()
        universe["Sector_Index_Trend"] = ["UPTREND", "UPTREND", "UPTREND", "DOWNTREND"]

        with patch.object(sector_ranking_panel, "st") as mock_st:
            SectorRankingPanel.render(universe)

            fig = mock_st.plotly_chart.call_args[0][0]
            labels = list(fig.data[0].y)
            assert "Technology (3) — UPTREND" in labels
            assert "Healthcare (1) — DOWNTREND" in labels


class TestInterpretationCaption:

    def test_caption_rendered(self):
        with patch.object(sector_ranking_panel, "st") as mock_st:
            SectorRankingPanel.render(_scored_universe())
            mock_st.caption.assert_called_once()
            caption_text = mock_st.caption.call_args[0][0]
            assert "not the full market" in caption_text

    def test_caption_still_renders_even_with_no_rankings(self):
        """The caption explains the chart in general -- it should still
        appear on the empty-state path, not only once real data exists."""
        with patch.object(sector_ranking_panel, "st") as mock_st:
            SectorRankingPanel.render(pd.DataFrame())
            mock_st.caption.assert_called_once()
            mock_st.info.assert_called_once()
