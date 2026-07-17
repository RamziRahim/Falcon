"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Script      : test_scoring_relative_strength.py
Package     : Tests

Purpose
-------
Verifies the percentile-rank math in scoring/relative_strength.py against a
small synthetic dataset. Percentile ranking is easy to get subtly wrong in
two specific ways:

1. Direction reversed (a *lower* return incorrectly producing a *higher*
   rank).
2. Ranking against the wrong universe subset (a ticker with insufficient
   history polluting or being incorrectly included in the ranked set instead
   of being excluded as NaN).

Usage
-----
Open this file in VS Code and press F5 to execute.
===============================================================================
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from common.logger import get_logger
from scoring.relative_strength import (
    compute_returns,
    compute_rs_ratings,
    percentile_rank,
    WINDOW_12M,
)

logger = get_logger(__name__)


def _flat_growth_frame(daily_return: float, periods: int = 320) -> pd.DataFrame:
    """
    Builds a deterministic, monotonically-growing (or shrinking) price series
    so expected return ordering is unambiguous.
    """

    dates = pd.date_range("2024-01-01", periods=periods, freq="D")
    close = 100.0 * ((1.0 + daily_return) ** np.arange(periods))

    return pd.DataFrame({
        "Date": dates,
        "Close": close,
        "Volume": 100_000,
    })


def test_percentile_rank_direction() -> None:
    """
    Higher raw return must map to a strictly higher percentile rank.
    """

    returns = pd.Series({"WORST": -0.10, "MID": 0.02, "BEST": 0.30})

    ranked = percentile_rank(returns)

    assert ranked["WORST"] < ranked["MID"] < ranked["BEST"], (
        f"Percentile rank direction is reversed: {ranked.to_dict()}"
    )

    # The top performer's percentile is always exactly 1.0 (rank/n == n/n),
    # so it must land exactly on the 99 ceiling regardless of universe size.
    assert ranked["BEST"] == 99, f"Top performer should rate 99, got {ranked['BEST']}"

    logger.info("test_percentile_rank_direction passed: %s", ranked.to_dict())


def test_percentile_rank_excludes_missing_values() -> None:
    """
    A NaN input must stay NaN in the output and must not be silently ranked
    (e.g. treated as zero or as the lowest value).
    """

    returns = pd.Series({"A": 0.05, "B": np.nan, "C": 0.15})

    ranked = percentile_rank(returns)

    assert pd.isna(ranked["B"]), f"Missing input should remain NaN, got {ranked['B']}"
    assert ranked["C"] > ranked["A"], "Higher return should still outrank lower return"

    logger.info("test_percentile_rank_excludes_missing_values passed: %s", ranked.to_dict())


def test_compute_returns_flags_insufficient_history() -> None:
    """
    A ticker with fewer rows than the lookback window must report NaN for
    that window rather than an out-of-bounds or fabricated value.
    """

    short_history = _flat_growth_frame(0.001, periods=WINDOW_12M - 10)
    long_history = _flat_growth_frame(0.001, periods=WINDOW_12M + 10)

    returns = compute_returns({"SHORT": short_history, "LONG": long_history})

    assert pd.isna(returns.loc["SHORT", "Return_12M"]), (
        "Ticker with insufficient history must report NaN for that window"
    )
    assert not pd.isna(returns.loc["LONG", "Return_12M"]), (
        "Ticker with sufficient history must report a real 12M return"
    )

    logger.info("test_compute_returns_flags_insufficient_history passed.")


def test_compute_rs_ratings_ranks_against_correct_universe() -> None:
    """
    RS_Rating must rank tickers relative to the full universe passed in, and
    a ticker lacking enough history for the composite window must be excluded
    (NaN) rather than being force-ranked against a subset it can't belong to.
    """

    universe = {
        "LAGGARD": _flat_growth_frame(0.0000, periods=WINDOW_12M + 10),
        "MIDDLE": _flat_growth_frame(0.0010, periods=WINDOW_12M + 10),
        "LEADER": _flat_growth_frame(0.0030, periods=WINDOW_12M + 10),
        "TOO_SHORT": _flat_growth_frame(0.0050, periods=WINDOW_12M - 10),
    }

    ratings = compute_rs_ratings(universe)

    assert ratings.loc["LAGGARD", "RS_Rating"] < ratings.loc["MIDDLE", "RS_Rating"], (
        "Laggard must rank below middle performer"
    )
    assert ratings.loc["MIDDLE", "RS_Rating"] < ratings.loc["LEADER", "RS_Rating"], (
        "Middle performer must rank below leader"
    )
    assert pd.isna(ratings.loc["TOO_SHORT", "RS_Rating"]), (
        "Ticker without enough history for the composite window must be excluded, not ranked"
    )

    logger.info(
        "test_compute_rs_ratings_ranks_against_correct_universe passed: %s",
        ratings["RS_Rating"].to_dict(),
    )


def run_all() -> None:
    logger.info("==================================================")
    logger.info("Running scoring/relative_strength.py percentile-rank tests")
    logger.info("==================================================")

    test_percentile_rank_direction()
    test_percentile_rank_excludes_missing_values()
    test_compute_returns_flags_insufficient_history()
    test_compute_rs_ratings_ranks_against_correct_universe()

    logger.info("==================================================")
    logger.info("All scoring/relative_strength.py tests passed.")
    logger.info("==================================================")


if __name__ == "__main__":
    run_all()
