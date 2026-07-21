"""
===============================================================================
Falcon AI Swing Trading Platform — Sector-Index-Anchored RS Rating
===============================================================================
Script      : sector_index_rs.py
Package     : Scoring

Replaces the small-universe percentile-rank RS Rating (compute_rs_ratings()
in relative_strength.py -- a stock's return ranked against ~100-167
tracked peer tickers, biased by sample composition) with a multi-factor
relative strength anchored to real market benchmarks: the stock's own
sector index (e.g. NIFTY IT) and NIFTY 50 itself, not peer returns.

Reuses relative_strength.py's WINDOW_2M/3M/6M/9M/12M and WEIGHT_3M/6M/9M/12M
constants and compute_returns()/percentile_rank() functions directly --
only the underlying return comparison changes (vs. index instead of vs.
peers); the weighting and percentile-ranking logic is unchanged, per the
spec's own instruction not to redefine what already exists.

get_sector_index_history() / SECTOR_INDEX_MAP already exist in
scoring/sector_indices.py (built for the market-regime redesign's sector
trend signal) -- reused here rather than duplicated, since both this
module and that one need the identical sector-name-to-index-name mapping
and the identical NSE fetch.

-------------------------------------------------------------------------
Real bug found and fixed, not implemented as literally given
-------------------------------------------------------------------------
The originally proposed formula was a RATIO:
    RS_vs_Sector = (stock_return / sector_index_return) - 1
This is mathematically unsound whenever either return is negative --
verified directly with concrete numbers before writing this module, not
assumed: a stock returning +5% against a sector returning -10% (a stock
CLEARLY outperforming a declining sector) produces RS = -1.5 under the
ratio formula -- a strongly NEGATIVE score for what should be a strongly
POSITIVE outperformance signal. Negative returns over a 3/6/9/12-month
window are routine in real markets (any correction or drawdown), so this
isn't an edge case -- it would systematically misrank genuinely
outperforming stocks during any market weakness, exactly the condition
this Leadership screen most needs to get right.

Fixed by using the standard subtractive excess-return form instead
(stock_return minus benchmark_return, in percentage-point terms) -- the
same methodology real relative-strength research uses, sign-safe
regardless of whether either return is positive or negative:
    RS_vs_Sector = stock_return - sector_index_return
    RS_vs_Market = stock_return - nifty50_return
    Composite_RS = (RS_vs_Sector * 0.6) + (RS_vs_Market * 0.4)
Same 60/40 weighting intent as originally specified (sector comparison
weighted higher -- more specific, more actionable; market comparison
prevents a stock in a weak sector from looking great only because
everything around it is worse), just computed on excess return instead
of a return ratio. Weights are starting points, not backtested, same
caveat as everywhere else in this project.
===============================================================================
"""
from __future__ import annotations

import pandas as pd

from scoring.relative_strength import (
    WEIGHT_3M, WEIGHT_6M, WEIGHT_9M, WEIGHT_12M,
    compute_returns, compute_rs_ratings, percentile_rank,
)
from scoring.sector_indices import get_sector_index_history  # noqa: F401 -- re-exported for callers

SECTOR_RS_WEIGHT = 0.6
MARKET_RS_WEIGHT = 0.4

NIFTY50_KEY = "__NIFTY50__"  # internal-only key, never a real ticker symbol


def _weighted_returns(returns: pd.DataFrame) -> pd.Series:
    """Same composite blend compute_rs_ratings() uses -- reusing the
    existing WEIGHT_3M/6M/9M/12M constants directly, not redefining them."""
    return (
        returns["Return_3M"] * WEIGHT_3M
        + returns["Return_6M"] * WEIGHT_6M
        + returns["Return_9M"] * WEIGHT_9M
        + returns["Return_12M"] * WEIGHT_12M
    )


def compute_sector_index_rs(
    price_dataframes: dict,
    sector_map_data: dict,
    nifty50_history: pd.DataFrame,
    sector_index_cache: dict,
) -> pd.DataFrame:
    """
    Returns the same output shape as compute_rs_ratings() -- indexed by
    symbol, columns RS_Rating / RS_2M / RS_6M / RS_12M -- so the rest of
    the pipeline (candidate_assembler, decision engine, UI) requires zero
    changes.

    Parameters
    ----------
    price_dataframes : dict[symbol -> OHLCV history], same shape
        compute_rs_ratings() takes.
    sector_map_data : dict[symbol -> Sector label] (scoring.sector_map.sector_map.get_sector()'s
        output, precomputed by the caller so this function makes no
        lookups of its own).
    nifty50_history : NIFTY 50's own OHLCV history (scoring.benchmark.get_benchmark_history()).
    sector_index_cache : dict[Sector label -> sector index OHLCV history],
        pre-fetched by the caller via scoring.sector_indices.get_sector_index_history()
        for whichever sectors are actually present in sector_map_data --
        mirrors the history_cache pattern already used by
        scoring.sector_indices.get_sector_index_trend().

    For any ticker whose sector index can't be resolved (Unknown sector,
    sector missing from sector_index_cache, or insufficient history to
    compute a return) this falls back to the ordinary peer-percentile
    RS_Rating (compute_rs_ratings(), computed once up front for the whole
    universe) rather than returning None or NaN -- degrades gracefully,
    doesn't break the whole run. RS_2M/RS_6M/RS_12M are always the
    peer-percentile values -- only the composite RS_Rating gets the
    sector/market-anchored treatment.
    """
    fallback_ratings = compute_rs_ratings(price_dataframes)

    if not price_dataframes:
        return fallback_ratings

    stock_returns = compute_returns(price_dataframes)
    stock_weighted_return = _weighted_returns(stock_returns)

    nifty_returns = compute_returns({NIFTY50_KEY: nifty50_history})
    nifty_weighted_return = (
        _weighted_returns(nifty_returns).iloc[0] if not nifty_returns.empty else float("nan")
    )

    sector_returns = compute_returns(sector_index_cache) if sector_index_cache else pd.DataFrame()
    sector_weighted_return = _weighted_returns(sector_returns) if not sector_returns.empty else pd.Series(dtype=float)

    composite_rs = pd.Series(index=list(price_dataframes.keys()), dtype=float)

    for symbol in price_dataframes:
        stock_return = stock_weighted_return.get(symbol)
        sector = sector_map_data.get(symbol)
        sector_return = sector_weighted_return.get(sector) if sector is not None else None

        resolvable = (
            stock_return is not None and not pd.isna(stock_return)
            and sector_return is not None and not pd.isna(sector_return)
            and not pd.isna(nifty_weighted_return)
        )

        if not resolvable:
            continue  # left NaN -- filled from fallback_ratings below

        rs_vs_sector = stock_return - sector_return
        rs_vs_market = stock_return - nifty_weighted_return
        composite_rs[symbol] = (rs_vs_sector * SECTOR_RS_WEIGHT) + (rs_vs_market * MARKET_RS_WEIGHT)

    composite_rating = percentile_rank(composite_rs)

    result = pd.DataFrame(index=list(price_dataframes.keys()))
    result["RS_Rating"] = composite_rating.combine_first(fallback_ratings["RS_Rating"])
    result["RS_2M"] = fallback_ratings["RS_2M"]
    result["RS_6M"] = fallback_ratings["RS_6M"]
    result["RS_12M"] = fallback_ratings["RS_12M"]

    return result
