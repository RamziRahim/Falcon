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

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from config import PATTERN_DATA_FOLDER

from common.logger import get_logger
from market_data.cache_manager import cache_manager

from scoring.exceptions import ScoringError
from scoring.universe import get_universe
from scoring.sector_map import sector_map
from scoring.relative_strength import compute_rs_ratings
from scoring.relative_volume import calculate as calculate_rvol

logger = get_logger(__name__)

RS_COLUMNS = ["RS_Rating", "RS_2M", "RS_6M", "RS_12M"]


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
            Rel_Vol, Sector.
        """

        empty_result = pd.DataFrame(
            columns=["Symbol"] + RS_COLUMNS + ["Rel_Vol", "Sector"]
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

            self._rs_cache = compute_rs_ratings(price_data)

            rows = []

            for symbol, history in price_data.items():

                try:
                    row = self.score_ticker(symbol, history)
                    row["Symbol"] = symbol
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

            return result[["Symbol"] + RS_COLUMNS + ["Rel_Vol", "Sector"]]

        except Exception as ex:

            raise ScoringError(str(ex)) from ex


scoring_engine = ScoringEngine()
