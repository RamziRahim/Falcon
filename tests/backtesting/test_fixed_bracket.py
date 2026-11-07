import numpy as np
import pandas as pd
import pytest

from backtesting.fixed_bracket import run_bracket
from backtesting.mtm_portfolio import CostModel
from backtesting.pit_strategies import Panel

FREE = CostModel(statutory=0.0, spread_tiers=((0, 0.0),), impact_coeff=0.0)
DAYS = pd.bdate_range("2018-01-01", periods=60)


def _panel(close, high, low):
    c = pd.DataFrame({"X": close}, index=DAYS)
    me = DAYS.to_series().groupby(DAYS.to_period("M")).max()
    v = c * 0 + 1e6
    return Panel(c, pd.DataFrame({"X": high}, index=DAYS), pd.DataFrame({"X": low}, index=DAYS), c, v, c * v,
                 {m: {"X"} for m in me}, pd.Series(DAYS[-1], index=["X"]), pd.Series(["X"], index=["X"]))


def _once(day_idx):
    def fn(i, day, busy):
        return [("market", "X", 100.0, 1.0, 0)] if i == day_idx and "X" not in busy else []
    return fn


def _run(high_on, low_on, n=60):
    close = np.full(n, 100.0); high = close + 0.5; low = close - 0.5
    for d, v in high_on.items(): high[d] = v
    for d, v in low_on.items(): low[d] = v
    return run_bracket(_panel(close, high, low), DAYS[0], DAYS[-1], _once(10), FREE)


def test_target_hit_pays_six_percent_and_uses_twenty_percent():
    eq, t = _run({14: 106.5}, {})
    row = t.iloc[0]
    assert row["exit_reason"] == "TARGET" and row["entry_date"] == DAYS[11]
    assert row["proceeds"] / row["cost_basis"] == pytest.approx(1.06)
    assert row["cost_basis"] == pytest.approx(200_000, rel=1e-3)


def test_stop_wins_same_day_tie_and_costs_two_percent():
    eq, t = _run({13: 107.0}, {13: 97.0})
    row = t.iloc[0]
    assert row["exit_reason"] == "STOP" and row["proceeds"] / row["cost_basis"] == pytest.approx(0.98)


def test_time_stop_after_twenty_sessions():
    eq, t = _run({}, {})
    row = t.iloc[0]
    assert row["exit_reason"] == "TIME_STOP" and row["exit_date"] == DAYS[11 + 20]
