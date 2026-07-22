"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : scoring_engine.py
Package     : Scoring

Purpose
-------
Orchestrates the Scoring package into one scored row per ticker: RS Rating,
RS vs Nifty (2M/6M/12M), Relative Volume, and Sector. Backs both the
candidate table's RS columns and the Sector RS Ranking aggregation.

Mirrors the existing Loader -> Validator -> Processor -> Exporter -> Engine
convention used in market_data/ and technical_analysis/: this is the Engine,
the other scoring/ modules are the Processor-equivalents it calls.

===============================================================================
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from config import PATTERN_DATA_FOLDER

from common.logger import get_logger
from market_data.cache_manager import cache_manager

from scoring.exceptions import ScoringError
from scoring.universe import get_universe
from scoring.sector_map import sector_map, UNKNOWN_SECTOR
from scoring.relative_strength import compute_rs_ratings
from scoring.relative_volume import calculate as calculate_rvol
from scoring.benchmark import get_benchmark_history
from scoring.sector_indices import get_sector_index_history, get_sector_index_trend
from scoring.sector_index_rs import compute_sector_index_rs

logger = get_logger(__name__)

RS_COLUMNS = ["RS_Rating", "RS_2M", "RS_6M", "RS_12M"]

# Buffer for compute_sector_index_rs()'s 12-month return window --
# confirmed empirically (tests/backtesting/test_replay_engine.py's own
# comment) that compute_returns() needs strictly more than 252 trading
# days of history for RS_12M to resolve, not exactly 365 calendar days.
SECTOR_INDEX_LOOKBACK_DAYS = 400


class ScoringEngine:
    """
    Produces one scored row per ticker for the candidate table and sector
    ranking panels.
    """

    def __init__(self) -> None:

        # Last universe-wide RS ratings computed by score_universe(), keyed
        # by symbol. Lets score_ticker() reuse a real percentile context
        # instead of ranking a ticker against itself.
        self._rs_cache: Optional[pd.DataFrame] = None

        # Last universe-wide sector-index trend (UPTREND/DOWNTREND/CHOPPY),
        # keyed by Sector label -- computed once alongside _rs_cache since
        # both need the same sector_index_histories fetch, reused by
        # score_universe()'s per-row loop so ui/sector_ranking_panel.py
        # doesn't need its own separate fetch.
        self._sector_trend_cache: Dict[str, str] = {}

    # ------------------------------------------------------------------ #

    def _load_price_history(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Loads the richest available price history for a symbol: the
        pattern-enriched dataset first, falling back to raw OHLCV cache.
        """

        pattern_path = Path(PATTERN_DATA_FOLDER) / f"{symbol}.parquet"

        if pattern_path.exists():

            try:
                return pd.read_parquet(pattern_path)
            except Exception as ex:
                logger.warning("Failed loading pattern data for %s: %s", symbol, ex)

        if cache_manager.exists(symbol):

            try:
                return cache_manager.load(symbol)
            except Exception as ex:
                logger.warning("Failed loading raw cache for %s: %s", symbol, ex)

        return None

    # ------------------------------------------------------------------ #

    def score_ticker(self, ticker: str, technical_df: pd.DataFrame) -> dict:
        """
        Scores a single ticker.

        RS columns reuse the percentile context from the most recent
        score_universe() call when available; otherwise they're computed
        against this ticker alone (a degenerate single-member universe).

        Parameters
        ----------
        ticker : str
        technical_df : pd.DataFrame
            OHLCV (+ indicators) history for this ticker.

        Returns
        -------
        dict
            RS_Rating, RS_2M, RS_6M, RS_12M, Rel_Vol, Sector.
        """

        try:

            if self._rs_cache is not None and ticker in self._rs_cache.index:
                rs_row = self._rs_cache.loc[ticker]
            else:
                rs_row = (
                    compute_rs_ratings({ticker: technical_df})
                    .reindex([ticker])
                    .iloc[0]
                )

            rel_vol = float("nan")

            if technical_df is not None and not technical_df.empty:
                rvol_df = calculate_rvol(technical_df)
                if not rvol_df.empty:
                    rel_vol = rvol_df["Rel_Vol"].iloc[-1]

            sector = sector_map.get_sector(ticker)

            return {
                "RS_Rating": rs_row.get("RS_Rating"),
                "RS_2M": rs_row.get("RS_2M"),
                "RS_6M": rs_row.get("RS_6M"),
                "RS_12M": rs_row.get("RS_12M"),
                "Rel_Vol": rel_vol,
                "Sector": sector,
            }

        except Exception as ex:

            raise ScoringError(f"Failed scoring {ticker}: {ex}") from ex

    # ------------------------------------------------------------------ #

    def _compute_rs_and_sector_trends(
        self, price_data: Dict[str, pd.DataFrame], sector_map_data: Dict[str, str]
    ) -> pd.DataFrame:
        """
        Sector-index-anchored RS Rating (scoring.sector_index_rs.compute_sector_index_rs()),
        matching backtesting/replay_engine.py's build_scored_universe_as_of()
        -- the same methodology now feeds both the live candidate grid and
        decision_engine.leadership_decision_engine.categorize()'s score,
        replacing the old small-universe peer-percentile rank
        (scoring.relative_strength.compute_rs_ratings(), still used
        internally as compute_sector_index_rs()'s own graceful fallback for
        an unresolvable sector).

        Also populates self._sector_trend_cache (Sector -> UPTREND/
        DOWNTREND/CHOPPY via scoring.sector_indices.get_sector_index_trend()),
        computed from the same sector_index_histories fetch so callers
        needing both (score_universe()'s own per-row loop, and any future
        caller) don't each fetch it separately.

        Falls back to the plain compute_rs_ratings() -- and an empty
        _sector_trend_cache -- on any fetch failure (benchmark or
        sector-index data unavailable, e.g. no network): compute_sector_index_rs()
        itself already degrades to that same fallback per-ticker for an
        unresolvable sector, so failing this whole enrichment closed here
        is consistent with that, not a new failure mode.
        """
        try:
            benchmark_history = get_benchmark_history()

            distinct_sectors = {s for s in sector_map_data.values() if s and s != UNKNOWN_SECTOR}
            to_date = date.today()
            from_date = to_date - timedelta(days=SECTOR_INDEX_LOOKBACK_DAYS)

            sector_index_histories: Dict[str, pd.DataFrame] = {}
            for sector in distinct_sectors:
                history = get_sector_index_history(
                    sector,
                    from_date=from_date.strftime("%d-%m-%Y"),
                    to_date=to_date.strftime("%d-%m-%Y"),
                )
                if history is not None:
                    sector_index_histories[sector] = history

            self._sector_trend_cache = {
                sector: get_sector_index_trend(sector, to_date, sector_index_histories)
                for sector in distinct_sectors
            }

            return compute_sector_index_rs(price_data, sector_map_data, benchmark_history, sector_index_histories)

        except Exception as ex:

            logger.warning(
                "Sector-index RS computation failed, falling back to peer-percentile RS: %s", ex
            )
            self._sector_trend_cache = {}
            return compute_rs_ratings(price_data)

    # ------------------------------------------------------------------ #

    def score_universe(self, symbols: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Scores every ticker in the comparison universe.

        Parameters
        ----------
        symbols : Optional[List[str]]
            Explicit ticker list. Defaults to scoring.universe.get_universe().

        Returns
        -------
        pd.DataFrame
            One row per ticker: Symbol, RS_Rating, RS_2M, RS_6M, RS_12M,
            Rel_Vol, Sector, Sector_Index_Trend.
        """

        empty_result = pd.DataFrame(
            columns=["Symbol"] + RS_COLUMNS + ["Rel_Vol", "Sector", "Sector_Index_Trend"]
        )

        try:

            universe = symbols if symbols is not None else get_universe()

            if not universe:
                logger.warning("Comparison universe is empty; nothing to score.")
                return empty_result

            price_data: Dict[str, pd.DataFrame] = {}

            for symbol in universe:

                history = self._load_price_history(symbol)

                if history is not None and not history.empty:
                    price_data[symbol] = history

            if not price_data:
                logger.warning("No loadable price history for the universe.")
                return empty_result

            sector_map_data = {symbol: sector_map.get_sector(symbol) for symbol in price_data}
            self._rs_cache = self._compute_rs_and_sector_trends(price_data, sector_map_data)

            rows = []

            for symbol, history in price_data.items():

                try:
                    row = self.score_ticker(symbol, history)
                    row["Symbol"] = symbol
                    row["Sector_Index_Trend"] = self._sector_trend_cache.get(row["Sector"])
                    rows.append(row)

                except Exception as ex:
                    logger.exception("Skipping %s: %s", symbol, ex)

            logger.info(
                "Scored %d/%d universe tickers.",
                len(rows),
                len(universe),
            )

            if not rows:
                return empty_result

            result = pd.DataFrame(rows)

            return result[["Symbol"] + RS_COLUMNS + ["Rel_Vol", "Sector", "Sector_Index_Trend"]]

        except Exception as ex:

            raise ScoringError(str(ex)) from ex


scoring_engine = ScoringEngine()
