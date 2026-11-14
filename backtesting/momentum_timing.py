"""
===============================================================================
Falcon AI Swing Trading Platform — A10T: monthly momentum list, v3 breakout timing
===============================================================================
docs/momentum_patterns_preregistration.md, rules 2-7.
  - list: A10's month-end top 20 (passed in as run_momentum's stats["targets"]);
  - first session of a month: holdings not on the new list are sold at the open;
  - a list stock not held is bought at the close of the first session where it has a v3
    REAL_PATTERN setup scanned in the previous 5 sessions and that session has
    High > pivot, Close > pivot, close in the upper half of the range, Nifty > 50-DMA;
  - size equity / 20, limited by cash (several buys on one session split the cash
    evenly, as A10 does);
  - 10% stop from the fill, from the next session (stop, or the open on a gap); no
    re-buy of a stopped stock before the next list; no target, no time stop.
===============================================================================
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.mtm_portfolio import CostModel
from backtesting.pit_strategies import Ledger, Panel, _adv, _delisting_exits, _result


def run_momentum_timing(panel: Panel, start, end, targets: dict, setups: pd.DataFrame, nifty_ok,
                        cost: CostModel | None = None, hold: int = 20, stop_pct: float = 0.10, window: int = 5):
    """targets: {month-end session index: set of entity ids}. setups: entity_id, t (scan session
    index), pivot (v3 REAL_PATTERN only)."""
    ledger = Ledger(cost or CostModel())
    s = panel.sessions
    O, H, L, C = (x.to_numpy(float) for x in (panel.open, panel.high, panel.low, panel.close))
    cols = {e: j for j, e in enumerate(panel.close.columns)}
    by_e = {e: g.sort_values("t")[["t", "pivot"]].to_numpy() for e, g in setups.groupby("entity_id")}
    cur, stopped = set(), set()
    st = {"lists": 0, "buys": 0, "list_slots": 0, "held_at_month_end": 0}
    for i, day in enumerate(s):
        if day < start or day > end:
            continue
        _delisting_exits(panel, ledger, i, day)
        if (i - 1) in targets:                                   # new list: rebalance at this open
            cur, stopped = set(targets[i - 1]), set()
            st["lists"] += 1
            for e in sorted(ledger.shares):
                if e not in cur and np.isfinite(O[i, cols[e]]):
                    ledger.sell(day, e, O[i, cols[e]], _adv(panel, i, e), "REBALANCE")
        for e in sorted(ledger.shares):                          # stops on positions bought earlier
            m, j = ledger.meta[e], cols[e]
            if m.get("entry_idx", i) < i and np.isfinite(L[i, j]) and L[i, j] <= m["stop"]:
                o = O[i, j]
                ledger.sell(day, e, o if np.isfinite(o) and o < m["stop"] else m["stop"], _adv(panel, i, e), "STOP")
                stopped.add(e)
        buys = []
        if bool(nifty_ok[i]):
            for e in sorted(cur):
                if e in ledger.shares or e in stopped or e not in by_e or e not in cols:
                    continue
                arr = by_e[e]
                ok = arr[(arr[:, 0] < i) & (arr[:, 0] >= i - window)]
                if not len(ok):
                    continue
                pivot = ok[-1, 1]
                j = cols[e]
                h, l, c = H[i, j], L[i, j], C[i, j]
                if np.isfinite(c) and h > pivot and c > pivot and h > l and (c - l) / (h - l) >= 0.5:
                    buys.append(e)
        if buys:
            closes = panel.close.iloc[i]
            equity_now = ledger.cash + sum(ledger.value(x, closes) for x in ledger.shares)
            per_name = min(equity_now / hold, ledger.cash / len(buys) * 0.995)
            for e in buys:
                c = C[i, cols[e]]
                if ledger.buy(day, e, c, per_name, _adv(panel, i, e), {"stop": c * (1 - stop_pct), "entry_idx": i}):
                    st["buys"] += 1
        ledger.mark(day, panel.close.iloc[i])
        if i in targets or (i + 1 < len(s) and s[i + 1].month != day.month and cur):
            st["list_slots"] += len(cur)
            st["held_at_month_end"] += sum(1 for e in ledger.shares if e in cur)
    eq, trades = _result(ledger)
    st["buys_per_list"] = round(st["buys"] / max(st["lists"], 1), 2)
    st["held_share_pct"] = round(100 * st["held_at_month_end"] / max(st["list_slots"], 1), 1)
    return eq, trades, st
