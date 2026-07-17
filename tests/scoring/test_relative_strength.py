"""
Tests for scoring/relative_strength.py — matches the real implementation's
actual functions: compute_returns, percentile_rank, compute_rs_ratings.
"""
from __future__ import annotations

import pandas as pd
import pytest

from scoring.relative_strength import compute_returns, percentile_rank, compute_rs_ratings


class TestPercentileRankDirection:

    def test_highest_return_gets_highest_rank(self, synthetic_returns_series):
        ranked = percentile_rank(synthetic_returns_series)
        assert ranked["TICKER_E"] == ranked.max(), (
            f"Best performer (+30%) should get the top rank. Got {ranked.to_dict()}"
        )

    def test_lowest_return_gets_lowest_rank(self, synthetic_returns_series):
        ranked = percentile_rank(synthetic_returns_series)
        assert ranked["TICKER_A"] == ranked.min(), (
            f"Worst performer (-10%) should get the bottom rank. Got {ranked.to_dict()}"
        )

    def test_rank_is_monotonic_with_return(self, synthetic_returns_series):
        ranked = percentile_rank(synthetic_returns_series)
        ordered = synthetic_returns_series.sort_values()
        ranks_in_return_order = ranked[ordered.index]
        assert list(ranks_in_return_order) == sorted(ranks_in_return_order), (
            "Ranks are not monotonically increasing with return."
        )

    def test_rank_is_within_valid_range(self, synthetic_returns_series):
        ranked = percentile_rank(synthetic_returns_series)
        assert ranked.between(1, 99).all(), f"Ranks outside 1-99 range: {ranked.to_dict()}"

    def test_missing_input_stays_nan(self):
        series = pd.Series({"A": 0.05, "B": float("nan"), "C": 0.15})
        ranked = percentile_rank(series)
        assert pd.isna(ranked["B"]), "Missing input should remain NaN, not be silently ranked."
        assert ranked["C"] > ranked["A"]


class TestCompositeRSRatingRecencyWeighting:

    def test_recent_winner_outranks_recent_loser(self, synthetic_multi_ticker_history):
        ratings = compute_rs_ratings(synthetic_multi_ticker_history)
        winner = ratings.loc["RECENT_WINNER", "RS_Rating"]
        loser = ratings.loc["RECENT_LOSER", "RS_Rating"]
        assert winner > loser, (
            f"RECENT_WINNER (flat then rally) scored {winner}, RECENT_LOSER "
            f"(rally then drop) scored {loser}. Expected winner > loser due to "
            f"recent-quarter weighting (0.4 on 3M vs 0.2 on 12M)."
        )

    def test_steady_climber_lands_between_winner_and_loser(self, synthetic_multi_ticker_history):
        """
        A steady, unremarkable climber should land in the middle — not
        outrank the recent winner, not underrank the recent loser.
        """
        ratings = compute_rs_ratings(synthetic_multi_ticker_history)
        winner = ratings.loc["RECENT_WINNER", "RS_Rating"]
        steady = ratings.loc["STEADY_CLIMBER", "RS_Rating"]
        loser = ratings.loc["RECENT_LOSER", "RS_Rating"]
        assert loser < steady < winner


class TestOutputSchema:

    def test_compute_rs_ratings_has_expected_columns(self, synthetic_multi_ticker_history):
        ratings = compute_rs_ratings(synthetic_multi_ticker_history)
        assert set(ratings.columns) == {"RS_Rating", "RS_2M", "RS_6M", "RS_12M"}, (
            f"Column mismatch — check for naming drift vs what scoring_engine.py "
            f"and ui/candidate_grid.py's DISPLAY_COLUMNS expect. Got {list(ratings.columns)}"
        )


class TestEdgeCases:

    def test_insufficient_history_gives_nan_not_crash(self, synthetic_short_and_long_history):
        returns = compute_returns(synthetic_short_and_long_history)
        assert pd.isna(returns.loc["SHORT", "Return_12M"]), (
            "Ticker with <12 months of history should report NaN for Return_12M, "
            "not an out-of-bounds or fabricated value."
        )
        assert not pd.isna(returns.loc["LONG", "Return_12M"])

    def test_insufficient_history_excluded_from_rs_rating(self, synthetic_short_and_long_history):
        """
        A ticker without enough history for the composite window must be
        excluded (NaN) from RS_Rating, not force-ranked against a universe
        it can't fairly belong to.
        """
        ratings = compute_rs_ratings(synthetic_short_and_long_history)
        assert pd.isna(ratings.loc["SHORT", "RS_Rating"])

    def test_single_ticker_universe_does_not_crash(self):
        series = pd.Series({"ONLY_TICKER": 0.10})
        ranked = percentile_rank(series)
        assert ranked is not None
