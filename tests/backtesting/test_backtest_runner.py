"""
Tests for backtesting/backtest_runner.py -- kept lean per spec.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting.backtest_runner import compute_expectancy, populate_sector_cache, run_backtest


class TestExpectancyFormula:

    def test_hand_computed_win_loss_produces_exact_expected_number(self):
        # win_rate=0.6, avg_win=+8.0%, loss_rate=0.4, avg_loss=-3.0%
        # Expectancy = (0.6 * 8.0) + (0.4 * -3.0) = 4.8 - 1.2 = 3.6
        expectancy = compute_expectancy(
            win_rate=0.6, avg_win_pct=8.0, loss_rate=0.4, avg_loss_pct=-3.0
        )

        assert expectancy == pytest.approx(3.6)


@pytest.fixture
def isolated_backtest_sector_map(monkeypatch, tmp_path):
    """A SectorMap instance pointed at temp override/cache files instead of
    the real project paths (same isolation as tests/scoring/conftest.py's
    isolated_sector_map, duplicated here since fixtures aren't shared
    across tests/ subdirectories without a root conftest.py), patched in
    as backtesting.backtest_runner's module-level sector_map so
    populate_sector_cache() itself is what's under test."""
    import scoring.sector_map as sm
    import backtesting.backtest_runner as backtest_runner

    monkeypatch.setattr(sm, "OVERRIDES_PATH", tmp_path / "no_overrides.csv")
    monkeypatch.setattr(sm, "SECTOR_MAP_PATH", tmp_path / "sector_map_test_cache.json")
    instance = sm.SectorMap()
    monkeypatch.setattr(backtest_runner, "sector_map", instance)
    return instance


@pytest.mark.integration
class TestPopulateSectorCacheRealYahooIntegration:
    """Hits the real yfinance API. Run explicitly with: pytest -m integration"""

    def test_five_known_nifty50_tickers_resolve_to_non_unknown_sectors(self, isolated_backtest_sector_map):
        known_tickers = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]

        populate_sector_cache(known_tickers)

        for ticker in known_tickers:
            sector = isolated_backtest_sector_map.get_sector(ticker)
            assert sector != "Unknown", f"{ticker} should resolve to a real sector, got Unknown"


def _random_walk_df(n: int = 60, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    closes = np.abs(100 + np.cumsum(rng.normal(0, 1, n))) + 50
    return pd.DataFrame({
        "Date": pd.date_range("2022-01-01", periods=n, freq="D"),
        "Open": closes, "High": closes * 1.01, "Low": closes * 0.99, "Close": closes,
        "Volume": [100_000] * n, "Volume_SMA_20": [100_000] * n,
    })


class TestEnableMicrostructureSignalsThreadsThroughRunBacktest:
    """Confirms enable_microstructure_signals travels run_backtest() ->
    replay_decision_as_of() -> categorize() end-to-end -- not that
    categorize() itself respects the flag (already covered by
    tests/decision_engine/test_leadership_decision_engine.py's
    TestMicrostructureSignalsAreFeatureFlagged), but that the wiring
    across all three layers actually carries the caller's value.
    categorize() is monkeypatched only to record the kwarg it receives;
    run_backtest()'s own sampling loop and replay_decision_as_of()'s real
    truncation/detection chain both run unmodified."""

    def test_flag_value_reaches_categorizes_own_kwarg(self, monkeypatch):
        import backtesting.replay_engine as replay_engine

        received_flags = []

        def fake_categorize(candidate, sector_row, market_verdict, pattern_details=None,
                             disable_fundamental_signals=False, enable_microstructure_signals=False):
            received_flags.append(enable_microstructure_signals)
            return {
                "category": "NO_DATA", "market_regime_verdict": market_verdict,
                "sector_health_verdict": None, "confidence_score": 0.0,
                "caps_applied": [], "fakeout_risk_flags": [], "contributing_factors": [],
                "entry": None, "stop_loss": None, "target": None, "supporting_data": {},
            }

        monkeypatch.setattr(replay_engine, "categorize", fake_categorize)
        # Fake tickers never resolve to a real sector -- no network call,
        # same fallback compute_sector_index_rs() already handles.
        monkeypatch.setattr(replay_engine.sector_map, "get_sector", lambda symbol: "Unknown")

        history = _random_walk_df(seed=5, n=60)
        universe_histories = {"TEST.NS": history}
        benchmark_history = _random_walk_df(seed=99, n=60)
        as_of_date = history["Date"].iloc[-1]

        run_backtest(
            universe_histories=universe_histories,
            benchmark_history=benchmark_history,
            vix_history=None,
            start_date=as_of_date,
            end_date=as_of_date,
            sample_every_n_days=1,
            enable_microstructure_signals=True,
        )

        assert received_flags, "categorize() was never reached -- fixture didn't produce a sampled date"
        assert all(flag is True for flag in received_flags)

    def test_flag_defaults_to_false_when_caller_omits_it(self, monkeypatch):
        import backtesting.replay_engine as replay_engine

        received_flags = []

        def fake_categorize(candidate, sector_row, market_verdict, pattern_details=None,
                             disable_fundamental_signals=False, enable_microstructure_signals=False):
            received_flags.append(enable_microstructure_signals)
            return {
                "category": "NO_DATA", "market_regime_verdict": market_verdict,
                "sector_health_verdict": None, "confidence_score": 0.0,
                "caps_applied": [], "fakeout_risk_flags": [], "contributing_factors": [],
                "entry": None, "stop_loss": None, "target": None, "supporting_data": {},
            }

        monkeypatch.setattr(replay_engine, "categorize", fake_categorize)
        monkeypatch.setattr(replay_engine.sector_map, "get_sector", lambda symbol: "Unknown")

        history = _random_walk_df(seed=5, n=60)
        universe_histories = {"TEST.NS": history}
        benchmark_history = _random_walk_df(seed=99, n=60)
        as_of_date = history["Date"].iloc[-1]

        run_backtest(
            universe_histories=universe_histories,
            benchmark_history=benchmark_history,
            vix_history=None,
            start_date=as_of_date,
            end_date=as_of_date,
            sample_every_n_days=1,
        )

        assert received_flags, "categorize() was never reached -- fixture didn't produce a sampled date"
        assert all(flag is False for flag in received_flags)
