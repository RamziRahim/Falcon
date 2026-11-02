import numpy as np
import pandas as pd
import pytest

import backtesting.pit_strategies as ps
from backtesting.mtm_portfolio import CostModel
from backtesting.pit_strategies import Panel, judge, run_breakout, run_momentum

FREE = CostModel(statutory=0.0, spread_tiers=((0, 0.0),), impact_coeff=0.0)
DAYS = pd.bdate_range("2018-01-01", periods=400)


def _panel(close: pd.DataFrame, universe_ids=None, last_date=None, volume=None):
    vol = volume if volume is not None else close * 0 + 1000.0
    uni_ids = set(close.columns) if universe_ids is None else universe_ids
    month_ends = close.index.to_series().groupby(close.index.to_period("M")).max()
    return Panel(close, close * 1.01, close * 0.99, close, vol, close * vol,
                 {m: uni_ids for m in month_ends}, last_date if last_date is not None else
                 pd.Series(close.index[-1], index=close.columns), pd.Series(close.columns, index=close.columns))


def test_momentum_holds_the_strongest_names(monkeypatch):
    monkeypatch.setattr(ps, "MOM_HOLD", 2)
    growth = {f"S{k}": 100 * (1 + 0.0005 * k) ** np.arange(len(DAYS)) for k in range(6)}
    panel = _panel(pd.DataFrame(growth, index=DAYS))
    eq, trades = run_momentum(panel, DAYS[260], DAYS[-1], FREE)
    # the two fastest growers (S5, S4) are bought once and never sold
    assert eq["gross_exposure"].iloc[-1] > 0.99
    assert trades.empty
    assert eq["equity"].iloc[-1] > eq["equity"].iloc[0]


def test_delisted_holding_exits_at_last_close_minus_haircut(monkeypatch):
    monkeypatch.setattr(ps, "MOM_HOLD", 1)
    close = pd.DataFrame({"A": 100 * 1.001 ** np.arange(len(DAYS)), "B": np.full(len(DAYS), 50.0)}, index=DAYS)
    close.loc[DAYS[300]:, "A"] = np.nan                      # A stops trading
    last = pd.Series({"A": DAYS[299], "B": DAYS[-1]})
    eq, trades = run_momentum(_panel(close, last_date=last), DAYS[260], DAYS[-1], FREE)
    delisted = trades[trades["exit_reason"] == "DELISTED"].iloc[0]
    assert delisted["exit_date"] == DAYS[300]
    shares = delisted["cost_basis"] / close["A"].loc[delisted["entry_date"]]
    assert delisted["proceeds"] == pytest.approx(shares * close["A"].loc[DAYS[299]] * 0.95)


def test_breakout_enters_next_open_and_stops_out():
    n = len(DAYS)
    price = np.r_[np.linspace(50, 100, 300), np.full(n - 300, 100.0)]
    price[300] = 110.0                                       # breakout day
    price[301:305] = 111.0
    price[305:] = 80.0                                       # collapse -> stop
    close = pd.DataFrame({"X": price}, index=DAYS)
    vol = pd.DataFrame({"X": np.where(np.arange(n) == 300, 5000.0, 1000.0)}, index=DAYS)
    eq, trades = run_breakout(_panel(close, volume=vol), DAYS[250], DAYS[-1], FREE)
    first = trades.iloc[0]
    assert first["entry_date"] == DAYS[301] and first["exit_reason"] == "STOP"
    assert first["exit_date"] == DAYS[305]


def test_judge_flags_no_edge_for_a_copy_of_the_benchmark():
    days = pd.bdate_range("2019-01-01", "2024-07-31")
    nifty = pd.Series(100 * 1.0004 ** np.arange(len(days)), index=days)
    eq = pd.DataFrame({"equity": nifty * 10_000, "gross_exposure": 1.0})
    trades = pd.DataFrame({"pnl": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]})
    report = judge(eq, trades, nifty, pd.Series(0.0004, index=days))
    assert report["verdict"] == "NO DEMONSTRATED EDGE"
    assert not report["checks"]["CAGR beats Nifty by >= 5 pp/yr"]


def _pullback_panel(dip_day=320, recover=True):
    n = len(DAYS)
    strong = 100 * 1.003 ** np.arange(n)
    strong[dip_day - 2: dip_day + 1] *= np.array([0.985, 0.97, 0.955])   # 3-day dip > 3%, below 10-SMA
    if recover:
        strong[dip_day + 1:] *= 1.0                                          # back on trend next day
    weak = np.full(n, 100.0) * 0.9995 ** np.arange(n)
    close = pd.DataFrame({"STRONG": strong, "WEAK": weak}, index=DAYS)
    vol = close * 0 + 1e7
    return _panel(close, volume=vol)


def test_pullback_buys_dip_in_leader_and_hits_target_or_time():
    from backtesting.pit_strategies import run_pullback
    panel = _pullback_panel()
    nifty = pd.Series(100 * 1.0005 ** np.arange(len(DAYS)), index=DAYS)
    eq, trades = run_pullback(panel, DAYS[260], DAYS[-1], nifty, FREE)
    first = trades.iloc[0]
    assert first["entity_id"] == "STRONG" and first["entry_date"] == DAYS[321]
    assert first["exit_reason"] in {"TARGET", "TIME_STOP"}


def test_pullback_stands_aside_when_market_below_200_sma():
    from backtesting.pit_strategies import run_pullback
    panel = _pullback_panel()
    nifty = pd.Series(100 * 0.999 ** np.arange(len(DAYS)), index=DAYS)      # falling market
    eq, trades = run_pullback(panel, DAYS[260], DAYS[-1], nifty, FREE)
    assert trades.empty and eq["gross_exposure"].max() == 0
