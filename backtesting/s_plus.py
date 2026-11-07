"""
===============================================================================
Falcon AI Swing Trading Platform — S+ (improved momentum breakout, 1:3)
===============================================================================
Script      : s_plus.py
Package     : Backtesting

docs/s_plus_preregistration.md. backtesting/swing_risk.run_swing_risk (the
"#3" strategy: S entries + swing-low stop + 1% risk + 1:3, 20 sessions) with
three switchable changes:

  market_filter : new orders only when the Nifty 50 close > its 50-session SMA
  time_stop     : 40 sessions instead of 20
  atr_cap       : stop = the higher of the swing-low stop and fill - 3 x ATR(14)
                  (the far-away swing lows no longer cause a skip)

With all three off it reproduces run_swing_risk exactly.
===============================================================================
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.mtm_portfolio import CostModel
from backtesting.pit_strategies import Ledger, Panel, _adv, _delisting_exits, _result
from backtesting.swing_risk import ATR_LEN, MAX_STOP_DIST, POS_CAP, RISK, SLOTS, pivot_lows, swing_stop

ATR_CAP = 3.0


def run_s_plus(panel: Panel, start, end, order_fn, nifty: pd.Series, r_multiple: float = 3.0,
               market_filter: bool = False, time_stop: int = 20, atr_cap: bool = False,
               cost: CostModel | None = None, fixed_stop: float | None = None, fixed_tgt: float | None = None):
    """fixed_stop / fixed_tgt (docs/fixed_5_15_preregistration.md): stop = fill x (1 - fixed_stop),
    target = fill x (1 + fixed_tgt), replacing the swing-low stop and R target."""
    ledger = Ledger(cost or CostModel())
    sessions = panel.sessions
    piv = pivot_lows(panel)
    pc = panel.close.shift(1)
    tr = np.maximum(panel.high - panel.low, np.maximum((panel.high - pc).abs(), (panel.low - pc).abs()))
    atr = tr.rolling(ATR_LEN, min_periods=ATR_LEN).mean()
    nf = nifty.reindex(nifty.index.union(sessions)).ffill().reindex(sessions)
    market_ok = (nf > nf.rolling(50, min_periods=50).mean()).to_numpy()
    live, queued_exits = [], set()
    skipped = {"no_swing_low": 0, "gap_below_stop": 0, "stop_too_wide": 0, "market_filter_days": 0}
    for i, day in enumerate(sessions):
        if day < start or day > end:
            continue
        _delisting_exits(panel, ledger, i, day)
        opens, highs, lows, closes = panel.open.iloc[i], panel.high.iloc[i], panel.low.iloc[i], panel.close.iloc[i]
        for e in list(queued_exits):
            if e not in ledger.shares:
                queued_exits.discard(e)
            elif np.isfinite(opens.get(e, np.nan)):
                ledger.sell(day, e, opens[e], _adv(panel, i, e), "TIME_STOP")
                queued_exits.discard(e)
        still_live = []
        for od in sorted(live, key=lambda o: o["priority"]):
            e = od["entity"]
            if e in ledger.shares:
                continue
            o, hi, lo = opens.get(e, np.nan), highs.get(e, np.nan), lows.get(e, np.nan)
            fill = None
            if np.isfinite(o) and len(ledger.shares) < SLOTS:
                if od["type"] == "market":
                    if o <= od["ref"] * (1 + od["max_gap"]):
                        fill = o
                elif np.isfinite(hi) and hi >= od["ref"] and o <= od["ref"] * (1 + od["max_gap"]):
                    fill = max(od["ref"], o)
            if fill is not None:
                stop = od["stop"]
                if fixed_stop is not None:
                    stop = fill * (1 - fixed_stop)
                if atr_cap and fixed_stop is None and np.isfinite(od["atr"]):
                    stop = max(stop if stop is not None else -np.inf, fill - ATR_CAP * od["atr"])
                if stop is None:
                    skipped["no_swing_low"] += 1
                    continue
                if fill <= stop:
                    skipped["gap_below_stop"] += 1
                    continue
                dist = (fill - stop) / fill
                if dist > MAX_STOP_DIST:
                    skipped["stop_too_wide"] += 1
                    continue
                equity_now = ledger.cash + sum(ledger.value(x, opens) for x in ledger.shares)
                value = min(RISK * equity_now / dist, POS_CAP * equity_now, ledger.cash * 0.999)
                if value > 0:
                    ledger.buy(day, e, fill, value, _adv(panel, i, e),
                               {"stop": stop, "entry_idx": i,
                                "target": fill * (1 + fixed_tgt) if fixed_tgt is not None else fill + r_multiple * (fill - stop)})
                continue
            if od["type"] == "stop" and i < od["expires_idx"] and not (
                    od.get("cancel_below") is not None and np.isfinite(lo) and lo <= od["cancel_below"]):
                still_live.append(od)
        live = still_live
        for e in list(ledger.shares):
            m = ledger.meta[e]
            o, hi, lo = opens.get(e, np.nan), highs.get(e, np.nan), lows.get(e, np.nan)
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
        if market_filter and not market_ok[i]:
            skipped["market_filter_days"] += 1
            continue
        pending = {od["entity"] for od in live}
        for od in order_fn(i, day, set(ledger.shares) | pending):
            if od[0] == "market":
                _, e, ref, gap, pr = od
                rec = {"type": "market", "entity": e, "ref": ref, "max_gap": gap, "priority": pr}
            else:
                _, e, trig, gap, pr, valid, cancel = od
                rec = {"type": "stop", "entity": e, "ref": trig, "max_gap": gap, "priority": pr,
                       "expires_idx": i + valid, "cancel_below": cancel}
            stop = swing_stop(panel, piv, atr, i, e, min(rec["ref"], closes.get(e, np.nan)))
            if stop is None and not atr_cap and fixed_stop is None:
                skipped["no_swing_low"] += 1
                continue
            rec["stop"] = stop
            rec["atr"] = atr.iloc[i].get(e, np.nan)
            live.append(rec)
    return (*_result(ledger), skipped)
