"""
===============================================================================
Falcon AI Swing Trading Platform — momentum + short-term dip (academic test)
===============================================================================
Script      : mom_reversal.py
Package     : Backtesting

docs/pullback_diagnostics_preregistration.md, Step 3. Every 10 sessions rank by
the 6-month return skipping the last month; top 10%. REV buys the 10 with the
worst 5-day return; MOM10 buys the whole top 10%. Two tranches with half the
capital each, alternating rebalance dates, fixed 20-session hold (next open to
the open 20 sessions later), 15% catastrophic stop, optional Nifty 200-DMA filter.
===============================================================================
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.mtm_portfolio import CostModel
from backtesting.pit_strategies import Ledger, Panel, _adv, _delisting_exits

STEP, HOLD, TOP, N_REV, CAT_STOP = 10, 20, 0.10, 10, 0.15


def picks_at(panel: Panel, t: int, mode: str, MOM, R5, RAW, TV20, cols):
    day = panel.sessions[t]
    members = [e for e in panel.universe_on(day) if e in cols]
    rows = []
    for e in members:
        j = cols[e]
        if not (RAW[t, j] > 100 and TV20[t, j] >= 1e8 and np.isfinite(MOM[t, j]) and np.isfinite(R5[t, j])):
            continue
        rows.append((e, MOM[t, j], R5[t, j]))
    if len(rows) < 20:
        return []
    d = pd.DataFrame(rows, columns=["e", "mom", "r5"])
    top = d[d.mom >= d.mom.quantile(1 - TOP)]
    if mode == "REV":
        top = top.nsmallest(N_REV, "r5")
    return list(top.e)


def run_mom_reversal(panel: Panel, start, end, nifty: pd.Series, mode: str, use_filter: bool,
                     cost: CostModel | None = None, picks_log: list | None = None):
    s = panel.sessions
    c = panel.close
    O, L = panel.open.to_numpy(float), panel.low.to_numpy(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        MOM = c.shift(21).to_numpy(float) / c.shift(126).to_numpy(float) - 1
        R5 = c.to_numpy(float) / c.shift(5).to_numpy(float) - 1
        RAW = panel.turnover.to_numpy(float) / panel.volume.to_numpy(float)
    TV20 = panel.turnover.rolling(20, min_periods=15).mean().shift(1).to_numpy(float)
    cols = {e: j for j, e in enumerate(c.columns)}
    nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
    ok200 = (nf > nf.rolling(200, min_periods=200).mean()).to_numpy()
    tranches = [Ledger(cost or CostModel(), cash=0.5 * Ledger(cost or CostModel()).cash) for _ in range(2)]
    pending = [None, None]          # tranche -> list of entities to buy at the next open
    days = [i for i, d in enumerate(s) if start <= d <= end]
    first = days[0]
    equity = []
    for i in days:
        day = s[i]
        opens, closes = panel.open.iloc[i], panel.close.iloc[i]
        for k, led in enumerate(tranches):
            _delisting_exits(panel, led, i, day)
            if pending[k] is not None:                       # rebalance: sell everything, buy the new list
                for e in list(led.shares):
                    j = cols[e]
                    if np.isfinite(O[i, j]):
                        led.sell(day, e, O[i, j], _adv(panel, i, e), "HOLD_20")
                names = [e for e in pending[k] if np.isfinite(O[i, cols[e]])]
                if names:
                    each = led.cash * 0.999 / len(names)
                    for e in names:
                        led.buy(day, e, O[i, cols[e]], each, _adv(panel, i, e),
                                {"stop": O[i, cols[e]] * (1 - CAT_STOP), "entry_idx": i})
                pending[k] = None
            for e in list(led.shares):
                m = led.meta[e]
                j = cols[e]
                if m["entry_idx"] < i and np.isfinite(L[i, j]) and L[i, j] <= m["stop"]:
                    o = O[i, j]
                    led.sell(day, e, o if np.isfinite(o) and o < m["stop"] else m["stop"], _adv(panel, i, e), "CAT_STOP")
            led.mark(day, closes)
        tot = sum(led.equity[-1][1] for led in tranches)
        expo = sum(led.equity[-1][1] * led.equity[-1][2] for led in tranches) / tot if tot else 0.0
        equity.append((day, tot, expo))
        if day >= end:
            continue
        n = i - first
        if n % STEP == 0:
            k = (n // STEP) % 2                                 # alternate tranches every 10 sessions
            if use_filter and not ok200[i]:
                pending[k] = []                                 # sit in cash this cycle
            else:
                pending[k] = picks_at(panel, i, mode, MOM, R5, RAW, TV20, cols)
                if picks_log is not None:
                    picks_log.append((i, list(pending[k])))
    eq = pd.DataFrame(equity, columns=["Date", "equity", "gross_exposure"]).set_index("Date")
    trades = []
    for led in tranches:
        trades += led.trades
        end_day = eq.index[-1]
        trades += [{"entity_id": e, "entry_date": m["entry_date"], "exit_date": end_day, "cost_basis": m["cost_basis"],
                    "proceeds": led.shares[e] * m["last_mark"],
                    "pnl": led.shares[e] * m["last_mark"] - m["cost_basis"] - m["costs"], "exit_reason": "OPEN_AT_END"}
                   for e, m in led.meta.items() if e in led.shares]
    return eq, pd.DataFrame(trades), {}
