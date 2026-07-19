"""
Test for backtesting/outcome_measurement.py -- kept lean per spec: the
one that actually matters, the same-day target/stop tie-break.

Resolving this optimistically in either direction would quietly inflate
backtest results in a way that's easy to miss, since daily bars can't
tell which of target/stop was actually touched first intraday.
"""
from __future__ import annotations

import pandas as pd

from backtesting.outcome_measurement import measure_forward_outcome


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
