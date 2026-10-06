"""
Tests for backtesting/trailing_exit_simulator.py -- the four scenarios
the spec called out explicitly, plus the same-day hard-stop-vs-partial-
trigger tie-break and the NO_DATA fail-closed case.
"""
from __future__ import annotations

import pandas as pd
import pytest

from backtesting.trailing_exit_simulator import simulate_trailing_exit


def _flat_history(closes: list[float], start: str = "2024-01-01") -> pd.DataFrame:
    """Open/High/Low all equal to Close by default -- tests override
    specific rows' High/Low when a scenario needs an intraday stop touch
    distinct from the day's Close."""
    dates = pd.date_range(start, periods=len(closes), freq="D")
    return pd.DataFrame({
        "Date": dates, "Open": closes, "High": closes, "Low": closes, "Close": closes,
    })


class TestNeverReachesPartialTrigger:
    """Must behave EXACTLY as the original backtest would have -- stop or
    time-stop only, never a fabricated different outcome."""

    def test_hits_hard_stop_without_ever_reaching_partial_gain(self):
        # Entry 100, partial trigger at 108 (8%), hard stop at 92.
        # Price drifts down and touches the stop without ever closing >= 108.
        closes = [100.0, 99.0, 97.0, 95.0, 93.0, 90.0]
        history = _flat_history(closes)
        history.loc[5, "Low"] = 90.0  # breaches stop on day 5

        result = simulate_trailing_exit(
            entry_price=100.0, entry_date=history["Date"].iloc[0], price_history=history,
            hard_stop_price=92.0,
        )

        assert result["never_hit_partial_trigger"] is True
        assert result["partial_exit_date"] is None
        assert result["remainder_exit_reason"] == "HARD_STOP"
        assert result["remainder_exit_price"] == 92.0
        assert result["blended_return_pct"] == pytest.approx(-8.0)

    def test_runs_to_time_stop_without_ever_reaching_partial_gain(self):
        # Flat, never moves -- never triggers partial, never hits stop.
        closes = [100.0] * 10
        history = _flat_history(closes)

        result = simulate_trailing_exit(
            entry_price=100.0, entry_date=history["Date"].iloc[0], price_history=history,
            hard_stop_price=80.0, max_holding_days=5,
        )

        assert result["never_hit_partial_trigger"] is True
        assert result["remainder_exit_reason"] == "TIME_STOP"
        assert result["remainder_exit_price"] == 100.0
        assert result["blended_return_pct"] == pytest.approx(0.0)


class TestPartialThenTrailsUpFurtherBeforeMaCross:

    def test_hits_partial_then_continues_up_then_falls_below_trailing_ma(self):
        # Entry 100. Day 1: close 109 (>=108, triggers partial). Days
        # 2-4: keeps climbing (MA trails up under it). Day 5: gaps down
        # hard, closing well below its own trailing 3-day MA.
        closes = [100.0, 109.0, 112.0, 115.0, 118.0, 95.0]
        history = _flat_history(closes)

        result = simulate_trailing_exit(
            entry_price=100.0, entry_date=history["Date"].iloc[0], price_history=history,
            partial_exit_gain_pct=8.0, partial_exit_fraction=0.5,
            trailing_ma_period=3, hard_stop_price=70.0,
        )

        assert result["never_hit_partial_trigger"] is False
        assert result["partial_exit_price"] == pytest.approx(109.0)
        assert result["remainder_exit_reason"] == "TRAILING_MA"
        assert result["remainder_exit_price"] == pytest.approx(95.0)
        # blended = 0.5*9% + 0.5*(-5%)
        assert result["blended_return_pct"] == pytest.approx(0.5 * 9.0 + 0.5 * -5.0)

    def test_trailing_ma_not_checked_on_the_triggering_day_itself(self):
        """The day partial triggers, there's nothing to trail yet --
        confirmed by a price path where the MA condition would already be
        satisfied the instant it started being computed, but the position
        must still be open the next day (not exited same-day)."""
        closes = [100.0, 200.0, 199.0]  # day 1: huge spike triggers partial;
        # day 2 (199) is still above a rolling-2 MA of [100, 200]=150, so
        # this wouldn't false-trigger anyway -- the real check is that
        # remainder_exit_date is never equal to partial_exit_date.
        history = _flat_history(closes)

        result = simulate_trailing_exit(
            entry_price=100.0, entry_date=history["Date"].iloc[0], price_history=history,
            partial_exit_gain_pct=8.0, trailing_ma_period=2, hard_stop_price=50.0,
        )

        assert result["partial_exit_date"] != result["remainder_exit_date"]


class TestPartialThenReversesToHardStop:
    """Confirms the original stop stays live for the remainder even after
    profit has been partially banked -- a real reversal must still be
    caught, not silently ignored because "some profit is already safe"."""

    def test_hits_partial_then_reverses_and_hits_original_hard_stop(self):
        # Entry 100, stop 92. Day 1: spikes to 110 (partial triggers).
        # Day 2: crashes straight through the original stop.
        closes = [100.0, 110.0, 105.0]
        history = _flat_history(closes)
        history.loc[2, "Low"] = 90.0  # breaches the original stop intraday

        result = simulate_trailing_exit(
            entry_price=100.0, entry_date=history["Date"].iloc[0], price_history=history,
            partial_exit_gain_pct=8.0, partial_exit_fraction=0.5,
            trailing_ma_period=20, hard_stop_price=92.0,
        )

        assert result["never_hit_partial_trigger"] is False
        assert result["partial_exit_price"] == pytest.approx(110.0)
        assert result["remainder_exit_reason"] == "HARD_STOP"
        assert result["remainder_exit_price"] == pytest.approx(92.0)
        assert result["blended_return_pct"] == pytest.approx(0.5 * 10.0 + 0.5 * -8.0)

    def test_same_day_hard_stop_wins_over_partial_trigger(self):
        """A day where Low breaches the stop AND Close would have cleared
        the partial trigger -- the stop must win (same conservative
        tie-break as measure_forward_outcome's target/stop case), not the
        more optimistic "partial fired first" reading."""
        closes = [100.0, 109.0]
        history = _flat_history(closes)
        history.loc[1, "Low"] = 91.0  # wicks through the stop before closing at 109

        result = simulate_trailing_exit(
            entry_price=100.0, entry_date=history["Date"].iloc[0], price_history=history,
            partial_exit_gain_pct=8.0, hard_stop_price=92.0,
        )

        assert result["never_hit_partial_trigger"] is True
        assert result["remainder_exit_reason"] == "HARD_STOP"
        assert result["remainder_exit_price"] == pytest.approx(92.0)


class TestRunsPastMaxHoldingDays:

    def test_partial_triggers_then_stays_above_ma_until_time_stop(self):
        # Entry 100. Day 1: closes at 109 (partial triggers). Days 2-5:
        # stays comfortably above its own trailing MA the whole time --
        # max_holding_days caps the window at 5, so it must time out.
        closes = [100.0, 109.0, 110.0, 111.0, 112.0, 113.0]
        history = _flat_history(closes)

        result = simulate_trailing_exit(
            entry_price=100.0, entry_date=history["Date"].iloc[0], price_history=history,
            partial_exit_gain_pct=8.0, partial_exit_fraction=0.5,
            trailing_ma_period=2, max_holding_days=5, hard_stop_price=70.0,
        )

        assert result["never_hit_partial_trigger"] is False
        assert result["remainder_exit_reason"] == "TIME_STOP"
        # Window is entry_idx+1 .. +5 -> last day is index 5 (close 113.0).
        assert result["remainder_exit_price"] == pytest.approx(113.0)


class TestNoHardStopConfigured:

    def test_hard_stop_none_never_fires(self):
        """hard_stop_price is optional -- when omitted, only the trailing
        MA / partial / time-stop logic governs the exit."""
        closes = [100.0, 109.0, 108.0, 50.0]  # would "hit" any realistic
        # stop on day 3, but no stop was configured -- must run to the MA
        # cross or time-stop instead.
        history = _flat_history(closes)

        result = simulate_trailing_exit(
            entry_price=100.0, entry_date=history["Date"].iloc[0], price_history=history,
            partial_exit_gain_pct=8.0, trailing_ma_period=2, hard_stop_price=None,
        )

        assert result["remainder_exit_reason"] != "HARD_STOP"


class TestNoDataFailsClosed:

    def test_entry_date_not_in_history_returns_no_data(self):
        history = _flat_history([100.0] * 5)
        missing_date = pd.Timestamp("1999-01-01")

        result = simulate_trailing_exit(
            entry_price=100.0, entry_date=missing_date, price_history=history,
        )

        assert result["remainder_exit_reason"] == "NO_DATA"
        assert result["blended_return_pct"] is None

    def test_no_trading_days_after_entry_returns_no_data(self):
        history = _flat_history([100.0] * 3)
        last_date = history["Date"].iloc[-1]

        result = simulate_trailing_exit(
            entry_price=100.0, entry_date=last_date, price_history=history,
        )

        assert result["remainder_exit_reason"] == "NO_DATA"
