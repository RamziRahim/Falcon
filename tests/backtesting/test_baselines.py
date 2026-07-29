"""
Tests for backtesting/baselines.py (I-4).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting.baselines import (
    naive_momentum_baseline,
    naive_momentum_topdecile_baseline,
    nifty_buy_hold,
    random_entry_control,
    summarize_random_control,
)
from config import ROUND_TRIP_COST_PCT


def _ohlcv(closes, start="2024-01-01"):
    dates = pd.date_range(start, periods=len(closes), freq="D")
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame({
        "Date": dates, "Open": closes, "High": closes * 1.01, "Low": closes * 0.99,
        "Close": closes, "Volume": [100_000] * len(closes),
    })


class TestNiftyBuyHold:

    def test_total_return_matches_hand_computation(self):
        benchmark = _ohlcv([100.0] + [100.0] * 9 + [110.0])  # first close 100, last close 110

        result = nifty_buy_hold(benchmark, benchmark["Date"].iloc[0], benchmark["Date"].iloc[-1])

        assert result["total_return_pct"] == pytest.approx(10.0)
        assert result["net_return_pct"] == pytest.approx(10.0 - ROUND_TRIP_COST_PCT * 100)

    def test_insufficient_window_returns_zero_not_a_crash(self):
        benchmark = _ohlcv([100.0])

        result = nifty_buy_hold(benchmark, benchmark["Date"].iloc[0], benchmark["Date"].iloc[0])

        assert result["total_return_pct"] == 0.0
        assert result["max_drawdown_pct"] == 0.0
        assert result["calmar"] == 0.0

    def test_max_drawdown_reflects_a_real_dip_below_the_running_peak(self):
        # Rises to 120, dips to 90 (a real -25% drawdown from the peak),
        # recovers to 110 -- total return is still positive (+10%) but the
        # drawdown must reflect the dip, not just start-vs-end.
        benchmark = _ohlcv([100.0, 110.0, 120.0, 90.0, 100.0, 110.0])

        result = nifty_buy_hold(benchmark, benchmark["Date"].iloc[0], benchmark["Date"].iloc[-1])

        assert result["total_return_pct"] == pytest.approx(10.0)
        assert result["max_drawdown_pct"] == pytest.approx(-25.0)

    def test_trailing_nan_close_is_not_picked_as_the_window_endpoint(self):
        # A same-day intraday snapshot cached before that day's close
        # settles (real case: the cache's own incremental refresh only
        # ever fetches forward from the last cached date, so a stale
        # incomplete row for a past date is never revisited on its own)
        # must not be treated as the window's actual end price. Last row's
        # own close (999.0) would be an obviously-wrong result if it were
        # used instead of being dropped -- it's set to NaN below.
        benchmark = _ohlcv([100.0] + [100.0] * 8 + [110.0, 999.0])
        benchmark.loc[benchmark.index[-1], "Close"] = np.nan

        result = nifty_buy_hold(benchmark, benchmark["Date"].iloc[0], benchmark["Date"].iloc[-1])

        # End price should fall back to the last row WITH a real close
        # (110, +10%), not NaN, and not the (already-overwritten) 999.0.
        assert result["total_return_pct"] == pytest.approx(10.0)
        assert not pd.isna(result["total_return_pct"])


class TestRandomEntryControl:

    def test_draws_up_to_k_entries_and_grades_them(self):
        universe = {
            "AAA.NS": _ohlcv(np.linspace(100, 130, 60)),
            "BBB.NS": _ohlcv(np.linspace(100, 70, 60)),
        }
        start, end = pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-15")

        draws = random_entry_control(
            universe, start, end, target_pct=8.0, stop_pct=5.0, k=10, max_holding_days=15,
        )

        assert len(draws) <= 10
        assert not draws.empty
        assert set(draws["ticker"]).issubset({"AAA.NS", "BBB.NS"})
        assert "net_return_pct" in draws.columns

    def test_same_seed_is_deterministic(self):
        universe = {"AAA.NS": _ohlcv(np.linspace(100, 130, 60))}
        start, end = pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-15")

        first = random_entry_control(universe, start, end, target_pct=8.0, stop_pct=5.0, k=5, seed=7)
        second = random_entry_control(universe, start, end, target_pct=8.0, stop_pct=5.0, k=5, seed=7)

        pd.testing.assert_frame_equal(first.reset_index(drop=True), second.reset_index(drop=True))

    def test_empty_universe_returns_empty_frame(self):
        draws = random_entry_control({}, pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-01"), 8.0, 5.0)

        assert draws.empty


class TestSummarizeRandomControl:

    def test_percentiles_computed_from_net_return(self):
        draws = pd.DataFrame({"net_return_pct": [1.0, 2.0, 3.0, 4.0, 100.0]})

        summary = summarize_random_control(draws)

        assert summary["n"] == 5
        assert summary["p50_net_return_pct"] == pytest.approx(3.0)
        # p95 should sit close to the top of the distribution, pulled up by the outlier
        assert summary["p95_net_return_pct"] > summary["p50_net_return_pct"]

    def test_empty_draws_returns_zeroed_summary_not_a_crash(self):
        summary = summarize_random_control(pd.DataFrame())

        assert summary["n"] == 0


class TestNaiveMomentumBaseline:

    def test_picks_the_highest_trailing_momentum_ticker(self):
        # AAA rises steadily (strong trailing momentum by day 70), BBB flat
        universe = {
            "AAA.NS": _ohlcv(np.linspace(100, 200, 100)),
            "BBB.NS": _ohlcv([100.0] * 100),
        }
        as_of_date = universe["AAA.NS"]["Date"].iloc[70]

        result = naive_momentum_baseline(universe, [as_of_date], lookback_days=63, max_holding_days=10)

        assert len(result) == 1
        assert result.iloc[0]["ticker"] == "AAA.NS"

    def test_reports_the_actual_exit_date_used(self):
        # Needed to feed momentum trades into portfolio_simulator.py for a
        # like-for-like comparison against Falcon's own episodes.
        universe = {"AAA.NS": _ohlcv(np.linspace(100, 200, 100))}
        as_of_date = universe["AAA.NS"]["Date"].iloc[70]

        result = naive_momentum_baseline(universe, [as_of_date], lookback_days=63, max_holding_days=10)

        expected_exit_date = universe["AAA.NS"]["Date"].iloc[80]  # 70 + 10 trading days
        assert result.iloc[0]["exit_date"] == expected_exit_date

    def test_insufficient_lookback_history_is_skipped_not_a_crash(self):
        universe = {"AAA.NS": _ohlcv(np.linspace(100, 110, 20))}  # too short for a 63-day lookback
        as_of_date = universe["AAA.NS"]["Date"].iloc[-1]

        result = naive_momentum_baseline(universe, [as_of_date], lookback_days=63)

        assert result.empty


class TestNaiveMomentumTopDecileBaseline:

    def test_takes_top_decile_not_just_one(self):
        # 10 tickers, steadily increasing strength -- top decile of 10 is 1,
        # but the point of this test is multiple picks ARE possible with a
        # bigger universe (checked below), not that exactly 1 comes back here.
        universe = {
            f"T{i}.NS": _ohlcv(np.linspace(100, 100 + i * 20, 150))
            for i in range(10)
        }
        as_of_date = universe["T0.NS"]["Date"].iloc[130]

        result = naive_momentum_topdecile_baseline(
            universe, [as_of_date], lookback_days=126, max_holding_days=10, trend_filter_window=50,
        )

        assert len(result) == 1
        assert result.iloc[0]["ticker"] == "T9.NS"  # strongest momentum of the 10

    def test_multiple_picks_per_date_with_a_bigger_universe(self):
        # 20 tickers rising at different strengths (i starts at 1, not 0 --
        # a perfectly flat line sits exactly AT its own SMA, not above it,
        # and would be legitimately excluded by the trend filter) -- top
        # decile of 20 is 2, so 2 distinct tickers should come back.
        universe = {
            f"T{i}.NS": _ohlcv(np.linspace(100, 100 + i * 10, 150))
            for i in range(1, 21)
        }
        as_of_date = universe["T1.NS"]["Date"].iloc[130]

        result = naive_momentum_topdecile_baseline(
            universe, [as_of_date], lookback_days=126, max_holding_days=10, trend_filter_window=50,
        )

        assert len(result) == 2
        assert set(result["ticker"]) == {"T19.NS", "T20.NS"}  # two strongest

    def test_trend_filter_excludes_a_ticker_trading_below_its_own_sma(self):
        # AAA: strong trailing 126-day momentum on paper, but has since
        # rolled over hard and is now trading well below its own 50-day
        # SMA -- the trend filter must exclude it even though its raw
        # lookback-window return looks the best.
        aaa_prices = np.concatenate([np.linspace(100, 300, 100), np.linspace(300, 150, 50)])
        bbb_prices = np.linspace(100, 160, 150)  # steady, real uptrend, above its own SMA
        universe = {"AAA.NS": _ohlcv(aaa_prices), "BBB.NS": _ohlcv(bbb_prices)}
        # -15 from the end, not the very last row -- leaves room for the
        # 10-day forward exit window (a date with nothing after it can
        # never resolve an exit, regardless of whether it passes the
        # trend filter).
        as_of_date = universe["AAA.NS"]["Date"].iloc[-15]

        result = naive_momentum_topdecile_baseline(
            universe, [as_of_date], lookback_days=126, max_holding_days=10, trend_filter_window=50,
        )

        assert "AAA.NS" not in set(result["ticker"])
        assert "BBB.NS" in set(result["ticker"])

    def test_insufficient_history_is_skipped_not_a_crash(self):
        universe = {"AAA.NS": _ohlcv(np.linspace(100, 110, 30))}  # too short for a 126-day lookback
        as_of_date = universe["AAA.NS"]["Date"].iloc[-1]

        result = naive_momentum_topdecile_baseline(universe, [as_of_date], lookback_days=126)

        assert result.empty
