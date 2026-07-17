"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : relative_strength.py
Package     : Scoring

Purpose
-------
Computes IBD-style Relative Strength ratings:

• Composite RS Rating   — weighted blend of 3/6/9/12-month returns,
                           percentile-ranked against the universe (1-99).
• RS vs Nifty 2M/6M/12M  — raw single-window return, independently
                           percentile-ranked against the universe (1-99).

Design note
-----------
"RS vs Nifty" is standard trader shorthand for "percentile rank of relative
performance against the tracked universe" — not literally
`stock_return - nifty_return`. This module ranks purely against the universe
(scoring/universe.py); it does not subtract benchmark.py's index return. The
benchmark is used elsewhere (sector_rotation.py Phase 2 / RRG), which is the
module that genuinely needs a single reference series to rotate against.

Return windows are expressed in trading days (matching config.py's existing
RS_3M/RS_6M/RS_12M convention) rather than calendar days, so no benchmark
calendar alignment is required here.

===============================================================================
"""

from __future__ import annotations

from typing import Dict

import pandas as pd

from config import CLOSE_COLUMN, DATE_COLUMN, RS_3M, RS_6M, RS_12M

from common.logger import get_logger
from scoring.exceptions import RelativeStrengthError

logger = get_logger(__name__)

# ------------------------------------------------------------------ #
# Windows (trading days)
# ------------------------------------------------------------------ #

WINDOW_2M = 42
WINDOW_3M = RS_3M
WINDOW_6M = RS_6M
WINDOW_9M = 189
WINDOW_12M = RS_12M

# ------------------------------------------------------------------ #
# Composite RS Rating weights (IBD-style: most recent quarter double-weighted)
# ------------------------------------------------------------------ #

WEIGHT_3M = 0.4
WEIGHT_6M = 0.2
WEIGHT_9M = 0.2
WEIGHT_12M = 0.2

MIN_RATING = 1
MAX_RATING = 99


def _window_return(dataframe: pd.DataFrame, window: int) -> float:
    """
    Raw price return over `window` trading days, ending at the latest row.
    """

    if dataframe is None or dataframe.empty or CLOSE_COLUMN not in dataframe.columns:
        return float("nan")

    close = dataframe[CLOSE_COLUMN].dropna()

    if len(close) <= window:
        return float("nan")

    price_now = close.iloc[-1]
    price_then = close.iloc[-(window + 1)]

    if price_then == 0:
        return float("nan")

    return (price_now / price_then) - 1.0


def compute_returns(price_dataframes: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Computes raw window returns per symbol.

    Parameters
    ----------
    price_dataframes : Dict[str, pd.DataFrame]
        Mapping of symbol -> OHLCV dataframe (must contain 'Close'),
        sorted ascending by date.

    Returns
    -------
    pd.DataFrame
        Indexed by symbol, columns: Return_2M, Return_3M, Return_6M,
        Return_9M, Return_12M.
    """

    try:

        rows = {}

        for symbol, df in price_dataframes.items():

            ordered = df

            if DATE_COLUMN in df.columns:
                ordered = df.sort_values(DATE_COLUMN)

            rows[symbol] = {
                "Return_2M": _window_return(ordered, WINDOW_2M),
                "Return_3M": _window_return(ordered, WINDOW_3M),
                "Return_6M": _window_return(ordered, WINDOW_6M),
                "Return_9M": _window_return(ordered, WINDOW_9M),
                "Return_12M": _window_return(ordered, WINDOW_12M),
            }

        return pd.DataFrame.from_dict(rows, orient="index")

    except Exception as ex:

        raise RelativeStrengthError(str(ex)) from ex


def percentile_rank(series: pd.Series) -> pd.Series:
    """
    IBD-style 1-99 percentile rank. Higher raw value => higher rank.
    Entries with missing input remain NaN (excluded from the universe rank).
    """

    valid = series.dropna()

    if valid.empty:
        return pd.Series(index=series.index, dtype=float)

    pct = valid.rank(pct=True, method="average")

    rating = (pct * (MAX_RATING - MIN_RATING) + MIN_RATING).round()

    return rating.reindex(series.index)


def compute_rs_ratings(price_dataframes: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Computes composite RS Rating + per-window RS vs Nifty ratings for a universe.

    Parameters
    ----------
    price_dataframes : Dict[str, pd.DataFrame]
        Mapping of symbol -> OHLCV dataframe for every ticker in the
        comparison universe (see scoring/universe.py).

    Returns
    -------
    pd.DataFrame
        Indexed by symbol, columns: RS_Rating, RS_2M, RS_6M, RS_12M.
    """

    try:

        returns = compute_returns(price_dataframes)

        if returns.empty:
            return pd.DataFrame(
                columns=["RS_Rating", "RS_2M", "RS_6M", "RS_12M"]
            )

        weighted_return = (
            returns["Return_3M"] * WEIGHT_3M
            + returns["Return_6M"] * WEIGHT_6M
            + returns["Return_9M"] * WEIGHT_9M
            + returns["Return_12M"] * WEIGHT_12M
        )

        result = pd.DataFrame(index=returns.index)

        result["RS_Rating"] = percentile_rank(weighted_return)
        result["RS_2M"] = percentile_rank(returns["Return_2M"])
        result["RS_6M"] = percentile_rank(returns["Return_6M"])
        result["RS_12M"] = percentile_rank(returns["Return_12M"])

        logger.info(
            "Computed RS ratings for %d/%d tickers.",
            result["RS_Rating"].notna().sum(),
            len(result),
        )

        return result

    except Exception as ex:

        raise RelativeStrengthError(str(ex)) from ex
