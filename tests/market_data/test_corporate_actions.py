"""
Tests for market_data/corporate_actions.py -- backward-adjustment for
confirmed stock splits/bonus issues (NSEProvider has no adjusted-close
alternative at all, see that module's own docstring for how this was
found: BAJFINANCE.NS's real ~10x split+bonus on 2025-06-16).
"""
from __future__ import annotations

import pandas as pd
import pytest

from market_data.corporate_actions import (
    confirm_and_adjust,
    detect_discontinuities,
)


def _ohlcv(closes, start="2024-01-01", volumes=None):
    dates = pd.date_range(start, periods=len(closes), freq="D")
    n = len(closes)
    return pd.DataFrame({
        "Date": dates, "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": volumes if volumes is not None else [100_000] * n,
    })


def _corporate_actions(symbol: str, ex_date: str, subject: str = "Bonus 4:1") -> pd.DataFrame:
    return pd.DataFrame({
        "symbol": [symbol], "exDate": [pd.Timestamp(ex_date)], "subject": [subject],
    })


class TestDetectDiscontinuities:

    def test_flags_a_move_past_the_threshold(self):
        closes = [100.0, 101.0, 102.0, 10.0, 10.2]  # day 3: ~90% drop
        df = _ohlcv(closes)

        result = detect_discontinuities(df, threshold=0.40)

        assert len(result) == 1
        assert result.iloc[0]["Date"] == df["Date"].iloc[3]

    def test_does_not_flag_ordinary_volatility(self):
        closes = [100.0, 95.0, 103.0, 98.0, 105.0]  # normal day-to-day noise
        df = _ohlcv(closes)

        result = detect_discontinuities(df, threshold=0.40)

        assert result.empty


class TestConfirmAndAdjust:

    def test_confirmed_split_scales_everything_before_the_event_date(self):
        # 10x drop on day 3, matching a real NSE-documented action.
        closes = [100.0, 101.0, 102.0, 10.2, 10.4]
        df = _ohlcv(closes)
        event_date = df["Date"].iloc[3]
        corporate_actions = _corporate_actions("AAA", str(event_date.date()))

        adjusted, log = confirm_and_adjust(df, "AAA.NS", corporate_actions)

        assert len(log) == 1
        assert log[0]["confirmed"] is True
        factor = closes[3] / closes[2]  # ~0.1

        assert adjusted["Close"].iloc[0] == pytest.approx(closes[0] * factor)
        assert adjusted["Close"].iloc[2] == pytest.approx(closes[2] * factor)
        # On/after the event date: untouched.
        assert adjusted["Close"].iloc[3] == pytest.approx(closes[3])
        assert adjusted["Close"].iloc[4] == pytest.approx(closes[4])

    def test_volume_is_inversely_adjusted(self):
        closes = [100.0, 100.0, 10.0, 10.0]
        volumes = [50_000, 50_000, 500_000, 500_000]
        df = _ohlcv(closes, volumes=volumes)
        event_date = df["Date"].iloc[2]
        corporate_actions = _corporate_actions("AAA", str(event_date.date()))

        adjusted, _ = confirm_and_adjust(df, "AAA.NS", corporate_actions)

        factor = closes[2] / closes[1]  # 0.1
        # Volume before the event scales UP (inverse of the price factor)
        # -- more shares outstanding post-split represent the same value.
        assert adjusted["Volume"].iloc[0] == pytest.approx(volumes[0] / factor, rel=1e-6)

    def test_unconfirmed_discontinuity_is_left_untouched_and_reported(self):
        # A real -90% single-day move with NO matching corporate action
        # record -- must not be silently "corrected" on a guess.
        closes = [100.0, 101.0, 102.0, 10.2, 10.4]
        df = _ohlcv(closes)
        corporate_actions = pd.DataFrame(columns=["symbol", "exDate", "subject"])

        adjusted, log = confirm_and_adjust(df, "AAA.NS", corporate_actions)

        assert len(log) == 1
        assert log[0]["confirmed"] is False
        pd.testing.assert_series_equal(adjusted["Close"], df["Close"], check_names=False)

    def test_no_discontinuity_returns_original_frame_and_empty_log(self):
        closes = [100.0, 101.0, 99.0, 102.0]
        df = _ohlcv(closes)
        corporate_actions = pd.DataFrame(columns=["symbol", "exDate", "subject"])

        adjusted, log = confirm_and_adjust(df, "AAA.NS", corporate_actions)

        assert log == []
        pd.testing.assert_frame_equal(adjusted, df.sort_values("Date").reset_index(drop=True))

    def test_two_splits_compound_correctly_in_reverse_chronological_order(self):
        # A 2x split on day 3, then (going further back) a 5x split on
        # day 2 relative to day 1 -- day 0/1's prices must reflect BOTH
        # factors compounded, not just the most recent one.
        closes = [500.0, 505.0, 100.0, 101.0, 50.0, 50.5]
        df = _ohlcv(closes)
        first_event = df["Date"].iloc[2]   # 505 -> 100, ~5x
        second_event = df["Date"].iloc[4]  # 101 -> 50, ~2x
        corporate_actions = pd.concat([
            _corporate_actions("AAA", str(first_event.date()), "Bonus 4:1"),
            _corporate_actions("AAA", str(second_event.date()), "Face Value Split"),
        ], ignore_index=True)

        adjusted, log = confirm_and_adjust(df, "AAA.NS", corporate_actions)

        assert len(log) == 2
        assert all(entry["confirmed"] for entry in log)

        factor1 = closes[2] / closes[1]   # ~0.198 (the 5x-ish split)
        factor2 = closes[4] / closes[3]   # ~0.495 (the 2x-ish split)
        # Day 0/1 (before BOTH events) must reflect the compounded factor.
        assert adjusted["Close"].iloc[0] == pytest.approx(closes[0] * factor1 * factor2)
        # Day 2/3 (after the first event, before the second) reflects only factor2.
        assert adjusted["Close"].iloc[2] == pytest.approx(closes[2] * factor2)
        # Day 4/5 (after both): untouched.
        assert adjusted["Close"].iloc[4] == pytest.approx(closes[4])

    def test_date_tolerance_matches_an_ex_date_a_couple_days_off(self):
        # The observed price move and NSE's own recorded exDate don't
        # always land on the exact same calendar day (settlement/weekend
        # drift) -- within DATE_TOLERANCE_DAYS should still confirm.
        closes = [100.0, 101.0, 102.0, 10.2, 10.4]
        df = _ohlcv(closes)
        event_date = df["Date"].iloc[3]
        recorded_ex_date = event_date - pd.Timedelta(days=2)
        corporate_actions = _corporate_actions("AAA", str(recorded_ex_date.date()))

        _, log = confirm_and_adjust(df, "AAA.NS", corporate_actions, date_tolerance_days=3)

        assert log[0]["confirmed"] is True
