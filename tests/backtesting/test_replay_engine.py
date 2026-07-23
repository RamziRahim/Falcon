"""
Tests for backtesting/replay_engine.py -- kept lean per spec, the two
that actually matter:

1. Lookahead bias, directly tested: corrupt all price data strictly
   after a known VCP breakout date with an impossible value (0.0) and
   confirm replay_decision_as_of() called ON that breakout date returns
   the identical result either way -- the most direct possible proof
   that future data isn't leaking into the replayed decision.
2. RS Rating replay uses the whole truncated universe, not just one
   ticker: two tickers with IDENTICAL individual histories but different
   universe-mates must produce different RS Ratings at the same replay
   date, proving the percentile rank is genuinely recomputed against the
   truncated universe rather than reused/cached from anywhere.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting.replay_engine import build_scored_universe_as_of, replay_decision_as_of
from technical_analysis.pattern_system.models import SwingPoint


def _vcp_breakout_df(extra_days_after_breakout: int = 30, corrupt_future: bool = False) -> pd.DataFrame:
    """A real zigzag (two higher-highs, two higher-lows via genuine
    fractal swing detection) into a tight base, then a breakout bar --
    verified directly (not assumed) to make VCP the genuinely CONFIRMED,
    highest-priority-selected pattern, not just some pattern.
    """
    wave1_down = np.linspace(90, 70, 10)
    wave1_up = np.linspace(71, 95, 10)
    wave2_down = np.linspace(94, 80, 10)
    wave2_up = np.linspace(81, 110, 10)
    base_down = np.linspace(109, 100.5, 6)
    base_rise = np.linspace(101, 108, 25)
    breakout = np.array([125.0])
    post = np.linspace(126, 140, extra_days_after_breakout)

    closes = np.concatenate([wave1_down, wave1_up, wave2_down, wave2_up, base_down, base_rise, breakout, post])
    n = len(closes)
    breakout_idx = 71  # 10+10+10+10+6+25
    volumes = [100_000] * breakout_idx + [300_000] + [100_000] * extra_days_after_breakout

    df = pd.DataFrame({
        "Date": pd.date_range("2022-01-01", periods=n, freq="D"),
        "Open": closes, "High": closes * 1.001, "Low": closes * 0.999, "Close": closes,
        "Volume": volumes, "Volume_SMA_20": [100_000] * n,
    })

    if corrupt_future:
        # Strictly AFTER the breakout day -- an impossible value a real
        # market could never produce, so any leakage would be obvious.
        df.loc[breakout_idx + 1:, ["Open", "High", "Low", "Close"]] = 0.0
        df.loc[breakout_idx + 1:, "Volume"] = 0.0

    return df


def _random_walk_df(n: int = 200, seed: int = 1, drift: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    closes = np.abs(100 + np.cumsum(rng.normal(drift, 1, n))) + 50
    return pd.DataFrame({
        "Date": pd.date_range("2022-01-01", periods=n, freq="D"),
        "Open": closes, "High": closes * 1.01, "Low": closes * 0.99, "Close": closes,
        "Volume": [100_000] * n, "Volume_SMA_20": [100_000] * n,
    })


BREAKOUT_INDEX = 71


class TestLookaheadBias:

    def test_corrupting_future_data_does_not_change_the_replayed_decision(self):
        clean_df = _vcp_breakout_df(corrupt_future=False)
        corrupt_df = _vcp_breakout_df(corrupt_future=True)
        breakout_date = clean_df.loc[BREAKOUT_INDEX, "Date"]
        benchmark_history = _random_walk_df(seed=99, n=300)

        def replay(target_df):
            universe_histories = {
                "TARGET.NS": target_df,
                "PEER1.NS": _random_walk_df(seed=1),
                "PEER2.NS": _random_walk_df(seed=2),
            }
            return replay_decision_as_of(
                ticker="TARGET.NS", as_of_date=breakout_date, full_history=target_df,
                benchmark_history=benchmark_history, universe_histories=universe_histories,
                vix_history=None,
            )

        clean_result = replay(clean_df)
        corrupt_result = replay(corrupt_df)

        # Sanity: this genuinely is a VCP breakout being replayed, not an
        # empty/no-op result the corruption trivially can't affect.
        assert clean_result["supporting_data"]["is_vcp_breakout"] == True

        for key in ("category", "confidence_score", "entry", "stop_loss", "target",
                    "market_regime_verdict", "sector_health_verdict"):
            assert clean_result[key] == corrupt_result[key], f"{key} differed: future data leaked in"


class TestRSRatingUsesTruncatedUniverse:

    def test_identical_ticker_histories_get_different_rs_ratings_with_different_universe_mates(self):
        # RS_Rating's composite blend includes a 12-month (252 trading
        # day) window -- compute_returns() returns NaN whenever truncated
        # history doesn't strictly exceed a window, which silently NaNs
        # the whole weighted blend. Needs enough bars past as_of_date's
        # truncation point for every window (up to 252d) to be satisfied,
        # confirmed empirically after an initial too-short fixture
        # produced NaN ratings for everyone.
        as_of_date = pd.Timestamp("2022-01-01") + pd.Timedelta(days=340)

        # Ticker under test: literally the same history object in both
        # universes -- only its universe-mates differ.
        shared_history = _random_walk_df(seed=7, n=400, drift=0.05)

        universe_a = {
            "TEST.NS": shared_history,
            "WEAK1.NS": _random_walk_df(seed=101, n=400, drift=-0.3),
            "WEAK2.NS": _random_walk_df(seed=102, n=400, drift=-0.3),
        }
        universe_b = {
            "TEST.NS": shared_history,
            "STRONG1.NS": _random_walk_df(seed=201, n=400, drift=0.5),
            "STRONG2.NS": _random_walk_df(seed=202, n=400, drift=0.5),
        }

        # Fake tickers resolve to sector "Unknown" (not real Yahoo
        # symbols), which is never in SECTOR_INDEX_MAP -- so
        # compute_sector_index_rs() falls back to the same peer-
        # percentile calculation this test is actually exercising, same
        # behavior as before sector-index RS existed.
        benchmark_history = _random_walk_df(seed=99, n=400)

        _, _, rs_ratings_a = build_scored_universe_as_of(as_of_date, universe_a, benchmark_history)
        _, _, rs_ratings_b = build_scored_universe_as_of(as_of_date, universe_b, benchmark_history)

        rating_a = rs_ratings_a.get("TEST.NS")
        rating_b = rs_ratings_b.get("TEST.NS")

        assert rating_a is not None and rating_b is not None
        # Same ticker, same individual history -- only the peer set
        # differs, so its percentile rank must differ: weak peers make it
        # look relatively strong, strong peers make it look relatively weak.
        assert rating_a != rating_b
        assert rating_a > rating_b


def _pivot(pivot_type, is_higher, index=0):
    return SwingPoint(index=index, date="d", price=100.0, type=pivot_type, is_higher=is_higher)


def _minimal_df(n=25):
    return pd.DataFrame({
        "Date": pd.date_range("2022-01-01", periods=n, freq="D"),
        "Close": [100.0] * n, "High": [101.0] * n, "Low": [99.0] * n, "Volume": [100_000] * n,
    })


class TestRegimeTrendStateRecalibration:
    """B-7: _regime_trend_state_of_truncated() -- market-level-only
    recalibration, verified on the tuning split (see the function's own
    docstring for the real NIFTY numbers). Pivots are monkeypatched
    directly (detect_swings is already tested elsewhere) so each case
    tests only the classification logic itself."""

    def _classify(self, monkeypatch, highs, lows):
        import backtesting.replay_engine as replay_engine

        pivots = (
            [_pivot("HIGH", flag, i) for i, flag in enumerate(highs)]
            + [_pivot("LOW", flag, i) for i, flag in enumerate(lows)]
        )
        monkeypatch.setattr(replay_engine.macro_swing_detector, "detect_swings", lambda df: pivots)

        return replay_engine._regime_trend_state_of_truncated(_minimal_df())

    def test_clear_uptrend(self, monkeypatch):
        result = self._classify(monkeypatch, highs=[True, True, True], lows=[True, True, True])
        assert result == "UPTREND"

    def test_clear_downtrend_short_circuits_before_any_vote(self, monkeypatch):
        # Only the single most recent pivot pair matters for DOWNTREND --
        # deliberately NOT loosened, unlike UPTREND.
        result = self._classify(monkeypatch, highs=[True, True, False], lows=[True, True, False])
        assert result == "DOWNTREND"

    def test_back_and_fill_pivot_pair_still_reads_uptrend(self, monkeypatch):
        # One "bad" pivot pair each side (majority still 2-of-3 "higher")
        # -- the whole point of the recalibration: this used to flip to
        # CHOPPY under the single-most-recent-pivot-pair rule whenever the
        # LAST pivot happened to be the back-and-fill one.
        result = self._classify(monkeypatch, highs=[True, False, True], lows=[True, True, False])
        assert result == "UPTREND"

    def test_no_majority_either_direction_is_choppy(self, monkeypatch):
        # Last pivot pair isn't a clean downtrend (high is higher), but
        # only 1-of-3 lows are higher -- no majority for UPTREND either.
        result = self._classify(monkeypatch, highs=[True, True, True], lows=[False, False, True])
        assert result == "CHOPPY"

    def test_too_few_pivots_to_vote_is_choppy(self, monkeypatch):
        result = self._classify(monkeypatch, highs=[True], lows=[True])
        assert result == "CHOPPY"

    def test_no_pivots_at_all_is_choppy(self, monkeypatch):
        result = self._classify(monkeypatch, highs=[], lows=[])
        assert result == "CHOPPY"

    def test_short_history_is_unknown_without_calling_detect_swings(self, monkeypatch):
        import backtesting.replay_engine as replay_engine

        def _fail_if_called(df):
            raise AssertionError("detect_swings should not be called for too-short history")

        monkeypatch.setattr(replay_engine.macro_swing_detector, "detect_swings", _fail_if_called)

        short_df = _minimal_df(n=5)
        result = replay_engine._regime_trend_state_of_truncated(short_df)

        assert result == "UNKNOWN"

    def test_does_not_affect_the_shared_per_stock_trend_helper(self, monkeypatch):
        # _trend_state_of_truncated (pattern-gating/sector-breadth) must
        # still use market_structure_engine's own original rule, untouched
        # by this recalibration -- confirmed by NOT monkeypatching
        # detect_swings here and instead checking the two functions can
        # legitimately disagree given the same monkeypatched pivots.
        import backtesting.replay_engine as replay_engine

        # Back-and-fill pivots: original single-pivot-pair rule reads
        # CHOPPY (last high True but last low False -> neither clean
        # uptrend nor downtrend); recalibrated rule reads UPTREND (2-of-3
        # majority each side).
        pivots = [
            _pivot("HIGH", True, 0), _pivot("HIGH", False, 1), _pivot("HIGH", True, 2),
            _pivot("LOW", True, 0), _pivot("LOW", True, 1), _pivot("LOW", False, 2),
        ]
        monkeypatch.setattr(replay_engine.macro_swing_detector, "detect_swings", lambda df: pivots)

        df = _minimal_df()
        original = replay_engine._trend_state_of_truncated(df)
        recalibrated = replay_engine._regime_trend_state_of_truncated(df)

        assert original == "CHOPPY"
        assert recalibrated == "UPTREND"
