"""
===============================================================================
Falcon AI Swing Trading Platform — Swing-Low Stop, 1% Risk, Fixed R Target
===============================================================================
Script      : swing_risk.py
Package     : Backtesting

docs/swing_low_risk_preregistration.md: the F, S, B and MR entry signals are
reused exactly (backtesting/fixed_bracket.py generators); only stop, sizing
and target change:

  stop   = most recent confirmed swing low (Falcon fractal, 3 bars each side,
           confirmed on or before the signal day, within 60 sessions, below
           the order price) minus 0.25 x ATR(14) on the signal day
  size   = 1% of current equity at risk: value = 0.01 x equity x fill / (fill - stop),
           capped at 25% of equity and at available cash; at most 10 positions
  skip   = no swing low found, fill at/below the stop, or stop > 15% below the fill
  target = fill + R x (fill - stop), R = 2 or 3
  time   = 20 sessions, sold at the next open
===============================================================================
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.mtm_portfolio import CostModel
from backtesting.pit_strategies import Ledger, Panel, _adv, _delisting_exits, _result

PIVOT_W, LOOKBACK, ATR_LEN, BUFFER_ATR = 3, 60, 14, 0.25
RISK, POS_CAP, SLOTS, MAX_STOP_DIST, TIME_STOP = 0.01, 0.25, 10, 0.15, 20


def pivot_lows(panel: Panel) -> dict:
    """entity -> sorted array of session indices that are fractal swing lows:
    no bar within PIVOT_W on either side has a strictly lower Low (same rule
    as technical_analysis/pattern_system/swing_detector.py)."""
    low = panel.low.to_numpy(dtype=float)
    n = len(low)
    beaten = np.zeros_like(low, dtype=bool)
    for r in range(1, PIVOT_W + 1):
        left = np.full_like(low, np.nan)
        right = np.full_like(low, np.nan)
        left[r:] = low[:-r]
        right[:-r] = low[r:]
        with np.errstate(invalid="ignore"):
            beaten |= (left < low) | (right < low)
    valid = np.isfinite(low)
    valid[:PIVOT_W] = False
    valid[n - PIVOT_W:] = False
    mask = valid & ~beaten
    return {e: np.flatnonzero(mask[:, j]) for j, e in enumerate(panel.low.columns)}


def swing_stop(panel: Panel, piv: dict, atr: pd.DataFrame, i: int, e, ref: float):
    """Stop for an order placed at the close of session i, or None."""
    idx = piv.get(e)
    if idx is None or not np.isfinite(ref):
        return None
    a = atr.iloc[i].get(e, np.nan)
    if not np.isfinite(a):
        return None
    lows = panel.low[e].to_numpy()
    k = np.searchsorted(idx, i - PIVOT_W, side="right") - 1    # confirmed by day i
    while k >= 0 and idx[k] >= i - LOOKBACK:
        lv = lows[idx[k]]
        if lv < ref:
            return lv - BUFFER_ATR * a
        k -= 1
    return None


def run_swing_risk(panel: Panel, start, end, order_fn, r_multiple: float, cost: CostModel | None = None):
    ledger = Ledger(cost or CostModel())
    sessions = panel.sessions
    piv = pivot_lows(panel)
    pc = panel.close.shift(1)
    tr = np.maximum(panel.high - panel.low, np.maximum((panel.high - pc).abs(), (panel.low - pc).abs()))
    atr = tr.rolling(ATR_LEN, min_periods=ATR_LEN).mean()
    live, queued_exits = [], set()
    skipped = {"no_swing_low": 0, "gap_below_stop": 0, "stop_too_wide": 0}
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
                               {"stop": stop, "target": fill + r_multiple * (fill - stop), "entry_idx": i,
                                "stop_dist": dist})
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
            if i - ledger.meta[e]["entry_idx"] + 1 >= TIME_STOP:
                queued_exits.add(e)
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
            if stop is None:
                skipped["no_swing_low"] += 1
                continue
            rec["stop"] = stop
            live.append(rec)
    equity, trades = _result(ledger)
    return equity, trades, skipped
