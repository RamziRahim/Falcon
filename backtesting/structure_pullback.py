"""
===============================================================================
Falcon AI Swing Trading Platform — swing-structure retest and higher-low pullback
===============================================================================
docs/structure_pullback_preregistration.md.
  zigzag_confirmed : the v3 ATR zigzag (engine.detect_atr_zigzag, 2.2 ATR) run over a
                     stock's whole history, with the session each swing was confirmed
  stock_signals    : trend-change retest (TCR, rules 3-6) and higher-low pullback (HLP,
                     rules 7-10) entries at the close, with the rule 11 trend flag and
                     the rule 13 risk window applied
  run_signals      : rules 12-15 (Nifty filter, 1:3, 40 sessions, 1% risk, 10 slots)
===============================================================================
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.mtm_portfolio import CostModel
from backtesting.pit_strategies import Ledger, Panel, _adv, _delisting_exits, _result

ZZ_MULT, RETEST_WIN, HLP_WIN, PL_RECENT = 2.2, 15, 30, 4
RISK, POS_CAP, SLOTS, TIME_STOP, MIN_RISK, MAX_RISK = 0.01, 0.25, 10, 40, 0.015, 0.10


def wilder_atr(h, l, c):
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.vstack([h - l, np.abs(h - pc), np.abs(l - pc)]), axis=0)
    return pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()


def zigzag_confirmed(h, l, atr, mult=ZZ_MULT):
    """Same algorithm and start as engine.detect_atr_zigzag; returns confirmed swings only, as
    (idx, price, kind, confirm_idx), kind +1 = high, -1 = low."""
    n = len(h)
    start = 50
    if n < start + 11:
        return []
    ih = start + int(np.argmax(h[start:start + 10]))
    il = start + int(np.argmin(l[start:start + 10]))
    if il < ih:
        d, ei, ep = 1, ih, h[ih]
    else:
        d, ei, ep = -1, il, l[il]
    out = []
    for i in range(max(ih, il) + 1, n):
        a = atr[i]
        if np.isnan(a) or a <= 0:
            continue
        if d == 1:
            if h[i] >= ep:
                ep, ei = h[i], i
            if l[i] <= ep - mult * a:
                out.append((ei, float(ep), 1, i))
                d, ei, ep = -1, i, l[i]
        else:
            if l[i] <= ep:
                ep, ei = l[i], i
            if h[i] >= ep + mult * a:
                out.append((ei, float(ep), -1, i))
                d, ei, ep = 1, i, h[i]
    return out


def stock_signals(o, h, l, c):
    """Entries for one stock over its valid rows. Returns a list of dicts with row index r,
    setup, entry (= close), stop, trend_ok, plus counters {'tcr_breaks': n}."""
    n = len(c)
    atr = wilder_atr(h, l, c)
    sma200 = pd.Series(c).rolling(200).mean().to_numpy()
    piv = zigzag_confirmed(h, l, atr)
    sig, breaks = [], 0
    known, k = [], 0
    broken, hlp_done = set(), set()
    tcr = []                                            # open retest windows
    for r in range(1, n):
        while k < len(piv) and piv[k][3] <= r:
            known.append(piv[k])
            k += 1
        if not np.isfinite(c[r]):
            continue
        trend_ok = bool(np.isfinite(sma200[r]) and r >= 20 and np.isfinite(sma200[r - 20])
                        and c[r] > sma200[r] and sma200[r] > sma200[r - 20])
        fired = set()
        # --- TCR: retest windows already open (sessions b+1 .. b+15) ---
        keep = []
        for w in tcr:
            if r > w["b"] + RETEST_WIN:
                continue
            if c[r] < w["H2"] - 1.0 * atr[r] or l[r] < w["L2"]:
                continue                                 # rule 4: dropped
            if l[r] <= w["H2"] + 0.5 * atr[r]:
                w["touched"] = True
            if w["touched"] and c[r] > h[r - 1] and c[r] > w["H2"]:
                stop = float(np.nanmin(l[w["b"]:r + 1])) - 0.5 * atr[r]
                sig.append({"r": r, "setup": "TCR", "entry": float(c[r]), "stop": float(stop), "trend_ok": trend_ok,
                            "lag": r - w["b"]})
                fired.add("TCR")
                continue                                 # one entry per break
            keep.append(w)
        tcr = keep
        # --- TCR: the break (rule 3) ---
        if len(known) >= 4:
            (i1, H1, k1, _), (j1, L1, k2, _), (i2, H2, k3, _), (j2, L2, k4, _) = known[-4:]
            if (k1, k2, k3, k4) == (1, -1, 1, -1) and H2 < H1 and L2 < L1 and i2 not in broken and c[r] > H2:
                broken.add(i2)
                breaks += 1
                tcr.append({"b": r, "H2": H2, "L2": L2, "touched": False})
        # --- HLP (rules 7-10) ---
        if len(known) >= 4 and "TCR" not in fired:
            (ia, La, ka, _), (ja, Ha, kb, _), (ib, Lb, kc, _), (jb, Hb, kd, _) = known[-4:]
            if (ka, kb, kc, kd) == (-1, 1, -1, 1) and Lb > La and Hb > Ha and jb not in hlp_done and r - jb <= HLP_WIN:
                seg = l[jb:r + 1]
                pl_off = int(np.nanargmin(seg))
                PL = float(seg[pl_off])
                if (PL > Lb and (Hb - PL) / (Hb - Lb) >= 0.382 and r - (jb + pl_off) <= PL_RECENT
                        and c[r] > h[r - 1] and c[r] < Hb):
                    sig.append({"r": r, "setup": "HLP", "entry": float(c[r]), "stop": float(PL - 0.5 * atr[r]),
                                "trend_ok": trend_ok, "lag": r - jb})
                    hlp_done.add(jb)
    out = []
    for s_ in sig:                                       # rule 13: risk window
        risk = (s_["entry"] - s_["stop"]) / s_["entry"]
        if MIN_RISK <= risk <= MAX_RISK:
            s_["risk"] = risk
            out.append(s_)
    return out, {"tcr_breaks": breaks, "raw_tcr": sum(1 for x in sig if x["setup"] == "TCR"),
                 "raw_hlp": sum(1 for x in sig if x["setup"] == "HLP")}


def panel_signals(panel: Panel):
    """All signals for the panel's stocks, indexed to panel sessions."""
    O, H, L, C = (x.to_numpy(float) for x in (panel.open, panel.high, panel.low, panel.close))
    rows, breaks = [], []
    for j, e in enumerate(panel.close.columns):
        valid = np.flatnonzero(np.isfinite(C[:, j]) & np.isfinite(H[:, j]) & np.isfinite(L[:, j]) & np.isfinite(O[:, j]))
        if len(valid) < 260:
            continue
        sg, cnt = stock_signals(O[valid, j], H[valid, j], L[valid, j], C[valid, j])
        for x in sg:
            x["t"] = int(valid[x.pop("r")])
            x["entity_id"] = e
            rows.append(x)
        breaks.append(cnt["tcr_breaks"])
    df = pd.DataFrame(rows)
    return df, int(sum(breaks))


def run_signals(panel: Panel, signals: pd.DataFrame, start, end, nifty_ok, cost: CostModel | None = None):
    """Rules 12-15. signals: entity_id, t, setup, entry, stop, mom_rank (already filtered by rule 11
    where required)."""
    ledger = Ledger(cost or CostModel())
    s = panel.sessions
    O, H, L, C = (x.to_numpy(float) for x in (panel.open, panel.high, panel.low, panel.close))
    cols = {e: j for j, e in enumerate(panel.close.columns)}
    by_t = {t: g for t, g in signals.groupby("t")}
    queued = set()
    st = {"signals": 0, "not_in_universe": 0, "nifty_blocked": 0, "slots_full": 0, "filled": 0}
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
        for e in sorted(ledger.shares):
            m, j = ledger.meta[e], cols[e]
            o, h, l = O[i, j], H[i, j], L[i, j]
            if np.isfinite(l) and l <= m["stop"]:
                ledger.sell(day, e, o if np.isfinite(o) and o < m["stop"] else m["stop"], _adv(panel, i, e), "STOP")
            elif np.isfinite(h) and h >= m["target"]:
                ledger.sell(day, e, o if np.isfinite(o) and o > m["target"] else m["target"], _adv(panel, i, e), "TARGET")
        g = by_t.get(i)
        if g is not None and day < end:
            members = set(panel.universe_on(day))
            seen = set()
            for r in g.sort_values(["mom_rank", "entity_id"], ascending=[False, True]).itertuples():
                if r.entity_id in seen:
                    continue
                seen.add(r.entity_id)
                st["signals"] += 1
                if r.entity_id in ledger.shares:
                    continue
                if r.entity_id not in members:
                    st["not_in_universe"] += 1
                    continue
                if not bool(nifty_ok[i]):
                    st["nifty_blocked"] += 1
                    continue
                if len(ledger.shares) >= SLOTS:
                    st["slots_full"] += 1
                    continue
                dist = (r.entry - r.stop) / r.entry
                equity_now = ledger.cash + sum(ledger.value(x, closes) for x in ledger.shares)
                value = min(RISK * equity_now / dist, POS_CAP * equity_now, ledger.cash * 0.999)
                if value > 0 and ledger.buy(day, r.entity_id, r.entry, value, _adv(panel, i, r.entity_id),
                                            {"stop": r.stop, "target": r.entry + 3.0 * (r.entry - r.stop),
                                             "entry_idx": i, "setup": r.setup}):
                    st["filled"] += 1
        ledger.mark(day, closes)
        if day >= end:
            continue
        for e in ledger.shares:
            if i - ledger.meta[e]["entry_idx"] + 1 >= TIME_STOP:
                queued.add(e)
    eq, trades = _result(ledger)
    return eq, trades, st
