"""
===============================================================================
Falcon AI Swing Trading Platform — Backtesting Replay Engine (Part A)
===============================================================================
Script      : replay_engine.py
Package     : Backtesting

Reconstructs what leadership_decision_engine.py would have said about a
ticker on an arbitrary historical date, using ONLY data available through
that date. pattern_engine.py computes each pattern once against the FULL
history and broadcasts that single answer to every row -- correct for live
scanning, wrong for backtesting, where "what would this system have said
on 2024-03-03" requires re-running detection using only data through that
date.

CRITICAL: no code path here may read any row of any input dataframe dated
after as_of_date. This is the one thing this whole module exists to get
right -- see tests/backtesting/test_replay_engine.py's lookahead-bias test
for how that gets verified directly (corrupt the future, confirm the
answer doesn't change).

-------------------------------------------------------------------------
Scope decisions (settled, recorded here so they don't drift)
-------------------------------------------------------------------------
Fundamental gates (ROCE, D/E disqualifiers, and everything else
fundamental_analysis-sourced) are disabled for this backtest, not silently
applied -- current fundamental data is a live snapshot, not point-in-time.
Applying today's ROCE to judge a trade from 2 years ago is lookahead bias.
Real point-in-time fundamentals (nselib's financial_results_for_equity
pulls genuine historical NSE XBRL filings) is real and buildable, but
deliberately deferred to a second-pass backtest once this one validates
the core technical/regime design. See
leadership_decision_engine.categorize()'s disable_fundamental_signals for
exactly what this skips.

RS Rating is a percentile rank against the whole tracked universe
(scoring.relative_strength.compute_rs_ratings) -- replaying it correctly
means truncating EVERY ticker in the universe to the same as_of_date, not
just the one being tested, and recomputing the percentile ranks fresh.
build_scored_universe_as_of() does this once per date; run_backtest.py
(Part D) reuses that result across every ticker sampled on the same date
rather than recomputing it once per ticker.

Market regime is trend-based, not VIX-based: NIFTY's own Trend_State
(same market_structure_engine already used per-stock, applied to
benchmark_history) replaced VIX as the regime signal -- validated first
via backtesting/regime_threshold_calibration.py's
analyze_trend_state_vs_forward_returns() (UPTREND/CHOPPY/DOWNTREND showed
the correct monotonic ordering; VIX's own validation showed the opposite
direction at a 20-day horizon). See
leadership_decision_engine.get_market_regime_verdict()'s own docstring
for the full reasoning. vix_history is still threaded through this
module's signature (fetched by callers, no longer read here) -- VIX
isn't discarded, just no longer the regime signal itself; flagged as a
candidate input elsewhere (e.g. stop-loss width) in a future task.
===============================================================================
"""
from __future__ import annotations

import pandas as pd

from technical_analysis.indicator_calculator import indicator_calculator
from technical_analysis.pattern_engine import analyze_ticker, build_pattern_row_fields, macro_swing_detector
from technical_analysis.pattern_system.market_structure import market_structure_engine
from scoring.relative_volume import calculate as calculate_relative_volume
from scoring.relative_strength import compute_rs_ratings
from scoring.sector_rotation import rank_sectors
from scoring.sector_map import sector_map
from scoring.market_regime import count_distribution_days
from decision_engine.candidate_assembler import assemble_candidate, assemble_sector_row, assemble_pattern_details
from decision_engine.leadership_decision_engine import categorize, get_market_regime_verdict

# Same floor pattern_engine.py's execute_pipeline() uses -- a shorter
# truncated view can't support real fractal/indicator detection anyway.
MIN_HISTORY_ROWS = 20

NO_DATA_RESULT_TEMPLATE = {
    "category": "NO_DATA",
    "market_regime_verdict": None,
    "sector_health_verdict": None,
    "confidence_score": 0.0,
    "caps_applied": [],
    "fakeout_risk_flags": [],
    "contributing_factors": [],
    "entry": None,
    "stop_loss": None,
    "target": None,
    "supporting_data": {},
}


def _truncate(df: pd.DataFrame, as_of_date: pd.Timestamp) -> pd.DataFrame:
    """Rows with Date <= as_of_date only, sorted ascending -- the one
    operation every other function in this module depends on getting
    right."""
    ordered = df.sort_values("Date").reset_index(drop=True)
    return ordered[ordered["Date"] <= as_of_date].reset_index(drop=True)


def _trend_state_of_truncated(df: pd.DataFrame) -> str:
    """Lightest-weight replay needed for a universe peer's sector-breadth
    contribution: just Trend_State via swing detection + market
    structure, not the full 5-detector chain -- rank_sectors()'s
    Pct_Uptrend only needs this one field per ticker, and running full
    pattern detection for every universe member at every replay date
    would multiply the already-expensive per-date cost for no benefit."""
    if len(df) < MIN_HISTORY_ROWS:
        return "UNKNOWN"
    macro_pivots = macro_swing_detector.detect_swings(df)
    return market_structure_engine.analyze_structure(df, macro_pivots)["trend_state"]


def build_scored_universe_as_of(
    as_of_date: pd.Timestamp, universe_histories: dict
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """
    Truncates every ticker in the tracked universe to as_of_date and
    recomputes RS Rating + sector breadth fresh against that truncated
    view -- the actual point of this function, since a percentile rank
    computed against full (untruncated) histories would leak future
    relative performance into a historical replay date.

    Computed once per date, not once per ticker: run_backtest.py (Part D)
    calls this once per sampled date and reuses the result across every
    ticker sampled at that same date via replay_decision_as_of's
    precomputed_universe_scoring parameter.

    Returns
    -------
    (scored_universe, sector_ranking, rs_ratings) : the assembled
    Symbol/Sector/RS_Rating/Trend_State table, scoring.sector_rotation.rank_sectors()'s
    output on it, and the raw RS_Rating Series (indexed by symbol) for
    looking up any individual ticker's own rating.
    """
    truncated_universe = {symbol: _truncate(history, as_of_date) for symbol, history in universe_histories.items()}
    rs_ratings = compute_rs_ratings(truncated_universe)

    rows = []
    for symbol, history in truncated_universe.items():
        rows.append({
            "Symbol": symbol,
            "Sector": sector_map.get_sector(symbol),
            "RS_Rating": rs_ratings["RS_Rating"].get(symbol) if not rs_ratings.empty else None,
            "Trend_State": _trend_state_of_truncated(history),
        })

    scored_universe = pd.DataFrame(rows)
    sector_ranking = rank_sectors(scored_universe)

    return scored_universe, sector_ranking, rs_ratings["RS_Rating"] if not rs_ratings.empty else pd.Series(dtype=float)


def replay_decision_as_of(
    ticker: str,
    as_of_date: pd.Timestamp,
    full_history: pd.DataFrame,
    benchmark_history: pd.DataFrame,
    universe_histories: dict,
    vix_history: pd.DataFrame | None,
    precomputed_universe_scoring: tuple | None = None,
) -> dict:
    """
    Truncates full_history to rows <= as_of_date, re-runs the full
    detection chain against that truncated view ONLY, then produces
    exactly the output contract leadership_decision_engine.categorize()
    already returns (category, confidence_score, entry, stop_loss,
    target, market_regime_verdict, sector_health_verdict, ...).

    Parameters
    ----------
    ticker : the symbol being replayed.
    as_of_date : the historical date to reconstruct the decision for.
    full_history : this ticker's full OHLCV(+indicator) history --
        should be the same object as universe_histories[ticker].
    benchmark_history : NIFTY 50 full history (scoring.benchmark.get_benchmark_history()),
        truncated the same way for distribution-day counting.
    universe_histories : dict[symbol -> full OHLCV history] for every
        ticker in the tracked Leadership universe, including `ticker`
        itself -- needed because RS Rating is a percentile rank against
        the whole universe, not this ticker in isolation.
    vix_history : scoring.market_regime.get_vix_history()'s output. No
        longer read for the regime verdict itself (trend-based now, see
        module docstring) -- kept in the signature since it's still
        fetched by callers and may back a future stop-loss-width use.
    precomputed_universe_scoring : optional (scored_universe, sector_ranking,
        rs_ratings) tuple from build_scored_universe_as_of(), so callers
        replaying many tickers at the same as_of_date don't each
        redundantly recompute the whole universe's RS ratings. Computed
        internally if not given.

    Returns
    -------
    dict : leadership_decision_engine.categorize()'s output contract, or
    a category="NO_DATA" sentinel if there isn't enough truncated history
    yet to run detection at all.
    """
    truncated_target = _truncate(full_history, as_of_date)

    if len(truncated_target) < MIN_HISTORY_ROWS:
        return {"symbol": ticker, "as_of_date": as_of_date, **NO_DATA_RESULT_TEMPLATE}

    # 1. Indicators computed fresh against ONLY the truncated view -- the
    # actual lookahead-bias guard. An indicator computed against the full
    # history would leak future values into its own trailing windows.
    enriched = indicator_calculator.calculate(truncated_target)
    enriched = calculate_relative_volume(enriched)

    # 2. All 5 pattern detectors + market structure, via the exact same
    # chain execute_pipeline() runs live (see analyze_ticker()'s own
    # docstring for why this must be the identical function).
    analysis = analyze_ticker(enriched)

    pattern_row = {
        **enriched.iloc[-1].to_dict(),
        **build_pattern_row_fields(analysis),
        "Delivery_Pct_20d_avg": (
            enriched["Delivery_Pct"].rolling(window=20).mean().iloc[-1]
            if "Delivery_Pct" in enriched.columns else None
        ),
    }

    # 3. Market regime -- NIFTY's own Trend_State (trend-based, not VIX-based;
    # see get_market_regime_verdict()'s own docstring for why VIX was
    # replaced) plus distribution days, truncated the same way. vix_history
    # is no longer used for the regime verdict itself -- kept as a
    # parameter for now since it's still fetched by callers and may back a
    # future stop-loss-width use, per the redesign's own scope note.
    truncated_benchmark = _truncate(benchmark_history, as_of_date)
    distribution_days = count_distribution_days(truncated_benchmark)
    nifty_trend_state = _trend_state_of_truncated(truncated_benchmark)

    if nifty_trend_state != "UNKNOWN" and distribution_days is not None:
        market_verdict = get_market_regime_verdict(nifty_trend_state, distribution_days)
    else:
        # Conservative default when regime can't be determined for this
        # date (too little benchmark history) rather than silently
        # defaulting to FAVORABLE -- same fail-closed philosophy as the
        # live path's missing-fundamentals handling, applied here to
        # missing-regime-data instead.
        market_verdict = "UNFAVORABLE"

    # 4. Scoring -- RS Rating + sector breadth, from the whole truncated
    # universe (see build_scored_universe_as_of's own docstring).
    if precomputed_universe_scoring is not None:
        scored_universe, sector_ranking, rs_ratings = precomputed_universe_scoring
    else:
        scored_universe, sector_ranking, rs_ratings = build_scored_universe_as_of(as_of_date, universe_histories)

    ticker_sector = sector_map.get_sector(ticker)

    if ticker_sector in sector_ranking.index:
        sector_row = assemble_sector_row(sector_ranking, ticker_sector)
    else:
        # Sector has no valid RS_Rating entries yet this early in the
        # replay period (rank_sectors() drops those) -- a neutral,
        # honestly-unknown sector row rather than a crash or a fabricated
        # STRONG/WEAK verdict.
        sector_row = {"Avg_RS_Rating": 0.0, "Pct_Uptrend": 0.0, "Rank": None, "Total_Sectors": len(sector_ranking)}

    scoring_row = {
        "Rel_Vol": pattern_row.get("Rel_Vol"),
        "RS_Rating": rs_ratings.get(ticker),
        "Sector": ticker_sector,
    }

    # 5. candidate_assembler + leadership_decision_engine, called exactly
    # as they would be live -- fundamentals deliberately empty/disabled
    # per this module's scope decision (see module docstring). enriched
    # is the truncated, indicator-computed history already built in step
    # 1 -- passed through so MACD signal detection sees the same
    # trailing Close/MACD_Hist bars a live scan would, not just today's
    # single flattened row.
    candidate = assemble_candidate(
        pattern_row, fundamentals={}, scoring_row=scoring_row, symbol=ticker, pattern_history_df=enriched,
    )
    pattern_details = assemble_pattern_details(pattern_row)

    return categorize(
        candidate, sector_row, market_verdict,
        pattern_details=pattern_details,
        disable_fundamental_signals=True,
    )
