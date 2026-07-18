"""
Tests for ui/candidate_grid.py -- row-click ticker selection (replacing the
old dropdown), the candidate-count subheader, and the single-row-required
-> single-row fallback for older Streamlit versions.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.errors import StreamlitAPIException

import ui.candidate_grid as candidate_grid


def _candidates_df() -> pd.DataFrame:
    return pd.DataFrame({
        "Symbol": ["AAA.NS", "BBB.NS", "CCC.NS"],
        "Price": [100.0, 200.0, 300.0],
        "Trend_State": ["UPTREND", "DOWNTREND", "CHOPPY"],
        "VCP_Score": [10.0, 20.0, 30.0],
        "Status": ["Breakout", "Pullback", "Strong Trend"],
    })


def _event_with_selected_rows(rows: list[int]):
    return SimpleNamespace(selection=SimpleNamespace(rows=rows))


class TestEmptyCandidates:

    def test_returns_none_and_shows_info(self):
        with patch.object(candidate_grid, "st") as mock_st:
            result = candidate_grid.render(pd.DataFrame())
            assert result is None
            mock_st.info.assert_called_once()
            mock_st.dataframe.assert_not_called()

    def test_subheader_has_no_count_when_empty(self):
        with patch.object(candidate_grid, "st") as mock_st:
            candidate_grid.render(pd.DataFrame())
            mock_st.subheader.assert_called_once_with("Swing Candidates")


class TestSubheaderCount:

    def test_subheader_shows_row_count(self):
        with patch.object(candidate_grid, "st") as mock_st:
            mock_st.dataframe.return_value = _event_with_selected_rows([])
            candidate_grid.render(_candidates_df())
            mock_st.subheader.assert_called_once_with("Swing Candidates (3)")


class TestRowClickSelection:

    def test_no_selection_returns_none(self):
        with patch.object(candidate_grid, "st") as mock_st:
            mock_st.dataframe.return_value = _event_with_selected_rows([])
            result = candidate_grid.render(_candidates_df())
            assert result is None

    def test_selected_row_returns_correct_symbol_not_just_index(self):
        """Regression guard: must map the selected row index through the
        *displayed* dataframe's Symbol column, not assume index == row
        position in some other ordering."""
        with patch.object(candidate_grid, "st") as mock_st:
            mock_st.dataframe.return_value = _event_with_selected_rows([1])
            result = candidate_grid.render(_candidates_df())
            assert result == "BBB.NS"

    def test_selecting_first_row_returns_first_symbol(self):
        with patch.object(candidate_grid, "st") as mock_st:
            mock_st.dataframe.return_value = _event_with_selected_rows([0])
            result = candidate_grid.render(_candidates_df())
            assert result == "AAA.NS"

    def test_none_event_returns_none_not_crash(self):
        with patch.object(candidate_grid, "st") as mock_st:
            mock_st.dataframe.return_value = None
            result = candidate_grid.render(_candidates_df())
            assert result is None


class TestSelectionModeFallback:

    def test_prefers_single_row_required(self):
        with patch.object(candidate_grid, "st") as mock_st:
            mock_st.dataframe.return_value = _event_with_selected_rows([])
            candidate_grid.render(_candidates_df())
            _, kwargs = mock_st.dataframe.call_args
            assert kwargs["selection_mode"] == "single-row-required"
            assert mock_st.dataframe.call_count == 1

    def test_falls_back_to_single_row_when_unsupported(self):
        with patch.object(candidate_grid, "st") as mock_st:
            mock_st.dataframe.side_effect = [
                StreamlitAPIException("Invalid selection mode"),
                _event_with_selected_rows([0]),
            ]
            result = candidate_grid.render(_candidates_df())

            assert mock_st.dataframe.call_count == 2
            first_call_kwargs = mock_st.dataframe.call_args_list[0][1]
            second_call_kwargs = mock_st.dataframe.call_args_list[1][1]
            assert first_call_kwargs["selection_mode"] == "single-row-required"
            assert second_call_kwargs["selection_mode"] == "single-row"
            assert result == "AAA.NS"
