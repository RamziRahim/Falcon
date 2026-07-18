"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : sector_rotation.py
Package     : Scoring

Purpose
-------
Phase 1 (shipped): Sector RS Ranking — averages each sector's member RS
Rating and ranks sectors by that average. Backs the "Sector RS Ranking
(1 Month)" bar chart.

Phase 2 (deferred): full Relative Rotation Graph (RRG). Real, specific
methodology (Julius de Kempenaer's) that is meaningfully harder to get
*correct* — a wrong RRG actively misleads rather than just being incomplete.
Do not attempt until Phase 1 is live and validated against real data.

===============================================================================
"""

from __future__ import annotations

import pandas as pd

from common.logger import get_logger
from scoring.exceptions import SectorRotationError

logger = get_logger(__name__)

REQUIRED_COLUMNS = {"Sector", "RS_Rating"}


def rank_sectors(scored_universe: pd.DataFrame) -> pd.DataFrame:
    """
    Averages composite RS Rating per sector and ranks sectors by that average.

    Parameters
    ----------
    scored_universe : pd.DataFrame
        One row per ticker, must contain 'Sector' and 'RS_Rating' columns —
        as produced by scoring_engine.ScoringEngine.score_universe().

    Returns
    -------
    pd.DataFrame
        Indexed by Sector, columns: Avg_RS_Rating, Ticker_Count, Rank
        (Rank 1 = strongest sector), sorted by Rank ascending.
    """

    empty_result = pd.DataFrame(
        columns=["Avg_RS_Rating", "Ticker_Count", "Rank", "Pct_Uptrend"]
    )

    try:

        if scored_universe.empty or not REQUIRED_COLUMNS.issubset(scored_universe.columns):
            return empty_result

        working = scored_universe.dropna(subset=["RS_Rating", "Sector"])

        if working.empty:
            return empty_result

        grouped = working.groupby("Sector")["RS_Rating"].agg(["mean", "count"])
        grouped.columns = ["Avg_RS_Rating", "Ticker_Count"]

        grouped = grouped.sort_values("Avg_RS_Rating", ascending=False)
        grouped["Rank"] = range(1, len(grouped) + 1)

        # Breadth alongside the existing magnitude-based ranking:
        # Avg_RS_Rating measures average momentum *strength*, Pct_Uptrend
        # measures *breadth of participation* -- a sector can have one very
        # strong stock (high avg RS) while only a fraction of its names are
        # actually trending up. Both together are more informative than
        # either alone. Computed from the full scored_universe (not
        # `working`, which is filtered to rows with valid RS_Rating) so a
        # ticker missing RS data but with a known Trend_State still counts
        # toward its sector's breadth.
        if "Trend_State" in scored_universe.columns:

            valid = scored_universe.dropna(subset=["Sector", "Trend_State"])

            uptrend_pct = (
                valid.assign(is_uptrend=valid["Trend_State"] == "UPTREND")
                .groupby("Sector")["is_uptrend"]
                .mean() * 100
            ).round(1)

            grouped["Pct_Uptrend"] = grouped.index.map(uptrend_pct).fillna(0.0)

        else:

            grouped["Pct_Uptrend"] = 0.0

        logger.info(
            "Ranked %d sectors from %d tickers.",
            len(grouped),
            len(working),
        )

        return grouped

    except Exception as ex:

        raise SectorRotationError(str(ex)) from ex


def compute_rrg(*args, **kwargs):
    """
    Phase 2 (deferred): full Relative Rotation Graph.

    Needs: (1) a daily equal-weighted sector price index normalized to a base
    value, (2) JdK RS-Ratio — sector index / benchmark.py's index, EMA-smoothed
    then re-normalized to mean 100, (3) JdK RS-Momentum — rate of change of the
    RS-Ratio, similarly smoothed/normalized, (4) each sector's last N days of
    (RS-Ratio, RS-Momentum) plotted as a quadrant-scatter tail
    (Leading / Weakening / Lagging / Improving).

    Not implemented: getting the smoothing/normalization constants wrong
    produces a plausible-looking but incorrect chart, which is worse than not
    having one. Validate against a known public RRG (e.g. stockcharts.com)
    once implemented.
    """

    raise NotImplementedError(
        "RRG (Phase 2) is deferred until Sector RS Ranking (Phase 1) is validated."
    )
