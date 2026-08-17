"""
Integration tests for scoring/scoring_engine.py — matches the real
ScoringEngine class (score_ticker / score_universe using an internal
_rs_cache), not the flat function assumed pre-implementation.
"""
from __future__ import annotations

import pandas as pd
import pytest

from scoring.scoring_engine import ScoringEngine
from scoring.relative_strength import compute_rs_ratings

EXPECTED_ROW_KEYS = {"RS_Rating", "RS_2M", "RS_6M", "RS_12M", "Rel_Vol", "Sector"}


def _index_history(n_days: int = 400) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=n_days, freq="D")
    return pd.DataFrame({
        "Date": dates, "Open": 100.0, "High": 101.0, "Low": 99.0,
        "Close": pd.Series(range(n_days), dtype=float) + 100.0, "Volume": 1_000_000,
    })


class TestSectorIndexRSEnrichmentReachesRealPath:
    """Regression test for a real bug: _compute_rs_and_sector_trends() passed
    a raw datetime.date (date.today()) to get_sector_index_trend(), which
    compares it against a datetime64[ns] column -- pandas raises
    "Invalid comparison between dtype=datetime64[ns] and date" on that,
    silently caught by this method's own except block, so the sector-index
    enrichment (and _sector_trend_cache) ALWAYS fell back to the plain
    peer-percentile path, undetected because the fallback returns a
    validly-shaped result. This test fails before the pd.Timestamp(to_date)
    fix (empty _sector_trend_cache) and passes after (real verdict cached)."""

    def test_sector_trend_cache_gets_populated_not_silently_empty(self, monkeypatch, synthetic_multi_ticker_history):
        import scoring.scoring_engine as se

        monkeypatch.setattr(se, "get_benchmark_history", lambda: _index_history())
        monkeypatch.setattr(se, "get_sector_index_history", lambda sector, from_date, to_date: _index_history())

        engine = ScoringEngine()
        sector_map_data = {symbol: "Technology" for symbol in synthetic_multi_ticker_history}

        engine._compute_rs_and_sector_trends(synthetic_multi_ticker_history, sector_map_data)

        assert engine._sector_trend_cache != {}, (
            "Sector trend cache is empty -- _compute_rs_and_sector_trends() "
            "silently fell back to the except block instead of completing "
            "the real sector-index path."
        )
        assert engine._sector_trend_cache["Technology"] in ("UPTREND", "DOWNTREND", "CHOPPY")


class TestScoreTickerSchema:

    def test_score_ticker_returns_exact_expected_keys(self, synthetic_multi_ticker_history):
        engine = ScoringEngine()
        engine._rs_cache = compute_rs_ratings(synthetic_multi_ticker_history)

        row = engine.score_ticker("RECENT_WINNER", synthetic_multi_ticker_history["RECENT_WINNER"])

        assert set(row.keys()) == EXPECTED_ROW_KEYS, (
            f"Column mismatch. Expected {EXPECTED_ROW_KEYS}, got {set(row.keys())}. "
            f"Check for naming drift against ui/candidate_grid.py's DISPLAY_COLUMNS."
        )

    def test_score_ticker_reuses_rs_cache_not_self_ranked(self, synthetic_multi_ticker_history):
        """
        score_ticker should reuse the universe-wide percentile context from
        the last score_universe() call, not rank a ticker against itself
        (a degenerate single-member universe would always score 99).
        """
        engine = ScoringEngine()
        engine._rs_cache = compute_rs_ratings(synthetic_multi_ticker_history)

        loser_row = engine.score_ticker(
            "RECENT_LOSER", synthetic_multi_ticker_history["RECENT_LOSER"]
        )
        assert loser_row["RS_Rating"] < 90, (
            f"RECENT_LOSER scored {loser_row['RS_Rating']} — if this is 99, "
            f"score_ticker is likely ranking the ticker against itself instead "
            f"of reusing the cached universe-wide ranking."
        )


class TestScoreUniverse:

    def test_score_universe_one_row_per_ticker(self, synthetic_multi_ticker_history, monkeypatch):
        engine = ScoringEngine()
        monkeypatch.setattr(
            engine, "_load_price_history",
            lambda symbol: synthetic_multi_ticker_history.get(symbol)
        )
        result = engine.score_universe(symbols=list(synthetic_multi_ticker_history.keys()))

        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(synthetic_multi_ticker_history)
        assert set(result["Symbol"]) == set(synthetic_multi_ticker_history.keys())

    def test_score_universe_has_exact_expected_columns(self, synthetic_multi_ticker_history, monkeypatch):
        engine = ScoringEngine()
        monkeypatch.setattr(
            engine, "_load_price_history",
            lambda symbol: synthetic_multi_ticker_history.get(symbol)
        )
        result = engine.score_universe(symbols=list(synthetic_multi_ticker_history.keys()))
        expected = {
            "Symbol", "RS_Rating", "RS_2M", "RS_6M", "RS_12M", "Rel_Vol", "Sector",
            "Sector_Index_Trend",
        }
        assert set(result.columns) == expected

    def test_score_universe_empty_symbols_returns_empty_not_crash(self):
        engine = ScoringEngine()
        result = engine.score_universe(symbols=[])
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_one_bad_ticker_does_not_crash_whole_universe(self, synthetic_multi_ticker_history, monkeypatch):
        """
        If one ticker fails to score (bad data, missing volume, etc.), the
        rest of the universe should still come back — not one bad ticker
        crashing the entire scoring run.
        """
        bad_df = pd.DataFrame({"Date": [], "Close": []})  # will fail scoring
        history_with_one_bad = {**synthetic_multi_ticker_history, "BAD_TICKER": bad_df}

        engine = ScoringEngine()
        monkeypatch.setattr(
            engine, "_load_price_history",
            lambda symbol: history_with_one_bad.get(symbol)
        )
        result = engine.score_universe(symbols=list(history_with_one_bad.keys()))

        # The good tickers should still be present even if BAD_TICKER isn't
        good_symbols = set(synthetic_multi_ticker_history.keys())
        assert good_symbols.issubset(set(result["Symbol"])), (
            "A single bad ticker should not prevent the rest of the universe "
            "from being scored."
        )
