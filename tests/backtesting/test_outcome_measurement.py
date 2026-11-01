"""
Test for backtesting/outcome_measurement.py -- kept lean per spec: the
one that actually matters, the same-day target/stop tie-break.

Resolving this optimistically in either direction would quietly inflate
backtest results in a way that's easy to miss, since daily bars can't
tell which of target/stop was actually touched first intraday.
"""
from __future__ import annotations

import pandas as pd

import pytest

from backtesting.outcome_measurement import FILL_LIMIT, measure_forward_outcome
from config import MAX_HOLDING_TRADING_DAYS


class TestSameDayTieBreak:

    def test_both_target_and_stop_touched_same_day_resolves_to_stop_hit(self):
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        df = pd.DataFrame({
            "Date": dates,
            "Open": [100.0] * 10, "Close": [100.0] * 10,
            "High": [100.0] * 10, "Low": [100.0] * 10,
        })

        # Day after entry: both target (110) and stop (95) fall within
        # this single day's High/Low range.
        df.loc[1, "High"] = 111.0
        df.loc[1, "Low"] = 94.0

        result = measure_forward_outcome(
            entry_date=dates[0], entry_price=100.0, stop_loss=95.0, target=110.0,
            full_history=df, max_holding_days=5,
        )

        assert result["exit_reason"] == "STOP_HIT"
        assert result["exit_price"] == 95.0
        assert result["return_pct"] == -5.0


class TestTimeStopDefault:
    """2.1: the default holding horizon is MAX_HOLDING_TRADING_DAYS (40),
    a single config value, not a hardcoded number quietly duplicated here
    and in run_backtest()."""

    def test_default_max_holding_days_matches_config(self):
        dates = pd.date_range("2024-01-01", periods=MAX_HOLDING_TRADING_DAYS + 5, freq="D")
        # Flat price, never hits target (150) or stop (50) -- forces a
        # TIME_EXIT so days_held reveals the actual default window used.
        df = pd.DataFrame({
            "Date": dates,
            "Open": [100.0] * len(dates), "Close": [100.0] * len(dates),
            "High": [100.0] * len(dates), "Low": [100.0] * len(dates),
        })

        result = measure_forward_outcome(
            entry_date=dates[0], entry_price=100.0, stop_loss=50.0, target=150.0, full_history=df,
        )

        assert result["exit_reason"] == "TIME_EXIT"
        assert result["days_held"] == MAX_HOLDING_TRADING_DAYS


def _bars(opens, highs=None, lows=None, closes=None):
    n = len(opens)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    return dates, pd.DataFrame({
        "Date": dates, "Open": opens,
        "High": highs or opens, "Low": lows or opens, "Close": closes or opens,
    })


class TestNextOpenFillModel:
    """Fill model added 2026-10-20 (docs/known_data_issues.md item 10): the
    position is bought at the NEXT day's open, not at the plan's reference
    entry, because the signal is only known at the signal-day close."""

    def test_fill_is_next_day_open_and_return_is_measured_from_it(self):
        dates, df = _bars([100, 104, 104, 104, 104], highs=[100, 104, 104, 112, 104])

        result = measure_forward_outcome(dates[0], entry_price=100.0, stop_loss=95.0, target=110.0,
                                         full_history=df, max_holding_days=5)

        assert result["fill_price"] == 104.0
        assert result["exit_reason"] == "TARGET_HIT"
        assert result["return_pct"] == pytest.approx((110.0 / 104.0 - 1) * 100)

    def test_next_open_already_past_target_is_not_a_trade(self):
        # The run #4 failure mode: plan says buy 100 / target 110, but the
        # stock opens at 115 the next morning.
        dates, df = _bars([112, 115, 116])

        result = measure_forward_outcome(dates[0], entry_price=100.0, stop_loss=95.0, target=110.0,
                                         full_history=df, max_holding_days=5)

        assert result["exit_reason"] == "NO_FILL_PAST_TARGET"
        assert result["return_pct"] is None

    def test_next_open_at_or_below_stop_is_not_a_trade(self):
        dates, df = _bars([100, 94, 94])

        result = measure_forward_outcome(dates[0], entry_price=100.0, stop_loss=95.0, target=110.0,
                                         full_history=df, max_holding_days=5)

        assert result["exit_reason"] == "NO_FILL_BELOW_STOP"

    def test_gap_down_through_stop_exits_at_the_open_not_the_stop(self):
        dates, df = _bars([100, 100, 90], lows=[100, 99, 88])

        result = measure_forward_outcome(dates[0], entry_price=100.0, stop_loss=95.0, target=110.0,
                                         full_history=df, max_holding_days=5)

        assert result["exit_reason"] == "STOP_HIT"
        assert result["exit_price"] == 90.0   # the stop at 95 could not be filled

    def test_legacy_as_given_fill_reproduces_old_behaviour(self):
        dates, df = _bars([112, 115, 116], highs=[112, 115, 116])

        result = measure_forward_outcome(dates[0], entry_price=100.0, stop_loss=95.0, target=110.0,
                                         full_history=df, max_holding_days=5, fill="as_given")

        # Exactly the run #4 artifact: a "win" on a price that never traded.
        assert result["exit_reason"] == "TARGET_HIT"
        assert result["return_pct"] == 10.0


class TestLimitOrderFill:
    """Pre-registered variant B: a limit buy at the pivot (100), valid 5
    days after the signal; stop 85, target 130. Signal day is dates[0]."""

    def _run(self, df, dates, max_holding_days=10, valid=5):
        return measure_forward_outcome(dates[0], entry_price=100.0, stop_loss=85.0, target=130.0,
                                       full_history=df, max_holding_days=max_holding_days, fill=FILL_LIMIT,
                                       limit_price=100.0, limit_valid_days=valid)

    def test_fills_at_the_limit_when_the_low_reaches_it(self):
        #         signal  d1   d2(dips to 99) d3   d4 (target)
        dates, df = _bars([115, 112, 108, 105, 120], highs=[116, 113, 109, 110, 131], lows=[110, 109, 99, 104, 118])
        r = self._run(df, dates)
        assert (r["fill_price"], r["fill_offset"], r["fill_date"]) == (100.0, 2, dates[2])
        assert r["exit_reason"] == "TARGET_HIT" and r["exit_price"] == 130.0
        assert r["return_pct"] == pytest.approx(30.0)
        assert r["days_held"] == 3        # fill day counts as day 1

    def test_gap_below_the_limit_fills_at_the_open(self):
        dates, df = _bars([115, 96, 100], highs=[116, 99, 101], lows=[110, 95, 99])
        r = self._run(df, dates, max_holding_days=2)
        assert (r["fill_price"], r["fill_offset"]) == (96.0, 1)
        assert r["exit_reason"] == "TIME_EXIT" and r["exit_price"] == 100

    def test_open_at_or_below_stop_cancels_the_order(self):
        dates, df = _bars([115, 84, 90], lows=[110, 80, 88])
        assert self._run(df, dates)["exit_reason"] == "NO_FILL_STOP_FIRST"

    def test_expires_after_the_valid_days(self):
        dates, df = _bars([115, 112, 111, 110, 109, 108, 99], lows=[115, 111, 110, 109, 108, 107, 98])
        r = self._run(df, dates)          # day 6 dips to 98 but the order expired after day 5
        assert r["exit_reason"] == "NO_FILL_LIMIT_EXPIRED" and r["return_pct"] is None

    def test_intraday_fill_day_does_not_count_the_target_but_counts_the_stop(self):
        # Fill-day high 131 may have printed before the dip -> not a target hit.
        dates, df = _bars([115, 120, 110], highs=[116, 131, 112], lows=[110, 99, 105], closes=[115, 105, 110])
        r = self._run(df, dates, max_holding_days=2)
        assert r["exit_reason"] == "TIME_EXIT" and r["fill_price"] == 100.0
        # Same day falling through the stop after the fill -> stopped out that day.
        dates, df = _bars([115, 110, 110], lows=[110, 80, 105])
        r = self._run(df, dates)
        assert r["exit_reason"] == "STOP_HIT" and r["exit_price"] == 85.0 and r["days_held"] == 1

    def test_gap_down_through_stop_after_fill_exits_at_the_open(self):
        dates, df = _bars([115, 110, 80], lows=[110, 99, 78])
        r = self._run(df, dates)
        assert r["exit_reason"] == "STOP_HIT" and r["exit_price"] == 80

    def test_limit_needs_its_parameters(self):
        dates, df = _bars([115, 110])
        with pytest.raises(ValueError):
            measure_forward_outcome(dates[0], 100.0, 85.0, 130.0, df, fill=FILL_LIMIT)
