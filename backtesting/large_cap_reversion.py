"""
Falcon -- LMR, large-cap mean reversion (docs/pullback_two_ways_preregistration.md, Part 1).

Universe: the monthly top 100 by turnover in force on the signal day (the latest month-end list
on or before it, as panel.universe_on does). Signal at day t's close: close > 200-day SMA and
RSI(2) (Wilder) < 10. Buy at that close (fill="close") or at the next open (fill="open").
Exit at the first close above the 5-day SMA, or the close of the 10th session after entry
(fill="open": both sell at the next open). Optional stop_pct (filled at the stop, or the open
if it gaps through). Optional nifty_ok (bool array over sessions) blocks new entries.
10 slots, equity / 10 each, limited by cash; lowest RSI(2) first, ties by entity_id.
"""
import numpy as np
import pandas as pd

from backtesting.pit_strategies import CostModel, Ledger, _adv, _delisting_exits, _result

SLOTS, RSI_MAX, SMA_TREND, SMA_EXIT, TIME_STOP = 10, 10.0, 200, 5, 10


def rsi_wilder(close: pd.DataFrame, n: int = 2) -> pd.DataFrame:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = up / dn
    out = 100 - 100 / (1 + rs)
    return out.where(dn > 0, 100.0).where(up.notna())


def run_lmr(panel, top100: dict, start, end, cost=None, fill: str = "close", stop_pct=None, nifty_ok=None,
            stats: dict | None = None):
    assert fill in ("close", "open")
    st = stats if stats is not None else {}
    for k in ("signals", "entries", "slots_full", "exit_bounce", "exit_time", "exit_stop"):
        st.setdefault(k, 0)
    st.setdefault("hold_days", [])
    st.setdefault("invested_share", [])
    ledger = Ledger(cost or CostModel())
    C = panel.close
    rsi = rsi_wilder(C).to_numpy()
    sma200 = C.rolling(SMA_TREND, min_periods=SMA_TREND).mean().to_numpy()
    sma5 = C.rolling(SMA_EXIT, min_periods=SMA_EXIT).mean().to_numpy()
    Cn, On, Ln = C.to_numpy(), panel.open.to_numpy(), panel.low.to_numpy()
    cols = {e: j for j, e in enumerate(C.columns)}
    sessions = panel.sessions
    ends = sorted(top100)
    pend_buy, pend_sell = [], []                     # fill="open": decided at a close, executed at the next open
    for i, day in enumerate(sessions):
        if day < start or day > end:
            continue
        _delisting_exits(panel, ledger, i, day)
        opens = panel.open.iloc[i]
        # 1. next-open executions
        for e in pend_sell:
            if e in ledger.shares and np.isfinite(On[i, cols[e]]):
                ledger.sell(day, e, On[i, cols[e]], _adv(panel, i, e), ledger.meta[e]["why"])
        pend_sell = []
        if pend_buy:
            free = SLOTS - len(ledger.shares)
            todo = [e for e in pend_buy if e not in ledger.shares and np.isfinite(On[i, cols[e]])][:max(free, 0)]
            if todo:
                eq = ledger.cash + sum(ledger.value(x, opens) for x in ledger.shares)
                per = min(eq / SLOTS, ledger.cash / len(todo) * 0.999)
                for e in todo:
                    o = On[i, cols[e]]
                    if ledger.buy(day, e, o, per, _adv(panel, i, e),
                                  {"entry_idx": i, "stop": o * (1 - stop_pct) if stop_pct else None}):
                        st["entries"] += 1
            pend_buy = []
        # 2. stops (intraday)
        if stop_pct:
            for e in list(ledger.shares):
                m, j = ledger.meta[e], cols[e]
                s = m.get("stop")
                if s is not None and np.isfinite(Ln[i, j]) and Ln[i, j] <= s:
                    if fill == "close" and m["entry_idx"] == i:
                        continue                     # bought at today's close: no stop check today
                    px = On[i, j] if (np.isfinite(On[i, j]) and On[i, j] < s and m["entry_idx"] < i) else s
                    ledger.sell(day, e, px, _adv(panel, i, e), "STOP")
                    st["exit_stop"] += 1
                    st["hold_days"].append(i - m["entry_idx"])
        # 3. exits decided at today's close
        for e in list(ledger.shares):
            m, j = ledger.meta[e], cols[e]
            if (fill == "close" and m["entry_idx"] == i) or e in pend_sell:
                continue
            c = Cn[i, j]
            if not np.isfinite(c):
                continue
            why = "BOUNCE" if (np.isfinite(sma5[i, j]) and c > sma5[i, j]) else ("TIME" if i - m["entry_idx"] >= TIME_STOP else None)
            if why is None:
                continue
            st["exit_bounce" if why == "BOUNCE" else "exit_time"] += 1
            st["hold_days"].append(i - m["entry_idx"])
            if fill == "close":
                ledger.sell(day, e, c, _adv(panel, i, e), why)
            else:
                m["why"] = why
                pend_sell.append(e)
        # 4. entries from today's close
        if day < end and (nifty_ok is None or nifty_ok[i]):
            me = [m for m in ends if m <= day]
            members = top100[me[-1]] if me else set()
            cand = []
            for e in members:
                j = cols.get(e)
                if j is None or e in ledger.shares:
                    continue
                c, r, s2 = Cn[i, j], rsi[i, j], sma200[i, j]
                if np.isfinite(c) and np.isfinite(r) and np.isfinite(s2) and c > s2 and r < RSI_MAX:
                    cand.append((r, e))
            cand.sort()
            st["signals"] += len(cand)
            if fill == "open":
                pend_buy = [e for _, e in cand]
            else:
                free = SLOTS - len(ledger.shares)
                todo = [e for _, e in cand][:max(free, 0)]
                st["slots_full"] += max(len(cand) - len(todo), 0)
                if todo:
                    closes = panel.close.iloc[i]
                    eq = ledger.cash + sum(ledger.value(x, closes) for x in ledger.shares)
                    per = min(eq / SLOTS, ledger.cash / len(todo) * 0.999)
                    for e in todo:
                        c = Cn[i, cols[e]]
                        if ledger.buy(day, e, c, per, _adv(panel, i, e),
                                      {"entry_idx": i, "stop": c * (1 - stop_pct) if stop_pct else None}):
                            st["entries"] += 1
        closes = panel.close.iloc[i]
        ledger.mark(day, closes)
        eq = ledger.cash + sum(ledger.value(x, closes) for x in ledger.shares)
        if eq > 0:
            st["invested_share"].append(1 - ledger.cash / eq)
    return _result(ledger)
