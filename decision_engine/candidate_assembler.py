"""
===============================================================================
Falcon AI Swing Trading Platform — Leadership Candidate Assembler
===============================================================================
Script      : candidate_assembler.py
Package     : Decision Engine

Bridges the three gaps leadership_decision_engine.py's own docstring
documents rather than solving itself: takes the real, disparate outputs
already sitting in the pipeline (a pattern_engine.py parquet row,
fundamental_analysis dicts, scoring outputs) and builds the exact
`candidate` / `sector_row` / `pattern_details` shapes that module already
expects -- per ITS documented contract, not a new one invented here.

-------------------------------------------------------------------------
Expected upstream shapes (confirmed real, not guessed)
-------------------------------------------------------------------------
`pattern_row` : dict -- the last row of a data/patterns/*.parquet file
    (e.g. df.iloc[-1].to_dict()), produced by technical_analysis/pattern_engine.py.
    Carries Trend_State, Close, RSI_14, ATR_14, Delivery_Pct (pass through
    from Phase 4 indicators), Has_Active_FVG, Is_Liquidity_Sweep,
    Multiple_Patterns_Confirmed, the five Is_X_Breakout PascalCase
    booleans, and (since the Part 1 persistence fast-follow) each
    pattern's *_Pivot_Level and structural-low columns.

`fundamentals` : dict -- merged from three separate fundamental_analysis
    fetches, which is the caller's job, not this module's:
      - fundamental_cache.get_fundamentals(ticker) -> roce, debt_to_equity
      - corporate_engine.get_comprehensive_fundamentals(ticker) ->
        margin_trend_yoy, days_to_earnings
      - institutional_engine.get_shareholding_profile_with_trend(ticker, session) ->
        institutional_sponsorship, fii_trend, dii_trend, promoter_trend
      - deal_activity.get_recent_institutional_activity(ticker) -> has_buy_activity
    roce/debt_to_equity/institutional_sponsorship are confirmed to come
    back as human-formatted strings ("14.20%") or non-numeric sentinels
    ("DEBT_FREE", "UNKNOWN") -- _parse_formatted_percentage handles both.

`scoring_row` : dict -- one row from scoring.scoring_engine.score_universe()
    (or score_ticker()): Rel_Vol, RS_Rating, Sector.

Delivery_Pct_20d_avg is now a real persisted column (pattern_engine.py
computes it via a rolling 20-day mean of Delivery_Pct, same defensive
pattern as Volume_SMA_20) -- assemble_candidate() reads it straight off
pattern_row like everything else here, no special handling needed.
===============================================================================
"""
from __future__ import annotations

import pandas as pd

from technical_analysis.pattern_system.macd_signal import get_macd_signal

# Naming mismatch documented in leadership_decision_engine.py's own
# docstring: pattern_engine.py persists PascalCase Is_X_Breakout columns;
# the decision engine's PATTERN_WEIGHTS expects lowercase is_x_breakout
# keys directly on `candidate`. This map is the one place that bridges it.
PATTERN_COLUMN_MAP = {
    "is_vcp_breakout": "Is_VCP_Breakout",
    "is_flat_base_breakout": "Is_Flat_Base_Breakout",
    "is_cup_handle_breakout": "Is_Cup_Handle_Breakout",
    "is_ascending_triangle_breakout": "Is_Ascending_Triangle_Breakout",
    "is_bull_flag_breakout": "Is_Bull_Flag_Breakout",
}

# Which persisted pivot_level column backs each pattern's entry in
# PATTERN_WEIGHTS -- only exists because of the Part 1 persistence
# fast-follow (pivot_level was not a column at all before that).
PATTERN_PIVOT_COLUMN_MAP = {
    "is_vcp_breakout": "VCP_Pivot_Level",
    "is_flat_base_breakout": "Flat_Base_Pivot_Level",
    "is_cup_handle_breakout": "Cup_Handle_Pivot_Level",
    "is_ascending_triangle_breakout": "Ascending_Triangle_Pivot_Level",
    "is_bull_flag_breakout": "Bull_Flag_Pivot_Level",
}


def _parse_formatted_percentage(value) -> float | None:
    """Handles corporate_engine.py / institutional_engine.py's human-formatted
    strings ("14.20%" -> 14.2). Passing this a sentinel like "DEBT_FREE"
    (confirmed to occur -- D_E can return this instead of a number) returns
    None, not 0.0 -- coercing to 0.0 would fabricate a value ("zero debt")
    that isn't what the sentinel means, and would silently let a
    DISQUALIFIERS check pass or fail on data that was never actually read.
    """
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip().endswith("%"):
        try:
            return float(value.strip().rstrip("%"))
        except ValueError:
            return None
    return None  # e.g. "DEBT_FREE", "UNKNOWN", or any other non-numeric sentinel


def assemble_candidate(
    pattern_row: dict,
    fundamentals: dict,
    scoring_row: dict,
    symbol: str | None = None,
    pattern_history_df=None,
) -> dict:
    """Builds the exact `candidate` dict leadership_decision_engine.py's
    docstring documents -- copying that field list here rather than
    re-deriving it, so the two don't drift apart.

    pattern_history_df : optional multi-row OHLCV+indicator DataFrame
        (the trailing history, not a single flattened row like
        pattern_row) -- needed by get_macd_signal(), which reads
        MACD_Hist/Close across several bars, not a single point-in-time
        value. Omitted (None) degrades to "NEUTRAL": get_macd_signal()
        itself already treats a dataframe with no MACD_Hist column as
        "no signal available," so passing an empty DataFrame produces
        the same graceful result without a separate code path here.
    """
    # D_E is a genuine scale mismatch, not just a formatting one:
    # corporate_engine.py's debt_to_equity comes back on the same
    # percentage scale as ROCE ("45.20%" from yfinance's raw
    # debtToEquity, which Yahoo already expresses x100). But
    # leadership_decision_engine.py's disqualifier (D_E > 0.5) uses the
    # standard "D/E ratio" screening convention -- a plain ratio like
    # 0.35, not 35.0. Parsing "45.20%" straight to 45.2 (as ROCE/
    # institutional_sponsorship correctly do) would make every real
    # company fail that disqualifier regardless of actual leverage, since
    # 45.2 > 0.5 always. Divide by 100 to convert into the ratio scale
    # the disqualifier actually expects -- found by tracing a real
    # candidate through categorize() end-to-end, not assumed.
    parsed_debt_to_equity_pct = _parse_formatted_percentage(fundamentals.get("debt_to_equity"))

    candidate = {
        "symbol": symbol,
        **{lower: pattern_row.get(pascal, False) for lower, pascal in PATTERN_COLUMN_MAP.items()},
        "Trend_State": pattern_row.get("Trend_State"),
        "Close": pattern_row.get("Close"),
        "RSI_14": pattern_row.get("RSI_14"),
        "ATR_14": pattern_row.get("ATR_14"),
        "Delivery_Pct": pattern_row.get("Delivery_Pct"),
        "Delivery_Pct_20d_avg": pattern_row.get("Delivery_Pct_20d_avg"),
        "has_active_fvg": pattern_row.get("Has_Active_FVG", False),
        "has_liquidity_sweep": pattern_row.get("Is_Liquidity_Sweep", False),
        "Multiple_Patterns_Confirmed": pattern_row.get("Multiple_Patterns_Confirmed", False),
        "Rel_Vol": scoring_row.get("Rel_Vol"),
        "RS_Rating": scoring_row.get("RS_Rating"),
        "ROCE": _parse_formatted_percentage(fundamentals.get("roce")),
        "D_E": parsed_debt_to_equity_pct / 100 if parsed_debt_to_equity_pct is not None else None,
        "institutional_sponsorship_pct": _parse_formatted_percentage(
            fundamentals.get("institutional_sponsorship")
        ),
        "margin_trend_yoy": fundamentals.get("margin_trend_yoy"),
        "days_to_earnings": fundamentals.get("days_to_earnings", 999),
        "has_buy_activity": fundamentals.get("has_buy_activity", False),
        "fii_trend": fundamentals.get("fii_trend"),
        "dii_trend": fundamentals.get("dii_trend"),
        "promoter_trend": fundamentals.get("promoter_trend"),
        "macd_signal": get_macd_signal(pattern_history_df if pattern_history_df is not None else pd.DataFrame()),
    }
    return candidate


def assemble_sector_row(sector_ranking_df, ticker_sector: str, sector_index_trend: str | None = None) -> dict:
    """One row from scoring.sector_rotation.rank_sectors(), plus
    Total_Sectors -- confirmed missing from rank_sectors() itself (each
    row only knows its own Rank, not how many sectors exist in total),
    and required by leadership_decision_engine.py's "top half of ranking"
    check.

    sector_index_trend : optional UPTREND/DOWNTREND/CHOPPY from
        scoring.sector_indices.get_sector_index_trend() (the real
        sector-index-based signal, not the Pct_Uptrend/Avg_RS_Rating
        breadth proxy already in sector_ranking_df). Passed through as
        Sector_Index_Trend for get_sector_health_verdict() to combine
        with the metrics -- omitted (None) when the caller hasn't wired
        scoring.sector_indices in yet, which get_sector_health_verdict()
        already handles by falling back to its metrics-only verdict.
    """
    row = sector_ranking_df.loc[ticker_sector].to_dict()
    row["Total_Sectors"] = len(sector_ranking_df)  # NOT the candidate's own Rank
    row["Sector_Index_Trend"] = sector_index_trend
    return row


def assemble_pattern_details(pattern_row: dict) -> dict:
    """Reconstructs a pattern_details-equivalent dict (name -> {"pivot_level": ...})
    from persisted parquet columns alone, per the recommended approach in
    this module's own design discussion: the raw per-pattern detector
    dicts (with pivot_level) only ever exist in memory during
    pattern_engine.py's own execution and are never persisted themselves
    -- only specific fields from them are, since the Part 1 fast-follow.
    Reconstructing from those persisted fields (rather than requiring a
    live in-memory hook into pattern_engine.py) is what lets this work
    identically for a live scan and for a backtest replaying a historical
    parquet row.
    """
    return {
        field_name: {"pivot_level": pattern_row.get(column)}
        for field_name, column in PATTERN_PIVOT_COLUMN_MAP.items()
    }
