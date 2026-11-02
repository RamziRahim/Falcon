import numpy as np
import pandas as pd
import pytest

from backtesting.breakout_entries import falcon_setup_from_analysis, run_strategy_f
from backtesting.mtm_portfolio import CostModel
from backtesting.pit_strategies import Panel

FREE = CostModel(statutory=0.0, spread_tiers=((0, 0.0),), impact_coeff=0.0)
DAYS = pd.bdate_range("2018-01-01", periods=120)


def _panel(o, h, l, c):
    cols = c.columns
    me = c.index.to_series().groupby(c.index.to_period("M")).max()
    vol = c * 0 + 1e6
    return Panel(o, h, l, c, vol, c * vol, {m: set(cols) for m in me},
                 pd.Series(c.index[-1], index=cols), pd.Series(cols, index=cols))


def _frames(close, high=None, low=None, open_=None):
    c = pd.DataFrame({"X": close}, index=DAYS)
    return (pd.DataFrame({"X": open_ if open_ is not None else close}, index=DAYS),
            pd.DataFrame({"X": high if high is not None else close}, index=DAYS),
            pd.DataFrame({"X": low if low is not None else close}, index=DAYS), c)


def _setup(scan_idx, pivot=100.0, stop=95.0, target=110.0):
    return pd.DataFrame([{"entity_id": "X", "scan_date": DAYS[scan_idx], "priority": 0, "pivot": pivot,
                          "stop": stop, "target": target, "distance": 0.02}])


def test_f_fills_at_pivot_on_breakout_day_and_hits_target():
    n = len(DAYS)
    close = np.full(n, 98.0); high = close + 1; low = close - 1
    high[52] = 101.0                         # breakout day: trades through the 100 pivot
    close[53:] = 105.0; high[53:] = 106; low[53:] = 104
    high[60] = 111.0                         # target day
    o, h, l, c = _frames(close, high, low)
    eq, trades = run_strategy_f(_panel(o, h, l, c), _setup(50), DAYS[0], DAYS[-1], FREE)
    t = trades.iloc[0]
    assert t["entry_date"] == DAYS[52] and t["exit_reason"] == "TARGET" and t["exit_date"] == DAYS[60]
    assert t["proceeds"] / t["cost_basis"] == pytest.approx(1.10)


def test_f_gap_above_pivot_more_than_3pct_is_not_chased_and_order_expires():
    n = len(DAYS)
    close = np.full(n, 98.0); high = close + 1; low = close - 1; open_ = close.copy()
    open_[51] = 104.0; high[51] = 105; close[51] = 104      # gap 4% above pivot -> no fill
    o, h, l, c = _frames(close, high, low, open_)
    eq, trades = run_strategy_f(_panel(o, h, l, c), _setup(50), DAYS[0], DAYS[-1], FREE)
    assert trades.empty


def test_f_order_cancelled_if_stop_trades_before_fill():
    n = len(DAYS)
    close = np.full(n, 98.0); high = close + 1; low = close - 1
    low[51] = 94.0                           # stop level hit first
    high[53] = 101.0                         # later breakout must NOT fill
    o, h, l, c = _frames(close, high, low)
    eq, trades = run_strategy_f(_panel(o, h, l, c), _setup(50), DAYS[0], DAYS[-1], FREE)
    assert trades.empty


def test_f_order_lives_exactly_five_sessions():
    n = len(DAYS)
    close = np.full(n, 98.0); high = close + 1; low = close - 1
    high[56] = 101.0                         # 6th session after the scan -> expired
    o, h, l, c = _frames(close, high, low)
    assert run_strategy_f(_panel(o, h, l, c), _setup(50), DAYS[0], DAYS[-1], FREE)[1].empty
    high[55] = 101.0                         # 5th session -> fills
    o, h, l, c = _frames(close, high, low)
    assert run_strategy_f(_panel(o, h, l, c), _setup(50), DAYS[0], DAYS[-1], FREE)[1].iloc[0]["entry_date"] == DAYS[55]


def test_falcon_setup_uses_falcon_plan_and_skips_confirmed_breakouts():
    analysis = {"vcp": {"is_vcp_setup": True, "is_breakout_confirmed": False, "pivot_level": 100.0,
                        "final_contraction_low": 94.0, "first_contraction_low": 80.0}}
    s = falcon_setup_from_analysis(analysis, close=97.0, atr=2.0)
    assert s and s["pattern"] == "is_vcp_breakout" and s["stop"] < 100 < s["target"]
    analysis["vcp"]["is_breakout_confirmed"] = True
    assert falcon_setup_from_analysis(analysis, close=97.0, atr=2.0) is None
    analysis["vcp"]["is_breakout_confirmed"] = False
    assert falcon_setup_from_analysis(analysis, close=90.0, atr=2.0) is None     # >5% below pivot


def test_s_buys_new_highs_only_in_the_strong_group(monkeypatch):
    import backtesting.breakout_entries as be
    monkeypatch.setattr(be, "S_PEERS", 3)
    monkeypatch.setattr(be, "S_CORR_LEN", 60)
    monkeypatch.setattr(be, "S_CORR_MIN", 50)
    monkeypatch.setattr(be, "S_MOM_LEN", 40)
    days = pd.bdate_range("2018-01-01", periods=420)
    rng = np.random.default_rng(3)
    common_up, common_flat = rng.normal(0.002, 0.01, len(days)), rng.normal(0.0, 0.01, len(days))
    cols = {}
    for k in range(4):
        cols[f"UP{k}"] = 100 * np.cumprod(1 + common_up + rng.normal(0, 0.003, len(days)))
        cols[f"FLAT{k}"] = 100 * np.cumprod(1 + common_flat + rng.normal(0, 0.003, len(days)))
    c = pd.DataFrame(cols, index=days)
    panel = _panel(c, c * 1.01, c * 0.99, c)
    nifty = pd.Series(100 * 1.0005 ** np.arange(len(days)), index=days)
    eq, trades = be.run_strategy_s(panel, days[260], days[-1], nifty, FREE)
    assert not trades.empty
    assert trades["entity_id"].str.startswith("UP").all()
