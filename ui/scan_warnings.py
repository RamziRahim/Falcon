"""
===============================================================================
Falcon AI Swing Trading Platform
Module  : scan_warnings.py
Package : ui

Purpose
-------
Surfaces per-ticker failures from a New Scan run (failed downloads, tickers
skipped for insufficient history, failed indicator calculation) instead of
letting the UI silently swallow them.
===============================================================================
"""

from __future__ import annotations

import streamlit as st

from market_data.data_collection_engine import DataCollectionResult
from technical_analysis.indicator_engine import IndicatorEngineResult


def render(collection_result: DataCollectionResult, indicator_result: IndicatorEngineResult) -> None:
    """
    Renders one st.warning per non-empty failure/skip category. Renders
    nothing when everything succeeded.
    """

    if collection_result.failed:
        st.warning(
            f"{collection_result.failed} ticker(s) failed market data collection."
        )

    if indicator_result.skipped_list:
        st.warning(
            f"{len(indicator_result.skipped_list)} ticker(s) skipped — "
            f"insufficient history (<200 candles): "
            f"{', '.join(indicator_result.skipped_list)}"
        )

    if indicator_result.failed_list:
        st.warning(
            f"{len(indicator_result.failed_list)} ticker(s) failed indicator "
            f"calculation: {', '.join(indicator_result.failed_list)}"
        )
