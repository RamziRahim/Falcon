"""
===============================================================================
Falcon AI Swing Trading Platform — Exit Variants (breakout-candle stop, partial exit)
===============================================================================
Script      : exit_variants.py
Package     : Backtesting

docs/exit_variants_preregistration.md. Same entries, costs, 1% risk sizing,
limits and fill conventions as backtesting/swing_risk.py, with two changes
that can be switched on separately:

  stop_mode="candle"  (Test 1, breakout entries S, B, F)
      B (buy next open after a breakout close): stop = breakout-day low - 0.25 ATR,
        known at the signal close.
      S, F (buy-stop that fills on the breakout day): stop = the fill day's
        low - 0.25 ATR, set at that day's close (a stop below the day's own
        low cannot trade that day). Size at the fill uses the previous
        session's low - 0.25 ATR, the only candle known at that moment.
      target = fill x (1 + target_pct), target_pct = 5% or 8%.

  partial=True  (Test 2, all four entries, swing-low stop, 1:2 and 1:3)
      at fill + R/2 x (fill - stop) sell half; the stop on the rest moves to
      the fill price from the next session; the rest exits at the full
      target, the break-even stop, or the time stop.
===============================================================================
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.mtm_portfolio import CostModel
from backtesting.pit_strategies import Ledger, Panel, _adv, _delisting_exits
from backtesting.swing_risk import (ATR_LEN, BUFFER_ATR, MAX_STOP_DIST, POS_CAP, RISK, SLOTS, TIME_STOP,
                                    pivot_lows, swing_stop)


class PartialLedger(Ledger):
    """Ledger that can sell half a position; the half's net proceeds are
    folded into the position's single trade row when it finally closes."""

    def sell_half(self, entity, price, adv):
        qty = self.shares[entity] / 2
        proceeds = qty * price
        cost = proceeds * self.cost.per_side(proceeds, adv)
        self.cash += proceeds - cost
        self.shares[entity] -= qty
        m = self.meta[entity]
        m["half_proceeds"] = m.get("half_proceeds", 0.0) + proceeds
        m["half_net"] = m.get("half_net", 0.0) + proceeds - cost

    def sell(self, day, entity, price, adv, reason):
        m = self.meta[entity]
        hp, hn = m.get("half_proceeds", 0.0), m.get("half_net", 0.0)
        partial = "half_proceeds" in m
        super().sell(day, entity, price, adv, reason)
        if partial:
            row = self.trades[-1]
            row["proceeds"] += hp
            row["pnl"] += hn
            row["exit_reason"] = "HALF+" + reason


def _result_partial(ledger: PartialLedger):
    eq = pd.DataFrame(ledger.equity, columns=["Date", "equity", "gross_exposure"]).set_index("Date")
    end = eq.index[-1] if len(eq) else None
    open_rows = [{"entity_id": e, "entry_date": m["entry_date"], "exit_date": end, "cost_basis": m["cost_basis"],
                  "proceeds": ledger.shares[e] * m["last_mark"] + m.get("half_proceeds", 0.0),
                  "pnl": ledger.shares[e] * m["last_mark"] + m.get("half_net", 0.0) - m["cost_basis"] - m["costs"],
                  "exit_reason": "OPEN_AT_END"}
                 for e, m in ledger.meta.items() if e in ledger.shares]
    return eq, pd.DataFrame(ledger.trades + open_rows)


def run_variant(panel: Panel, start, end, order_fn, *, stop_mode: str, r_multiple: float | None = None,
                target_pct: float | None = None, partial: bool = False, cost: CostModel | None = None):
    assert stop_mode in ("swing", "candle")
    ledger = PartialLedger(cost or CostModel())
    sessions = panel.sessions
    piv = pivot_lows(panel) if stop_mode == "swing" else None
    pc = panel.close.shift(1)
    tr = np.maximum(panel.high - panel.low, np.maximum((panel.high - pc).abs(), (panel.low - pc).abs()))
    atr = tr.rolling(ATR_LEN, min_periods=ATR_LEN).mean()
    live, queued_exits = [], set()
    skipped = {"no_stop_level": 0, "gap_below_stop": 0, "stop_too_wide": 0}
    halves = 0
    for i, day in enumerate(sessions):
        if day < start or day > end:
            continue
        _delisting_exits(panel, ledger, i, day)
        opens, highs, lows, closes = panel.open.iloc[i], panel.high.iloc[i], panel.low.iloc[i], panel.close.iloc[i]
        atr_i = atr.iloc[i]
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
                pending = stop_mode == "candle" and od["type"] == "stop"
                if pending:      # breakout candle is today's; size off the previous candle
                    a = atr.iloc[i - 1].get(e, np.nan)
                    sizing_stop = panel.low[e].iloc[i - 1] - BUFFER_ATR * a if np.isfinite(a) else np.nan
                else:
                    sizing_stop = od["stop"]
                if not np.isfinite(sizing_stop):
                    skipped["no_stop_level"] += 1
                    continue
                if fill <= sizing_stop:
                    skipped["gap_below_stop"] += 1
                    continue
                dist = (fill - sizing_stop) / fill
                if dist > MAX_STOP_DIST:
                    skipped["stop_too_wide"] += 1
                    continue
                equity_now = ledger.cash + sum(ledger.value(x, opens) for x in ledger.shares)
                value = min(RISK * equity_now / dist, POS_CAP * equity_now, ledger.cash * 0.999)
                if value > 0:
                    target = fill * (1 + target_pct) if target_pct is not None else fill + r_multiple * (fill - sizing_stop)
                    half = fill + (target - fill) / 2 if partial else None
                    ledger.buy(day, e, fill, value, _adv(panel, i, e),
                               {"stop": sizing_stop, "target": target, "half": half, "entry_idx": i,
                                "fill": fill, "stop_pending": pending, "be_from": None})
                continue
            if od["type"] == "stop" and i < od["expires_idx"] and not (
                    od.get("cancel_below") is not None and np.isfinite(lo) and lo <= od["cancel_below"]):
                still_live.append(od)
        live = still_live
        # exits: stop first (stop wins ties), then half, then full target
        for e in list(ledger.shares):
            m = ledger.meta[e]
            o, hi, lo = opens.get(e, np.nan), highs.get(e, np.nan), lows.get(e, np.nan)
            adv = _adv(panel, i, e)
            gap_ok = m["entry_idx"] < i and np.isfinite(o)
            if m["be_from"] is not None and i >= m["be_from"]:
                m["stop"] = max(m["stop"], m["fill"])
            if not m["stop_pending"] and np.isfinite(lo) and lo <= m["stop"]:
                ledger.sell(day, e, o if gap_ok and o < m["stop"] else m["stop"], adv,
                            "BREAKEVEN" if m["be_from"] is not None and m["stop"] >= m["fill"] else "STOP")
                continue
            if m["half"] is not None and m["be_from"] is None and np.isfinite(hi) and hi >= m["half"]:
                ledger.sell_half(e, o if gap_ok and o > m["half"] else m["half"], adv)
                m["be_from"] = i + 1
                halves += 1
            if np.isfinite(hi) and hi >= m["target"]:
                ledger.sell(day, e, o if gap_ok and o > m["target"] else m["target"], adv, "TARGET")
                continue
            if m["stop_pending"]:
                a = atr_i.get(e, np.nan)
                m["stop"] = lo - BUFFER_ATR * a if np.isfinite(a) and np.isfinite(lo) else m["stop"]
                m["stop_pending"] = False
        ledger.mark(day, closes)
        if day >= end:
            continue
        for e in ledger.shares:
            if i - ledger.meta[e]["entry_idx"] + 1 >= TIME_STOP:
                queued_exits.add(e)
        pend = {od["entity"] for od in live}
        for od in order_fn(i, day, set(ledger.shares) | pend):
            if od[0] == "market":
                _, e, ref, gap, pr = od
                rec = {"type": "market", "entity": e, "ref": ref, "max_gap": gap, "priority": pr}
            else:
                _, e, trig, gap, pr, valid, cancel = od
                rec = {"type": "stop", "entity": e, "ref": trig, "max_gap": gap, "priority": pr,
                       "expires_idx": i + valid, "cancel_below": cancel}
            if stop_mode == "swing":
                stop = swing_stop(panel, piv, atr, i, e, min(rec["ref"], closes.get(e, np.nan)))
            elif rec["type"] == "market":           # B: the signal day is the breakout candle
                a = atr_i.get(e, np.nan)
                stop = lows.get(e, np.nan) - BUFFER_ATR * a if np.isfinite(a) else None
            else:
                stop = np.nan                         # set from the fill day's candle
            if stop is None or (rec["type"] == "market" and not np.isfinite(stop)):
                skipped["no_stop_level"] += 1
                continue
            rec["stop"] = stop
            live.append(rec)
    equity, trades = _result_partial(ledger)
    return equity, trades, skipped, halves
