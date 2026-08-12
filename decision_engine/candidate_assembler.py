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

from technical_analysis.consolidation_features import compute_consolidation_features, compute_rs_line_new_high
from technical_analysis.pattern_engine import macro_swing_detector
from technical_analysis.pattern_system.macd_signal import get_macd_signal
from technical_analysis.liquidity_sweep import detect_liquidity_sweep
from technical_analysis.fair_value_gap import detect_fvg

# Same floor consolidation_features.py's own callers use (Phase 4.3's
# backfill_v2_features.py, tests/run_extended_window_replay.py) --
# _find_base_boundaries() needs a real macro-pivot history, not a couple
# of bars.
MIN_HISTORY_FOR_MACRO_PIVOTS = 10

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

# A-5 breakout-recency contract -- same persistence pattern as
# PATTERN_PIVOT_COLUMN_MAP above, one column pair per pattern.
PATTERN_BARS_SINCE_BREAKOUT_COLUMN_MAP = {
    "is_vcp_breakout": "VCP_Bars_Since_Breakout",
    "is_flat_base_breakout": "Flat_Base_Bars_Since_Breakout",
    "is_cup_handle_breakout": "Cup_Handle_Bars_Since_Breakout",
    "is_ascending_triangle_breakout": "Ascending_Triangle_Bars_Since_Breakout",
    "is_bull_flag_breakout": "Bull_Flag_Bars_Since_Breakout",
}

PATTERN_BREAKOUT_WITHIN_K_BARS_COLUMN_MAP = {
    "is_vcp_breakout": "VCP_Breakout_Within_K_Bars",
    "is_flat_base_breakout": "Flat_Base_Breakout_Within_K_Bars",
    "is_cup_handle_breakout": "Cup_Handle_Breakout_Within_K_Bars",
    "is_ascending_triangle_breakout": "Ascending_Triangle_Breakout_Within_K_Bars",
    "is_bull_flag_breakout": "Bull_Flag_Breakout_Within_K_Bars",
}

# 2.2 (I-6): each pattern's own structural-low column (already persisted
# by the Part 1 fast-follow, one differently-named column per pattern --
# VCP_Structural_Low/Flat_Base_Low/Cup_Handle_Low/Ascending_Triangle_Support/
# Bull_Flag_Low) mapped to the single uniform "structural_low" key
# get_entry_target_stop() reads, regardless of which pattern won selection.
PATTERN_STRUCTURAL_LOW_COLUMN_MAP = {
    "is_vcp_breakout": "VCP_Structural_Low",
    "is_flat_base_breakout": "Flat_Base_Low",
    "is_cup_handle_breakout": "Cup_Handle_Low",
    "is_ascending_triangle_breakout": "Ascending_Triangle_Support",
    "is_bull_flag_breakout": "Bull_Flag_Low",
}

# 2.2 (I-6) two-low model fix: each pattern's PROXIMAL low column -- the
# near-term support/resistance closest to entry, used for the stop.
# Deliberately distinct from PATTERN_STRUCTURAL_LOW_COLUMN_MAP's (deeper)
# target-anchoring low above -- using the same low for both was the
# original RR-floor bug (any unclamped structural stop mathematically
# forced reward_risk == 1.0). See each detector's own module docstring
# for why proximal is provably closer to entry than structural in a
# well-formed pattern.
PATTERN_PROXIMAL_LOW_COLUMN_MAP = {
    "is_vcp_breakout": "VCP_Proximal_Low",
    "is_flat_base_breakout": "Flat_Base_Proximal_Low",
    "is_cup_handle_breakout": "Cup_Handle_Proximal_Low",
    "is_ascending_triangle_breakout": "Ascending_Triangle_Proximal_Low",
    "is_bull_flag_breakout": "Bull_Flag_Proximal_Low",
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
    benchmark_history=None,
) -> dict:
    """Builds the exact `candidate` dict leadership_decision_engine.py's
    docstring documents -- copying that field list here rather than
    re-deriving it, so the two don't drift apart.

    pattern_history_df : optional multi-row OHLCV+indicator DataFrame
        (the trailing history, not a single flattened row like
        pattern_row) -- needed by get_macd_signal() (reads MACD_Hist/Close
        across several bars), detect_liquidity_sweep()/detect_fvg() (both
        need a trailing window, not a single point-in-time value), and
        (Phase 4.6) compute_consolidation_features()/compute_rs_line_new_high()
        for the v2 consolidation-quality model's own 9 features. Omitted
        (None) degrades gracefully for all of these: get_macd_signal()
        already treats a dataframe with no MACD_Hist column as "no signal
        available," detect_liquidity_sweep()/detect_fvg() both treat
        insufficient history as "nothing detected," and
        compute_consolidation_features() itself returns valid=False with
        an explicit invalidated_reason rather than a crash -- so passing
        an empty DataFrame produces the same graceful, fail-explicit
        result without a separate code path here.

    benchmark_history : optional NIFTY 50 OHLCV history (Phase 4.6) --
        needed by compute_rs_line_new_high() (RS line = stock Close /
        benchmark Close). Callers pass their own already-truncated
        (backtest) or current (live) benchmark series; identical function
        call either way, no separate logic path. Omitted (None) degrades
        to rs_line_new_high=None with invalidated_reason="NO_BENCHMARK_HISTORY"
        rather than a crash -- categorize()'s calibrated-model call
        already has to handle a candidate missing v2 features (falls
        back to the pre-model score-based path), so this is one more
        instance of that same handled case, not a new failure mode.

    liquidity_sweep_direction/fvg_direction/fvg_filled_pct are always
    computed and included on `candidate` regardless of whether the
    microstructure signals are actually used downstream -- assembling
    the data is unconditional; leadership_decision_engine.categorize()'s
    enable_microstructure_signals flag controls whether they affect the
    score, not whether they're present here. Cheap either way (both
    detectors are simple price-action checks, not expensive computation).
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

    history = pattern_history_df if pattern_history_df is not None else pd.DataFrame()
    sweep_result = detect_liquidity_sweep(history)
    # len(history) - 1 is -1 when history is empty, which detect_fvg()'s
    # own "as_of_index < 2" bounds check already rejects -- no separate
    # empty-history branch needed here.
    fvg_result = detect_fvg(history, as_of_index=len(history) - 1)

    # Phase 4.6: the v2 consolidation-quality model's own 9 own-history
    # features + rs_line_new_high. Same functions, same fail-explicit
    # convention, whether called from a live scan (history/benchmark_history
    # are already "as of now") or a backtest replay (both already
    # truncated by the caller) -- no separate logic path for either side.
    macro_pivots = macro_swing_detector.detect_swings(history) if len(history) >= MIN_HISTORY_FOR_MACRO_PIVOTS else []
    consolidation = compute_consolidation_features(history, macro_pivots)

    if benchmark_history is not None and not benchmark_history.empty:
        rs_line = compute_rs_line_new_high(history, benchmark_history)
    else:
        rs_line = {"rs_line_new_high": None, "invalidated_reason": "NO_BENCHMARK_HISTORY", "rs_line_value": None}

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
        "macd_signal": get_macd_signal(history),
        "liquidity_sweep_direction": sweep_result["direction"],
        "fvg_direction": fvg_result["direction"],
        "fvg_filled_pct": fvg_result["gap_filled_pct"],
        # Phase 4.6: v2 consolidation-quality model inputs.
        "consolidation_valid": consolidation["valid"],
        "consolidation_invalidated_reason": consolidation["invalidated_reason"],
        "prior_trend_pct_gain": consolidation["prior_trend_pct_gain"],
        "prior_trend_slope": consolidation["prior_trend_slope"],
        "prior_trend_bars": consolidation["prior_trend_bars"],
        "base_depth_pct": consolidation["base_depth_pct"],
        "base_length_bars": consolidation["base_length_bars"],
        "contraction_slope": consolidation["contraction_slope"],
        "volume_dryup_ratio": consolidation["volume_dryup_ratio"],
        "volume_down_up_ratio": consolidation["volume_down_up_ratio"],
        "pivot_proximity": consolidation["pivot_proximity"],
        "breakout_volume_ratio": consolidation["breakout_volume_ratio"],
        "dist_52w_high": consolidation["dist_52w_high"],
        "dist_52w_high_invalidated_reason": consolidation["dist_52w_high_invalidated_reason"],
        "rs_line_new_high": rs_line["rs_line_new_high"],
        "rs_line_invalidated_reason": rs_line["invalidated_reason"],
        "rs_line_value": rs_line["rs_line_value"],
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
    """Reconstructs a pattern_details-equivalent dict
    (name -> {"pivot_level": ..., "structural_low": ..., "bars_since_breakout": ...,
    "breakout_within_last_k_bars": ...}) from persisted parquet columns
    alone, per the recommended approach in this module's own design
    discussion: the raw per-pattern detector dicts only ever exist in
    memory during pattern_engine.py's own execution and are never
    persisted themselves -- only specific fields from them are, since the
    Part 1 fast-follow (pivot_level, and each pattern's own differently-
    named structural-low column -- see PATTERN_STRUCTURAL_LOW_COLUMN_MAP)
    and the A-5 breakout-recency contract
    (bars_since_breakout/breakout_within_last_k_bars). Reconstructing from
    those persisted fields (rather than requiring a live in-memory hook
    into pattern_engine.py) is what lets this work identically for a live
    scan and for a backtest replaying a historical parquet row.

    structural_low/proximal_low are the single uniform keys
    get_entry_target_stop() (2.2, I-6, two-low model) reads regardless of
    which pattern won selection -- callers never need to know that VCP's
    own columns are named differently from Cup & Handle's.
    """
    return {
        field_name: {
            "pivot_level": pattern_row.get(column),
            "structural_low": pattern_row.get(PATTERN_STRUCTURAL_LOW_COLUMN_MAP[field_name]),
            "proximal_low": pattern_row.get(PATTERN_PROXIMAL_LOW_COLUMN_MAP[field_name]),
            "bars_since_breakout": pattern_row.get(PATTERN_BARS_SINCE_BREAKOUT_COLUMN_MAP[field_name]),
            "breakout_within_last_k_bars": pattern_row.get(
                PATTERN_BREAKOUT_WITHIN_K_BARS_COLUMN_MAP[field_name], False
            ),
        }
        for field_name, column in PATTERN_PIVOT_COLUMN_MAP.items()
    }
