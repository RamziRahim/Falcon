"""
Tests for backtesting/backtest_runner.py -- kept lean per spec.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting.backtest_runner import (
    aggregate_ceiling_attribution, compute_expectancy, populate_sector_cache, run_backtest,
)
from backtesting.detector_funnel import DETECTOR_DISPLAY_NAMES


class TestExpectancyFormula:

    def test_hand_computed_win_loss_produces_exact_expected_number(self):
        # win_rate=0.6, avg_win=+8.0%, loss_rate=0.4, avg_loss=-3.0%
        # Expectancy = (0.6 * 8.0) + (0.4 * -3.0) = 4.8 - 1.2 = 3.6
        expectancy = compute_expectancy(
            win_rate=0.6, avg_win_pct=8.0, loss_rate=0.4, avg_loss_pct=-3.0
        )

        assert expectancy == pytest.approx(3.6)


def _ceiling_row(category, confidence_score, market_regime_verdict="CAUTION",
                  sector_health_verdict="NEUTRAL", return_pct=5.0):
    return {
        "category": category, "confidence_score": confidence_score,
        "market_regime_verdict": market_regime_verdict,
        "sector_health_verdict": sector_health_verdict, "return_pct": return_pct,
    }


class TestAggregateCeilingAttribution:

    def test_splits_watchlist_by_score_threshold_into_capped_vs_genuine(self):
        trades = pd.DataFrame([
            _ceiling_row("ALERT_WATCHLIST", confidence_score=70.0),  # capped -- score-worthy of EXECUTE
            _ceiling_row("ALERT_WATCHLIST", confidence_score=50.0),  # genuine -- correctly below 65
            _ceiling_row("EXECUTE", confidence_score=80.0),
        ])

        result = aggregate_ceiling_attribution(trades)

        assert result["capped"]["sample_size"] == 1
        assert result["genuine"]["sample_size"] == 1
        assert result["execute"]["sample_size"] == 1

    def test_by_cause_reports_every_distinct_cause_not_just_one(self):
        trades = pd.DataFrame([
            _ceiling_row("ALERT_WATCHLIST", 70.0, market_regime_verdict="UNFAVORABLE"),
            _ceiling_row("ALERT_WATCHLIST", 70.0, market_regime_verdict="CAUTION", sector_health_verdict="NEUTRAL"),
            _ceiling_row("ALERT_WATCHLIST", 70.0, market_regime_verdict="CAUTION", sector_health_verdict="WEAK"),
        ])

        result = aggregate_ceiling_attribution(trades)

        causes = set(result["by_cause"]["group"])
        assert causes == {
            "UNFAVORABLE market",
            "CAUTION market + NEUTRAL sector",
            "CAUTION market + WEAK sector",
        }

    def test_return_column_parameter_reads_episode_level_columns(self):
        # episode_builder.py's output uses gross_return_pct/net_return_pct,
        # not return_pct -- same attribution logic, different column name.
        trades = pd.DataFrame([{
            "category": "ALERT_WATCHLIST", "confidence_score": 70.0,
            "market_regime_verdict": "CAUTION", "sector_health_verdict": "NEUTRAL",
            "net_return_pct": 12.0, "gross_return_pct": 12.3,
        }])

        result = aggregate_ceiling_attribution(trades, return_column="net_return_pct")

        assert result["capped"]["avg_return_pct"] == pytest.approx(12.0)

    def test_default_return_column_is_unchanged_return_pct(self):
        # Regression guard: the return_column parameter must default to the
        # original raw-signal-level behavior, not silently change it.
        trades = pd.DataFrame([_ceiling_row("ALERT_WATCHLIST", 70.0, return_pct=7.5)])

        result = aggregate_ceiling_attribution(trades)

        assert result["capped"]["avg_return_pct"] == pytest.approx(7.5)


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


class TestComputedRuntimeEstimate:
    """0.4: the old hardcoded '~70 minutes' guess is gone -- run_backtest()
    now logs its own elapsed-per-date x remaining-dates estimate every 10
    sampled dates, computed from this run's actual observed pace."""

    def test_progress_logged_every_ten_dates_not_a_hardcoded_guess(self, monkeypatch, caplog):
        import backtesting.replay_engine as replay_engine

        def fake_categorize(candidate, sector_row, market_verdict, pattern_details=None,
                             disable_fundamental_signals=False, enable_microstructure_signals=False):
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

        with caplog.at_level("INFO", logger="backtesting.backtest_runner"):
            run_backtest(
                universe_histories=universe_histories,
                benchmark_history=benchmark_history,
                vix_history=None,
                start_date=history["Date"].iloc[0],
                end_date=history["Date"].iloc[-1],
                sample_every_n_days=1,  # 60 daily rows -> 60 sampled dates, several >10 checkpoints
            )

        progress_lines = [r.message for r in caplog.records if "Progress:" in r.message]
        assert progress_lines, "expected at least one progress log line for a 60-date run"
        assert any("remaining" in line for line in progress_lines)
        assert "70 minutes" not in " ".join(progress_lines)


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


class TestDetectorFunnelWiring:
    """2.4: run_backtest()'s funnel_counts accumulator is populated for
    EVERY (ticker, date) evaluation -- categorize() is monkeypatched
    (irrelevant to the funnel, which is built from analyze_ticker()'s own
    output before categorize() is ever called), so the real detection
    chain runs unmodified against a real, if synthetic, OHLCV history."""

    def test_funnel_counts_populated_when_provided(self, monkeypatch):
        import backtesting.replay_engine as replay_engine

        def fake_categorize(candidate, sector_row, market_verdict, pattern_details=None,
                             disable_fundamental_signals=False, enable_microstructure_signals=False):
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

        funnel_counts: dict = {}
        run_backtest(
            universe_histories=universe_histories,
            benchmark_history=benchmark_history,
            vix_history=None,
            start_date=as_of_date,
            end_date=as_of_date,
            sample_every_n_days=1,
            funnel_counts=funnel_counts,
        )

        assert funnel_counts, "funnel_counts should have at least one detector tallied"
        assert set(funnel_counts.keys()).issubset(DETECTOR_DISPLAY_NAMES.keys())
        for counter in funnel_counts.values():
            assert sum(counter.values()) == 1  # one (ticker, date) evaluation in this fixture

    def test_omitting_funnel_counts_does_not_change_behavior(self, monkeypatch):
        # Default None -- must not raise, must not require the caller to
        # opt in to get identical behavior to before A-4 existed.
        import backtesting.replay_engine as replay_engine

        monkeypatch.setattr(replay_engine.sector_map, "get_sector", lambda symbol: "Unknown")

        history = _random_walk_df(seed=5, n=60)
        universe_histories = {"TEST.NS": history}
        benchmark_history = _random_walk_df(seed=99, n=60)
        as_of_date = history["Date"].iloc[-1]

        trades = run_backtest(
            universe_histories=universe_histories,
            benchmark_history=benchmark_history,
            vix_history=None,
            start_date=as_of_date,
            end_date=as_of_date,
            sample_every_n_days=1,
        )

        assert isinstance(trades, pd.DataFrame)


def _fake_avoid_categorize(candidate, sector_row, market_verdict, pattern_details=None,
                            disable_fundamental_signals=False, enable_microstructure_signals=False):
    return {
        "category": "AVOID", "market_regime_verdict": market_verdict,
        "sector_health_verdict": "NEUTRAL", "confidence_score": 25.0,
        "caps_applied": [], "fakeout_risk_flags": [], "contributing_factors": [],
        "entry": None, "stop_loss": None, "target": None, "max_holding_days": None,
        "supporting_data": candidate, "pattern_details": pattern_details or {},
    }


class TestAvoidOutcomeRecording:
    """2.5 (A-1): AVOID decisions get a HYPOTHETICAL forward outcome
    recorded (never a real one -- categorize() genuinely never prices an
    AVOID trade), needed for the EXECUTE > ALERT_WATCHLIST > AVOID
    monotonicity criterion."""

    def test_avoid_row_recorded_with_full_sample_rate(self, monkeypatch):
        import backtesting.replay_engine as replay_engine

        monkeypatch.setattr(replay_engine, "categorize", _fake_avoid_categorize)
        monkeypatch.setattr(replay_engine.sector_map, "get_sector", lambda symbol: "Unknown")

        history = _random_walk_df(seed=5, n=60)
        universe_histories = {"TEST.NS": history}
        benchmark_history = _random_walk_df(seed=99, n=60)
        as_of_date = history["Date"].iloc[30]  # leaves forward bars for outcome measurement

        trades = run_backtest(
            universe_histories=universe_histories,
            benchmark_history=benchmark_history,
            vix_history=None,
            start_date=as_of_date,
            end_date=as_of_date,
            sample_every_n_days=1,
            avoid_sample_rate=1.0,
        )

        assert len(trades) == 1
        row = trades.iloc[0]
        assert row["category"] == "AVOID"
        assert row["sampled_avoid"] == False
        assert row["entry_price"] > 0  # a real hypothetical price was computed, not left None
        assert row["exit_reason"] in {"TARGET_HIT", "STOP_HIT", "TIME_EXIT"}

    def test_zero_sample_rate_records_nothing(self, monkeypatch):
        import backtesting.replay_engine as replay_engine

        monkeypatch.setattr(replay_engine, "categorize", _fake_avoid_categorize)
        monkeypatch.setattr(replay_engine.sector_map, "get_sector", lambda symbol: "Unknown")

        history = _random_walk_df(seed=5, n=60)
        universe_histories = {"TEST.NS": history}
        benchmark_history = _random_walk_df(seed=99, n=60)
        as_of_date = history["Date"].iloc[-1]

        trades = run_backtest(
            universe_histories=universe_histories,
            benchmark_history=benchmark_history,
            vix_history=None,
            start_date=as_of_date,
            end_date=as_of_date,
            sample_every_n_days=1,
            avoid_sample_rate=0.0,
        )

        assert trades.empty

    def test_sampled_avoid_flag_is_true_whenever_sampling_is_active(self, monkeypatch):
        # rate=1.0 exactly is documented as "no sampling" -- anything below
        # that means every kept row is part of a subsample by construction.
        import backtesting.replay_engine as replay_engine

        monkeypatch.setattr(replay_engine, "categorize", _fake_avoid_categorize)
        monkeypatch.setattr(replay_engine.sector_map, "get_sector", lambda symbol: "Unknown")

        # Several tickers so at least one survives a 0.99 sample rate with
        # a fixed seed, without the test depending on exact RNG output.
        histories = {f"T{i}.NS": _random_walk_df(seed=i, n=60) for i in range(20)}
        benchmark_history = _random_walk_df(seed=99, n=60)
        as_of_date = histories["T0.NS"]["Date"].iloc[30]  # leaves forward bars for outcome measurement

        trades = run_backtest(
            universe_histories=histories,
            benchmark_history=benchmark_history,
            vix_history=None,
            start_date=as_of_date,
            end_date=as_of_date,
            sample_every_n_days=1,
            avoid_sample_rate=0.99,
            avoid_sample_seed=1,
        )

        assert not trades.empty, "expected at least one AVOID row to survive a 0.99 sample rate across 20 tickers"
        assert (trades["sampled_avoid"] == True).all()


def _fake_real_trade_categorize_factory(category, confidence_score, sector_health_verdict="NEUTRAL"):
    def _fake(candidate, sector_row, market_verdict, pattern_details=None,
              disable_fundamental_signals=False, enable_microstructure_signals=False):
        return {
            "category": category, "market_regime_verdict": market_verdict,
            "sector_health_verdict": sector_health_verdict, "confidence_score": confidence_score,
            "caps_applied": [], "fakeout_risk_flags": [], "contributing_factors": [],
            "entry": 100.0, "stop_loss": 90.0, "target": 120.0, "max_holding_days": 20,
            "supporting_data": candidate,
        }
    return _fake


class TestRecommendedRiskFractionWiring:
    """2.6a: the adopted exposure-scaling policy (e) is surfaced per-trade
    as recommended_risk_fraction, reusing
    portfolio_simulator.policy_sector_aware_caution() rather than a second
    parallel sizing rule."""

    def _run(self, monkeypatch, fake_categorize):
        import backtesting.replay_engine as replay_engine

        monkeypatch.setattr(replay_engine, "categorize", fake_categorize)
        monkeypatch.setattr(replay_engine.sector_map, "get_sector", lambda symbol: "Unknown")

        history = _random_walk_df(seed=5, n=60)
        universe_histories = {"TEST.NS": history}
        benchmark_history = _random_walk_df(seed=99, n=60)
        as_of_date = history["Date"].iloc[30]

        return run_backtest(
            universe_histories=universe_histories,
            benchmark_history=benchmark_history,
            vix_history=None,
            start_date=as_of_date,
            end_date=as_of_date,
            sample_every_n_days=1,
        )

    def test_execute_gets_full_size(self, monkeypatch):
        trades = self._run(monkeypatch, _fake_real_trade_categorize_factory("EXECUTE", 90.0))

        assert len(trades) == 1
        assert trades.iloc[0]["recommended_risk_fraction"] == 1.0

    def test_capped_caution_neutral_sector_gets_half_size(self, monkeypatch):
        # market_verdict is set by run_backtest()'s own regime computation,
        # not the fake -- CAUTION isn't guaranteed for this synthetic
        # history, so assert the policy's own documented contract instead
        # of a specific market_regime_verdict.
        trades = self._run(
            monkeypatch, _fake_real_trade_categorize_factory("ALERT_WATCHLIST", 70.0, "NEUTRAL"),
        )

        assert len(trades) == 1
        row = trades.iloc[0]
        if row["market_regime_verdict"] == "CAUTION":
            assert row["recommended_risk_fraction"] == 0.5
        else:
            assert row["recommended_risk_fraction"] == 0.0

    def test_genuine_low_score_gets_zero(self, monkeypatch):
        trades = self._run(monkeypatch, _fake_real_trade_categorize_factory("ALERT_WATCHLIST", 50.0))

        assert len(trades) == 1
        assert trades.iloc[0]["recommended_risk_fraction"] == 0.0

    def test_avoid_rows_have_no_recommended_risk_fraction(self, monkeypatch):
        trades = self._run(monkeypatch, _fake_avoid_categorize)

        assert len(trades) == 1
        assert trades.iloc[0]["recommended_risk_fraction"] is None

    def test_monitor_rows_have_no_recommended_risk_fraction(self, monkeypatch):
        # 2.6c: MONITOR gets a REAL outcome recorded (unlike AVOID) but
        # must never be sized -- it was never a real, tradeable signal.
        fake_monitor_categorize = _fake_real_trade_categorize_factory("MONITOR", 90.0)

        trades = self._run(monkeypatch, fake_monitor_categorize)

        assert len(trades) == 1
        row = trades.iloc[0]
        assert row["category"] == "MONITOR"
        assert row["recommended_risk_fraction"] is None
        assert row["exit_reason"] in {"TARGET_HIT", "STOP_HIT", "TIME_EXIT"}
