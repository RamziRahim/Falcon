"""
===============================================================================
Falcon AI Swing Trading Platform — #3 with retest entries
===============================================================================
Script      : s_retest.py
Package     : Backtesting

docs/s_retest_preregistration.md. Same breakout signals as #3 (S entries,
Nifty > 50-SMA at the signal close). A breakout happens on day b when the
next-day buy-stop at the 20-day high L would have filled (high >= L and
open <= L x 1.03). Instead of buying it:

  "limit"   : limit buy at L on sessions b+1 .. b+WATCH; fill = min(open, L).
              Stop = #3's swing-low stop (signal day). Target R x risk.
  "reclaim" : wait for a low <= L (b+1 .. b+WATCH), then a close > L in the same
              window; buy at the next open (skip if > 3% above that close).
              Stop = lowest low from b+1 to the reclaim day - 0.25 ATR(14).
              Target R x risk.
Skip if the stop is > 15% below the fill or at/above it. 1% risk, <= 25% per
position, <= 10 positions, 20-session time stop, stop wins ties.
===============================================================================
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.mtm_portfolio import CostModel
from backtesting.pit_strategies import Ledger, Panel, _adv, _delisting_exits, _result
from backtesting.swing_risk import ATR_LEN, MAX_STOP_DIST, POS_CAP, RISK, SLOTS, pivot_lows, swing_stop

WATCH, BUFFER, RECLAIM_GAP = 10, 0.25, 0.03


def run_retest(panel: Panel, start, end, order_fn, nifty: pd.Series, mode: str, r_multiple: float = 3.0,
               time_stop: int = 20, cost: CostModel | None = None):
    assert mode in ("limit", "reclaim")
    ledger = Ledger(cost or CostModel())
    s = panel.sessions
    piv = pivot_lows(panel)
    pc = panel.close.shift(1)
    tr = np.maximum(panel.high - panel.low, np.maximum((panel.high - pc).abs(), (panel.low - pc).abs()))
    atr = tr.rolling(ATR_LEN, min_periods=ATR_LEN).mean()
    A = atr.to_numpy(float)
    O, H, L, C = (x.to_numpy(float) for x in (panel.open, panel.high, panel.low, panel.close))
    cols = {e: j for j, e in enumerate(panel.close.columns)}
    nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
    market_ok = (nf > nf.rolling(50, min_periods=50).mean()).to_numpy()
    pending_bo, watch, orders, queued_exits = [], {}, [], set()
    st = {"breakouts": 0, "retested": 0, "reclaimed": 0, "filled": 0, "expired": 0,
          "stop_skip": 0, "too_wide": 0, "gap_skip": 0}
    for i, day in enumerate(s):
        if day < start or day > end:
            continue
        _delisting_exits(panel, ledger, i, day)
        opens, closes = panel.open.iloc[i], panel.close.iloc[i]
        for e in list(queued_exits):
            if e not in ledger.shares:
                queued_exits.discard(e)
            elif np.isfinite(opens.get(e, np.nan)):
                ledger.sell(day, e, opens[e], _adv(panel, i, e), "TIME_STOP")
                queued_exits.discard(e)

        def try_buy(e, fill, stop, priority):
            if e in ledger.shares or len(ledger.shares) >= SLOTS:
                return False
            if not np.isfinite(stop) or fill <= stop:
                st["stop_skip"] += 1
                return True
            dist = (fill - stop) / fill
            if dist > MAX_STOP_DIST:
                st["too_wide"] += 1
                return True
            equity_now = ledger.cash + sum(ledger.value(x, opens) for x in ledger.shares)
            value = min(RISK * equity_now / dist, POS_CAP * equity_now, ledger.cash * 0.999)
            if value > 0:
                ledger.buy(day, e, fill, value, _adv(panel, i, e),
                           {"stop": stop, "target": fill + r_multiple * (fill - stop), "entry_idx": i})
                st["filled"] += 1
            return True

        # 1) reclaim orders placed yesterday: buy at today's open
        for od in sorted(orders, key=lambda o: o["priority"]):
            j = cols[od["entity"]]
            o = O[i, j]
            if not np.isfinite(o):
                continue
            if o > od["ref"] * (1 + RECLAIM_GAP):
                st["gap_skip"] += 1
                continue
            try_buy(od["entity"], o, od["stop"], od["priority"])
        orders = []
        # 2) breakouts that happen today (yesterday's buy-stop would fill) start a watch tomorrow
        for bo in pending_bo:
            e, j, lvl = bo["entity"], cols[bo["entity"]], bo["level"]
            if np.isfinite(O[i, j]) and H[i, j] >= lvl and O[i, j] <= lvl * (1 + bo["gap"]) and e not in watch:
                st["breakouts"] += 1
                watch[e] = {"level": lvl, "b": i, "stop": bo["stop"], "priority": bo["priority"],
                            "touched": False, "low": np.inf}
        pending_bo = []
        # 3) watched stocks, sessions b+1 .. b+WATCH
        for e in sorted(watch, key=lambda x: watch[x]["priority"]):
            w = watch[e]
            j = cols[e]
            if i <= w["b"]:
                continue
            if i > w["b"] + WATCH or e in ledger.shares:
                st["expired"] += 1 if e not in ledger.shares else 0
                watch.pop(e)
                continue
            if not np.isfinite(L[i, j]):
                continue
            lvl = w["level"]
            if mode == "limit":
                if L[i, j] <= lvl:
                    if not w["touched"]:
                        st["retested"] += 1
                    w["touched"] = True
                    if try_buy(e, min(O[i, j], lvl), w["stop"], w["priority"]):
                        watch.pop(e)
            else:
                if L[i, j] <= lvl:
                    if not w["touched"]:
                        st["retested"] += 1
                    w["touched"] = True
                if w["touched"]:
                    w["low"] = min(w["low"], L[i, j])
                    if C[i, j] > lvl and np.isfinite(A[i, j]):
                        st["reclaimed"] += 1
                        orders.append({"entity": e, "ref": C[i, j], "stop": w["low"] - BUFFER * A[i, j],
                                       "priority": w["priority"]})
                        watch.pop(e)
        # 4) exits
        for e in list(ledger.shares):
            m = ledger.meta[e]
            j = cols[e]
            o, hi, lo = O[i, j], H[i, j], L[i, j]
            gap_ok = m["entry_idx"] < i and np.isfinite(o)
            if np.isfinite(lo) and lo <= m["stop"]:
                ledger.sell(day, e, o if gap_ok and o < m["stop"] else m["stop"], _adv(panel, i, e), "STOP")
            elif np.isfinite(hi) and hi >= m["target"]:
                ledger.sell(day, e, o if gap_ok and o > m["target"] else m["target"], _adv(panel, i, e), "TARGET")
        ledger.mark(day, closes)
        if day >= end:
            continue
        for e in ledger.shares:
            if i - ledger.meta[e]["entry_idx"] + 1 >= time_stop:
                queued_exits.add(e)
        # 5) today's breakout signals (for tomorrow), Nifty filter at the signal close
        if not market_ok[i]:
            continue
        busy = set(ledger.shares) | set(watch) | {od["entity"] for od in orders}
        for od in order_fn(i, day, busy):
            if od[0] != "stop":
                continue
            _, e, trig, gap, pr, valid, cancel = od
            stop = swing_stop(panel, piv, atr, i, e, min(trig, closes.get(e, np.nan))) if mode == "limit" else 0.0
            if stop is None:
                continue
            pending_bo.append({"entity": e, "level": trig, "gap": gap, "priority": pr, "stop": stop})
    eq, trades = _result(ledger)
    return eq, trades, st
