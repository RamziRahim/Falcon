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


def run_setups_v2(panel: Panel, setups: pd.DataFrame, start, end, nifty_ok, cost: CostModel | None = None,
                  slots: int = SLOTS, entry: str = "close", retest_window: int = 10):
    """docs/falcon_v2_preregistration.md, rules 6-10. setups: entity_id, scan_date, pivot, stop,
    mom_rank (already filtered by rules 4-5). nifty_ok: boolean array over panel.sessions.
    Entry at the close of the first session in the 5 after the scan with High > pivot,
    Close > pivot, close in the upper half of the range and the Nifty above its 50-DMA.
    Stop = max(Falcon stop, fill - 3 ATR); target 3R; 40-session time stop.
    entry (docs/falcon_v2_retest_preregistration.md; default "close" = FV2 unchanged):
      "close"        buy the close of the breakout day (FV2)
      "retest_pivot" breakout day buys nothing; limit at the pivot for the next
                     `retest_window` sessions, fill min(pivot, open), same-day stop check (FV2R)
      "retest_close" same window, buy the close of the first session with Low <= pivot and
                     Close > pivot; no exit checks on the entry session (FV2RC)
      "retest_ema"   limit at the previous session's 20-EMA of closes while it is above
                     Falcon's stop, fill min(EMA, open), same-day stop check (FV2RE)
    Retest stops use ATR(14) as of the session before the fill."""
    ledger = Ledger(cost or CostModel())
    s = panel.sessions
    O, H, L, C = (x.to_numpy(float) for x in (panel.open, panel.high, panel.low, panel.close))
    pc = panel.close.shift(1)
    tr = np.maximum(panel.high - panel.low, np.maximum((panel.high - pc).abs(), (panel.low - pc).abs()))
    ATR = tr.rolling(14, min_periods=14).mean().to_numpy(float)
    EMA = panel.close.ewm(span=20, adjust=False, min_periods=20).mean().to_numpy(float) if entry == "retest_ema" else None
    cols = {e: j for j, e in enumerate(panel.close.columns)}
    pos = {d: k for k, d in enumerate(s)}
    by_day = {pos[pd.Timestamp(d)]: g for d, g in setups.groupby("scan_date") if pd.Timestamp(d) in pos}
    live, queued = [], set()
    st = {"orders": 0, "pivot_touches": 0, "touch_rejected": 0, "filled": 0, "cancelled_stop": 0,
          "stop_too_wide": 0, "slots_full": 0}
    if entry != "close":
        st.update({"breakouts": 0, "retest_filled": 0, "retest_expired": 0, "retest_cancelled_stop": 0,
                   "fill_day_stopped": 0, "never_retested": 0})
        no_retest_ret = []
    for i, day in enumerate(s):
        if day < start or day > end:
            continue
        _delisting_exits(panel, ledger, i, day)
        closes = panel.close.iloc[i]
        for e in sorted(queued):
            if e not in ledger.shares:
                queued.discard(e)
            elif np.isfinite(O[i, cols[e]]):
                ledger.sell(day, e, O[i, cols[e]], _adv(panel, i, e), "TIME_STOP")
                queued.discard(e)
        for e in list(ledger.shares):                                  # exits (positions bought earlier)
            m = ledger.meta[e]
            j = cols[e]
            o, h, l = O[i, j], H[i, j], L[i, j]
            if np.isfinite(l) and l <= m["stop"]:
                ledger.sell(day, e, o if np.isfinite(o) and o < m["stop"] else m["stop"], _adv(panel, i, e), "STOP")
            elif np.isfinite(h) and h >= m["target"]:
                ledger.sell(day, e, o if np.isfinite(o) and o > m["target"] else m["target"], _adv(panel, i, e), "TARGET")
        keep = []
        for od in sorted(live, key=lambda x: (-x["mom"], x["e"])):     # entries at today's close
            e, j = od["e"], cols[od["e"]]
            if entry != "close" and od.get("bo") is not None:
                if e in ledger.shares:
                    continue
                if i > od["bo"] + retest_window:
                    st["retest_expired"] += 1
                    if not od["touched"]:
                        st["never_retested"] += 1
                        k = od["bo"] + 40
                        if k < len(s) and np.isfinite(C[k, j]):
                            no_retest_ret.append(C[k, j] / od["bo_close"] - 1)
                    continue
                o, h, l, c = O[i, j], H[i, j], L[i, j], C[i, j]
                if not (np.isfinite(o) and np.isfinite(h) and np.isfinite(l) and np.isfinite(c)):
                    keep.append(od)
                    continue
                if l <= od["pivot"]:
                    od["touched"] = True
                fill, at_close = None, False
                if entry == "retest_pivot" and l <= od["pivot"]:
                    fill = min(od["pivot"], o)
                elif entry == "retest_close" and l <= od["pivot"] and c > od["pivot"]:
                    fill, at_close = c, True
                elif entry == "retest_ema" and i > 0 and np.isfinite(EMA[i - 1, j]) and EMA[i - 1, j] > od["stop"] \
                        and l <= EMA[i - 1, j]:
                    fill = min(EMA[i - 1, j], o)
                if fill is not None:
                    atr = ATR[i - 1, j] if i > 0 else np.nan
                    stop = max(od["stop"], fill - 3.0 * atr) if np.isfinite(atr) else od["stop"]
                    if not stop < fill or (fill - stop) / fill > MAX_STOP:
                        st["stop_too_wide"] += 1
                        continue
                    if len(ledger.shares) >= slots:
                        st["slots_full"] += 1
                    else:
                        dist = (fill - stop) / fill
                        equity_now = ledger.cash + sum(ledger.value(x, closes) for x in ledger.shares)
                        value = min(RISK * equity_now / dist, POS_CAP * equity_now, ledger.cash * 0.999)
                        if value > 0 and ledger.buy(day, e, fill, value, _adv(panel, i, e),
                                                    {"stop": stop, "target": fill + 3.0 * (fill - stop), "entry_idx": i}):
                            st["filled"] += 1
                            st["retest_filled"] += 1
                            if not at_close and l <= stop:
                                ledger.sell(day, e, stop, _adv(panel, i, e), "STOP")
                                st["fill_day_stopped"] += 1
                        continue
                if c <= od["stop"]:
                    st["retest_cancelled_stop"] += 1
                    continue
                keep.append(od)
                continue
            if e in ledger.shares or i > od["exp"]:
                continue
            o, h, l, c = O[i, j], H[i, j], L[i, j], C[i, j]
            if not (np.isfinite(o) and np.isfinite(h) and np.isfinite(l) and np.isfinite(c)):
                keep.append(od)
                continue
            if h > od["pivot"] and entry != "close":
                st["pivot_touches"] += 1
                if c > od["pivot"] and h > l and (c - l) / (h - l) >= 0.5 and bool(nifty_ok[i]):
                    st["breakouts"] += 1
                    od.update({"bo": i, "bo_close": c, "touched": False})
                    keep.append(od)
                    continue
                st["touch_rejected"] += 1
            elif h > od["pivot"]:
                st["pivot_touches"] += 1
                ok = c > od["pivot"] and h > l and (c - l) / (h - l) >= 0.5 and bool(nifty_ok[i])
                if not ok:
                    st["touch_rejected"] += 1
                else:
                    stop = max(od["stop"], c - 3.0 * ATR[i, j]) if np.isfinite(ATR[i, j]) else od["stop"]
                    if not stop < c or (c - stop) / c > MAX_STOP:
                        st["stop_too_wide"] += 1
                        continue
                    if len(ledger.shares) >= slots:
                        st["slots_full"] += 1
                        keep.append(od)
                        continue
                    dist = (c - stop) / c
                    equity_now = ledger.cash + sum(ledger.value(x, closes) for x in ledger.shares)
                    value = min(RISK * equity_now / dist, POS_CAP * equity_now, ledger.cash * 0.999)
                    if value > 0 and ledger.buy(day, e, c, value, _adv(panel, i, e),
                                                {"stop": stop, "target": c + 3.0 * (c - stop), "entry_idx": i}):
                        st["filled"] += 1
                    continue
            if c <= od["stop"]:
                st["cancelled_stop"] += 1
                continue
            keep.append(od)
        live = keep
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
                live.append({"e": r.entity_id, "pivot": r.pivot, "stop": r.stop, "exp": i + WINDOW,
                             "mom": r.mom_rank if np.isfinite(r.mom_rank) else -1.0})
    eq, trades = _result(ledger)
    if entry != "close":
        st["no_retest_40d_ret_pct"] = round(100 * float(np.mean(no_retest_ret)), 2) if no_retest_ret else None
        st["no_retest_40d_n"] = len(no_retest_ret)
    return eq, trades, st
