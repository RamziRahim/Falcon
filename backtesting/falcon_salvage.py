"""
===============================================================================
Falcon AI Swing Trading Platform — Falcon pattern setups, re-entered
===============================================================================
Script      : falcon_salvage.py
Package     : Backtesting

docs/falcon_salvage_preregistration.md. Trades Falcon's own pre-breakout setups
(data/pit/falcon_setups_*.parquet: scan every 5 sessions, pivot, Falcon stop and
measured-move target) with:
  entry  "pivot_stop"  : buy-stop at the pivot for the 5 sessions after the scan
                         (fill max(pivot, open); skip if open > pivot x 1.03)
         "clean_close" : buy at the close of the first session in that window with
                         High > pivot, Close > pivot, Close >= Open, upper wick < 50%
                         of the range and Volume >= 1.5 x its 20-session average
                         (Falcon's own breakout-volume rule)
  stop   "falcon" (the setup's) or "atr3" (fill - 3 x ATR14)
  target "falcon" (the setup's) or "r3" (fill + 3R)
Orders cancel on a Low (buy-stop) / Close (clean close) at or below the setup stop.
1% risk, <= 25% per position, 10 slots, 40-session time stop, stop wins ties.
===============================================================================
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.mtm_portfolio import CostModel
from backtesting.pit_strategies import Ledger, Panel, _adv, _delisting_exits, _result

SLOTS, RISK, POS_CAP, MAX_STOP, TIME_STOP, WINDOW = 10, 0.01, 0.25, 0.15, 40, 5


def run_setups(panel: Panel, setups: pd.DataFrame, start, end, entry: str, stop_mode: str, target_mode: str,
               cost: CostModel | None = None, info: list | None = None, wick_exit: bool = False):
    ledger = Ledger(cost or CostModel())
    s = panel.sessions
    O, H, L, C, V = (x.to_numpy(float) for x in (panel.open, panel.high, panel.low, panel.close, panel.volume))
    pc = panel.close.shift(1)
    tr = np.maximum(panel.high - panel.low, np.maximum((panel.high - pc).abs(), (panel.low - pc).abs()))
    ATR = tr.rolling(14, min_periods=14).mean().to_numpy(float)
    VS20 = panel.volume.rolling(20, min_periods=20).mean().to_numpy(float)
    cols = {e: j for j, e in enumerate(panel.close.columns)}
    pos = {d: k for k, d in enumerate(s)}
    by_day = {pos[pd.Timestamp(d)]: g for d, g in setups.groupby("scan_date") if pd.Timestamp(d) in pos}
    live, queued = [], set()
    st = {"orders": 0, "filled": 0, "cancelled_stop": 0, "gap_skip": 0, "not_clean": 0, "stop_too_wide": 0,
          "above_target": 0, "slots_full": 0}
    for i, day in enumerate(s):
        if day < start or day > end:
            continue
        _delisting_exits(panel, ledger, i, day)
        closes = panel.close.iloc[i]
        for e in list(queued):
            if e not in ledger.shares:
                queued.discard(e)
            elif np.isfinite(O[i, cols[e]]):
                ledger.sell(day, e, O[i, cols[e]], _adv(panel, i, e), "TIME_STOP")
                queued.discard(e)
        keep = []
        for od in sorted(live, key=lambda x: x["prio"]):
            e, j = od["e"], cols[od["e"]]
            if e in ledger.shares or i > od["exp"]:
                continue
            o, h, l, c = O[i, j], H[i, j], L[i, j], C[i, j]
            if not np.isfinite(o):
                keep.append(od)
                continue
            fill, kind = None, None
            if entry == "pivot_stop":
                if h >= od["pivot"]:
                    if o > od["pivot"] * 1.03:
                        st["gap_skip"] += 1
                        continue
                    fill = max(od["pivot"], o)
                elif l <= od["stop"]:
                    st["cancelled_stop"] += 1
                    continue
            else:
                if h > od["pivot"]:
                    rng = h - l
                    clean = (c > od["pivot"] and c >= o and rng > 0 and (h - max(o, c)) / rng < 0.5
                             and np.isfinite(VS20[i, j]) and V[i, j] >= 1.5 * VS20[i, j])
                    if clean:
                        fill = c
                    else:
                        st["not_clean"] += 1
                if fill is None and c <= od["stop"]:
                    st["cancelled_stop"] += 1
                    continue
            if fill is None:
                keep.append(od)
                continue
            if len(ledger.shares) >= SLOTS:
                st["slots_full"] += 1
                keep.append(od)
                continue
            stop = od["stop"] if stop_mode == "falcon" else fill - 3.0 * ATR[i, j]
            if not (np.isfinite(stop) and stop < fill):
                continue
            dist = (fill - stop) / fill
            if dist > MAX_STOP:
                st["stop_too_wide"] += 1
                continue
            target = od["target"] if target_mode == "falcon" else fill + 3.0 * (fill - stop)
            if target <= fill:
                st["above_target"] += 1
                continue
            equity_now = ledger.cash + sum(ledger.value(x, closes) for x in ledger.shares)
            value = min(RISK * equity_now / dist, POS_CAP * equity_now, ledger.cash * 0.999)
            if value > 0 and ledger.buy(day, e, fill, value, _adv(panel, i, e),
                                        {"stop": stop, "target": target, "entry_idx": i, "trig": od["pivot"],
                                         "at_close": entry == "clean_close"}):
                st["filled"] += 1
                if info is not None:
                    info.append({"entity_id": e, "entry_date": day, "pattern": od["pattern"], "fill": fill,
                                 "pivot": od["pivot"], "fill_close": c, "wick_fakeout": bool(c < od["pivot"]),
                                 "stop": stop, "target": target})
        live = keep
        for e in list(ledger.shares):
            m = ledger.meta[e]
            j = cols[e]
            if m["at_close"] and m["entry_idx"] == i:
                continue
            o, h, l = O[i, j], H[i, j], L[i, j]
            gap_ok = m["entry_idx"] < i and np.isfinite(o)
            if np.isfinite(l) and l <= m["stop"]:
                ledger.sell(day, e, o if gap_ok and o < m["stop"] else m["stop"], _adv(panel, i, e), "STOP")
            elif np.isfinite(h) and h >= m["target"]:
                ledger.sell(day, e, o if gap_ok and o > m["target"] else m["target"], _adv(panel, i, e), "TARGET")
            elif wick_exit and m["entry_idx"] == i and np.isfinite(C[i, j]) and C[i, j] < m["trig"]:
                ledger.sell(day, e, C[i, j], _adv(panel, i, e), "WICK_EXIT")
        ledger.mark(day, closes)
        if day >= end:
            continue
        for e in ledger.shares:
            if i - ledger.meta[e]["entry_idx"] + 1 >= TIME_STOP:
                queued.add(e)
        g = by_day.get(i)
        if g is not None:
            busy = set(ledger.shares) | {od["e"] for od in live}
            for r in g.itertuples():
                if r.entity_id in busy or r.entity_id not in cols:
                    continue
                st["orders"] += 1
                live.append({"e": r.entity_id, "pivot": r.pivot, "stop": r.stop, "target": r.target,
                             "exp": i + WINDOW, "prio": r.sort_key, "pattern": r.pattern})
    eq, trades = _result(ledger)
    return eq, trades, st
