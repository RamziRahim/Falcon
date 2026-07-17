"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : candidate_table_builder.py
Package     : Technical Analysis

Purpose
-------
Assembles the display-ready candidate table for the screener grid, one row
per ticker in the universe, from Falcon's Phase 4 pattern-file output.

Responsibilities
----------------
• Read the latest cached pattern data for each ticker (data/patterns/*.parquet)
• Derive the display Status ("Breakout" / "Pullback" / "Strong Trend") from
  boolean pattern flags
• Fall back to clearly-flagged synthetic placeholder rows (Is_Mock_Row=True)
  when no real pattern data exists yet for any ticker

===============================================================================
"""

from __future__ import annotations

import os

import pandas as pd

from common.logger import get_logger

logger = get_logger(__name__)

PATTERN_DIR = "data/patterns"

MOCK_ROW_LIMIT = 5


def _derive_status(last_row: pd.Series) -> str:
    """
    Derives the display Status from boolean pattern flags on the latest row.
    """

    if last_row.get("Is_VCP_Breakout", False):
        return "Breakout"

    if last_row.get("Is_Liquidity_Sweep", False):
        return "Pullback"

    return "Strong Trend"


def build_candidate_table(ticker_universe: list[str]) -> pd.DataFrame:
    """
    Reads the latest pattern data for each ticker in the universe and
    assembles the display-ready candidate table row per ticker.

    Falls back to a small set of clearly-flagged synthetic placeholder
    rows (Is_Mock_Row=True) when no real pattern data exists yet for
    any ticker — never a silently fabricated "real" row.

    Returns
    -------
    pd.DataFrame with columns: Symbol, Price, Trend_State, VCP_Score,
    Status, ROCE, YoY_Rev, D_E, Is_Mock_Row
    """

    consolidated_records = []

    for ticker in ticker_universe:

        pattern_path = os.path.join(PATTERN_DIR, f"{ticker}.parquet")

        if os.path.exists(pattern_path):

            df_metrics = pd.read_parquet(pattern_path)

            if not df_metrics.empty:

                last_row = df_metrics.iloc[-1]

                consolidated_records.append({
                    "Symbol": ticker,
                    "Price": round(last_row.get("Close", 0.0), 2),
                    "Trend_State": last_row.get("Trend_State", "UNKNOWN"),
                    "VCP_Score": round(last_row.get("VCP_Score", 0.0), 1),
                    "Status": _derive_status(last_row),
                    # Table-wide fundamentals are a fast-follow (Task 2.5 wires only the
                    # detail panel below); until then the grid shows an honest "not
                    # computed" dash rather than a fabricated number.
                    "ROCE": "—", "YoY_Rev": "—", "D_E": "—",
                    "Is_Mock_Row": False,
                })

    # If no physical parquets exist yet, use this compliant fallback data
    if not consolidated_records:

        for ticker in ticker_universe[:MOCK_ROW_LIMIT]:

            consolidated_records.append({
                # TODO(cleanup 2026-07-15): fully synthetic placeholder row — no real data
                # exists yet for this ticker (pattern engine hasn't run). Flagged via
                # Is_Mock_Row so the UI can visibly mark it instead of showing it as real.
                "Symbol": ticker, "Price": 1250.00, "Trend_State": "UPTREND", "VCP_Score": 88.5,
                "Status": "Breakout", "ROCE": "—", "YoY_Rev": "—", "D_E": "—",
                "Is_Mock_Row": True,
            })

    return pd.DataFrame(consolidated_records)
