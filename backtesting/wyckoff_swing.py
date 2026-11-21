"""
===============================================================================
Falcon AI Swing Trading Platform — Wyckoff swing strategy (Mentfx three-box method)
===============================================================================
docs/wyckoff_swing_preregistration.md (FROZEN 2026-11-21).
  swing_machine   : rules 1-4 (pullback-rule swing points, breaks of structure, mode)
  stock_candidates: rules 5-15, 17-18 for one stock: entries for WY (double-MB
                    confirmation), BASE_TAP and BASE_BOS, tagged with the BOS count
  run_wyckoff     : rules 16, 19-21 and section 7 (filters, exits, sizing, portfolio)
===============================================================================
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.mtm_portfolio import CostModel
from backtesting.pit_strategies import Ledger, Panel, _adv, _delisting_exits, _result

TAP_EXPIRY, MAX_STOP, TIME_STOP, POS_CAP = 60, 0.15, 120, 0.25
STOP_BUF, T1_R, T1_SHARE, GAP_R = 0.25, 2.5, 0.80, 0.5


def wilder_atr(h, l, c):
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.vstack([h - l, np.abs(h - pc), np.abs(l - pc)]), axis=0)
    return pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()


def swing_machine(h, l, c):
    """Rules 1-4. Returns (events, mode, sl_val, sl_conf):
    events : list of dicts {t, kind: 'up'|'down', broken, broken_idx, prot, prot_idx}
    mode   : +1 up / -1 down after each bar's close
    sl_val, sl_conf : latest confirmed swing low and the bar it was confirmed on, after each bar."""
    n = len(c)
    mode = np.zeros(n, dtype=np.int8)
    sl_val = np.full(n, np.nan)
    sl_conf = np.full(n, -1, dtype=np.int64)
    events = []
    if n < 3:
        return events, mode, sl_val, sl_conf
    m = 1
    last_sl, last_sl_i, last_sl_c = l[0], 0, 0
    last_sh, last_sh_i = h[0], 0
    ext_hi, ext_hi_i = h[0], 0          # up mode: highest high since the last swing low
    ext_lo, ext_lo_i = l[0], 0          # down mode: lowest low since the last swing high
    in_pb, sh, sh_i, pb_lo, pb_lo_i = False, np.nan, -1, np.nan, -1
    in_ra, sld, sld_i, ra_hi, ra_hi_i = False, np.nan, -1, np.nan, -1
    for t in range(1, n):
        if m == 1:
            if c[t] < last_sl:                                    # rule 3: break of structure down
                events.append({"t": t, "kind": "down"})
                m = -1
                seg = l[last_sh_i:t + 1]
                ext_lo_i = last_sh_i + int(np.argmin(seg))
                ext_lo = l[ext_lo_i]
                in_ra = False
            elif not in_pb:
                if h[t] > ext_hi:
                    ext_hi, ext_hi_i = h[t], t
                if l[t] < l[t - 1]:                               # pullback starts: swing high
                    in_pb, sh, sh_i, pb_lo, pb_lo_i = True, ext_hi, ext_hi_i, l[t], t
                    last_sh, last_sh_i = sh, sh_i
            else:
                if l[t] < pb_lo:
                    pb_lo, pb_lo_i = l[t], t
                if c[t] > sh:                                     # rule 1: continuation break up
                    events.append({"t": t, "kind": "up", "broken": sh, "broken_idx": sh_i,
                                   "prot": pb_lo, "prot_idx": pb_lo_i})
                    last_sl, last_sl_i, last_sl_c = pb_lo, pb_lo_i, t
                    in_pb = False
                    seg = h[pb_lo_i:t + 1]
                    ext_hi_i = pb_lo_i + int(np.argmax(seg))
                    ext_hi = h[ext_hi_i]
        else:
            if c[t] > last_sh:                                    # rule 3: break of structure up (reversal)
                seg = l[last_sh_i:t + 1]
                pi = last_sh_i + int(np.argmin(seg))
                events.append({"t": t, "kind": "up", "broken": last_sh, "broken_idx": last_sh_i,
                               "prot": l[pi], "prot_idx": pi})
                m = 1
                last_sl, last_sl_i, last_sl_c = l[pi], pi, t
                seg = h[pi:t + 1]
                ext_hi_i = pi + int(np.argmax(seg))
                ext_hi = h[ext_hi_i]
                in_pb = False
            elif not in_ra:
                if l[t] < ext_lo:
                    ext_lo, ext_lo_i = l[t], t
                if h[t] > h[t - 1]:                               # rally starts: swing low
                    in_ra, sld, sld_i, ra_hi, ra_hi_i = True, ext_lo, ext_lo_i, h[t], t
                    last_sl, last_sl_i, last_sl_c = sld, sld_i, t
            else:
                if h[t] > ra_hi:
                    ra_hi, ra_hi_i = h[t], t
                if c[t] < sld:                                    # rule 2: continuation break down
                    events.append({"t": t, "kind": "down"})
                    last_sh, last_sh_i = ra_hi, ra_hi_i
                    in_ra = False
                    seg = l[ra_hi_i:t + 1]
                    ext_lo_i = ra_hi_i + int(np.argmin(seg))
                    ext_lo = l[ext_lo_i]
        mode[t] = m
        sl_val[t] = last_sl
        sl_conf[t] = last_sl_c
    return events, mode, sl_val, sl_conf


def _h1(h, b, L1i):
    k = None
    for j in range(L1i - 1, b, -1):
        if h[j] > h[j - 1]:
            k = j
            break
    a = k if k is not None else b
    if a > L1i - 1:
        return None
    return float(np.max(h[a:L1i]))


def stock_candidates(o, h, l, c, events, atr):
    """Rules 5-15, 17-18. One record per (break of structure up, entry kind)."""
    out = []
    n = len(c)
    count = 0
    ups = []
    for ev in events:
        if ev["kind"] == "down":
            count = 0
            continue
        count += 1
        ev = dict(ev, count=count)
        ups.append(ev)
    ends = {}
    all_t = [e["t"] for e in events]
    for ev in ups:
        nxt = [t for t in all_t if t > ev["t"]]
        ends[ev["t"]] = nxt[0] if nxt else n - 1
    for ev in ups:
        b, prot, prot_i, bi = ev["t"], ev["prot"], ev["prot_idx"], ev["broken_idx"]
        end = ends[b]
        # rule 8: demand zone
        z = None
        for j in range(prot_i, bi, -1):
            if c[j] < o[j]:
                z = j
                break
        if z is None:
            z = prot_i
        ztop = h[z]
        zbot = min(l[z], l[z + 1]) if z + 1 < n else l[z]
        base = {"bos_t": b, "count": ev["count"]}
        # BASE_BOS: close of the break bar
        if b >= 1 and np.isfinite(atr[b - 1]):
            fill = c[b]
            stop = prot - STOP_BUF * atr[b - 1]
            if stop < fill and (fill - stop) / fill <= MAX_STOP:
                out.append(dict(base, kind="BOS", t=b, fill=float(fill), stop=float(stop),
                                t1=float(max(h[b], fill + T1_R * (fill - stop))), at_close=True))
        # walk forward from the break
        state, tap = "WAIT", None
        L1 = L1i = H1 = H2 = L2 = vi = None
        h2run = None
        for t in range(b + 1, min(end, n - 1) + 1):
            if state == "WAIT":
                if t - b > TAP_EXPIRY:
                    break
                if l[t] <= ztop:
                    tap = t
                    if np.isfinite(atr[t - 1]):                   # BASE_TAP
                        fill = min(ztop, o[t])
                        stop = min(zbot, prot) - STOP_BUF * atr[t - 1]
                        if stop < fill and (fill - stop) / fill <= MAX_STOP:
                            hi = float(np.max(h[b:t + 1]))
                            out.append(dict(base, kind="TAP", t=t, fill=float(fill), stop=float(stop),
                                            t1=float(max(hi, fill + T1_R * (fill - stop))), at_close=False))
                    state, L1, L1i = "TAPPED", l[t], t
                    H1 = _h1(h, b, L1i)
                    if c[t] < prot:
                        break
                    continue
                if c[t] < prot:
                    break
                continue
            if state == "ARMED":
                if h[t] >= H2:                                    # rule 15: buy-stop fills
                    stop = L2 - STOP_BUF * atr[t - 1]
                    fill = max(H2, o[t])
                    if o[t] > H2 + GAP_R * (H2 - stop):
                        break
                    if stop < fill and (fill - stop) / fill <= MAX_STOP and np.isfinite(atr[t - 1]):
                        hi = float(np.max(h[b:tap + 1]))
                        out.append(dict(base, kind="WY", t=t, fill=float(fill), stop=float(stop),
                                        t1=float(max(hi, fill + T1_R * (fill - stop))), at_close=False))
                    break
                if l[t] < L1:                                     # rule 14: back to MB1
                    state, L1, L1i = "TAPPED", l[t], t
                    H1 = _h1(h, b, L1i)
                elif l[t] < L2:
                    L2 = l[t]
            elif state == "TAPPED":
                if l[t] < L1:
                    L1, L1i = l[t], t
                    H1 = _h1(h, b, L1i)
                elif H1 is not None and t > L1i and h[t] > H1:    # rule 12: validation
                    state, vi, h2run = "VALID", t, h[t]
            elif state == "VALID":
                if l[t] < L1:
                    state, L1, L1i = "TAPPED", l[t], t
                    H1 = _h1(h, b, L1i)
                elif t > vi and l[t] < l[t - 1]:                  # rule 13: MB2 pullback
                    h2run = max(h2run, h[t])
                    state, H2, L2 = "ARMED", h2run, l[t]
                else:
                    h2run = max(h2run, h[t])
            if c[t] < prot:                                       # rule 7
                break
    return out


def weekly_mode(panel: Panel):
    """Rules 1-3 on weekly bars; returns a (sessions x stocks) array: the mode of the last week
    completed before each session (0 where unknown)."""
    s = panel.sessions
    W = {k: getattr(panel, k).resample("W-FRI") for k in ("open", "high", "low", "close")}
    wo, wh, wl, wc = W["open"].first(), W["high"].max(), W["low"].min(), W["close"].last()
    labels = wc.index
    pos = np.searchsorted(labels.values, s.values, side="left") - 1
    out = np.zeros((len(s), wc.shape[1]), dtype=np.int8)
    for j in range(wc.shape[1]):
        hh, ll, cc = wh.iloc[:, j].to_numpy(float), wl.iloc[:, j].to_numpy(float), wc.iloc[:, j].to_numpy(float)
        ok = np.flatnonzero(np.isfinite(hh) & np.isfinite(ll) & np.isfinite(cc))
        if len(ok) < 20:
            continue
        _, m, _, _ = swing_machine(hh[ok], ll[ok], cc[ok])
        full = np.zeros(len(labels), dtype=np.int8)
        full[ok] = m
        full = pd.Series(full).replace(0, np.nan).ffill().fillna(0).to_numpy(np.int8)
        valid = pos >= 0
        out[valid, j] = full[pos[valid]]
    return out


def panel_candidates(panel: Panel):
    """Candidates for every stock, plus per-stock swing-low arrays and ATR for the exits."""
    O, H, L, C = (x.to_numpy(float) for x in (panel.open, panel.high, panel.low, panel.close))
    T, N = C.shape
    SLV = np.full((T, N), np.nan)
    SLC = np.full((T, N), -1, dtype=np.int64)
    ATR = np.full((T, N), np.nan)
    rows = []
    for j, e in enumerate(panel.close.columns):
        v = np.flatnonzero(np.isfinite(O[:, j]) & np.isfinite(H[:, j]) & np.isfinite(L[:, j]) & np.isfinite(C[:, j]))
        if len(v) < 260:
            continue
        o, h, l, c = O[v, j], H[v, j], L[v, j], C[v, j]
        atr = wilder_atr(h, l, c)
        ev, _, slv, slc = swing_machine(h, l, c)
        ATR[v, j] = atr
        SLV[v, j] = slv
        SLC[v, j] = np.where(slc >= 0, v[np.clip(slc, 0, len(v) - 1)], -1)
        for x in stock_candidates(o, h, l, c, ev, atr):
            x["t"] = int(v[x["t"]])
            x["bos_t"] = int(v[x["bos_t"]])
            x["entity_id"] = e
            rows.append(x)
    return pd.DataFrame(rows), SLV, SLC, ATR


def run_wyckoff(panel: Panel, cand: pd.DataFrame, start, end, nifty_up, week_mode, SLV, SLC, ATR, members_on,
                sizing: str = "SD", risk: float = 0.005, open_cap: float | None = None, slots: int = 10,
                sector_on=None, cost: CostModel | None = None):
    """Rules 16, 19-21 and section 7. nifty_up: bool array (Nifty swing machine in up mode after
    each session's close). members_on(i) -> set of tradable entities on session i.
    sector_on(i) -> {entity: sector} (SD only)."""
    ledger = Ledger(cost or CostModel())
    s = panel.sessions
    O, H, L, C = (x.to_numpy(float) for x in (panel.open, panel.high, panel.low, panel.close))
    cols = {e: j for j, e in enumerate(panel.close.columns)}
    cap = open_cap if open_cap is not None else 8 * risk
    by_t = {t: g for t, g in cand.groupby("t")}
    queued = set()
    st = {"candidates": 0, "filtered_universe": 0, "filtered_nifty": 0, "filtered_weekly": 0, "held": 0,
          "no_room": 0, "sector_cap": 0, "filled": 0, "t1_hits": 0, "hold_days": []}

    def equity_now(i):
        closes = panel.close.iloc[i]
        return ledger.cash + sum(ledger.value(x, closes) for x in ledger.shares)

    def open_risk(i):
        r = 0.0
        for e in ledger.shares:
            j = cols[e]
            px = C[i - 1, j] if np.isfinite(C[i - 1, j]) else ledger.meta[e]["fill"]
            r += ledger.shares[e] * max(0.0, px - ledger.meta[e]["stop"])
        return r

    def try_buy(i, day, r):
        e = r.entity_id
        st["candidates"] += 1
        known = i if r.at_close else i - 1                       # state known before the fill
        if e in ledger.shares:
            st["held"] += 1
            return
        if e not in members_on(i):
            st["filtered_universe"] += 1
            return
        if not bool(nifty_up[known]):
            st["filtered_nifty"] += 1
            return
        if week_mode[i, cols[e]] == -1:
            st["filtered_weekly"] += 1
            return
        eqv = equity_now(i)
        dist = (r.fill - r.stop) / r.fill
        if sizing == "SF":
            if len(ledger.shares) >= slots:
                st["no_room"] += 1
                return
        else:
            if open_risk(i) + risk * eqv > cap * eqv + 1e-9:
                st["no_room"] += 1
                return
            secmap = sector_on(i) if sector_on else {}
            sec = secmap.get(e)
            if sec is not None and sum(1 for x in ledger.shares if secmap.get(x) == sec) >= 2:
                st["sector_cap"] += 1
                return
        value = min(risk * eqv / dist, POS_CAP * eqv, ledger.cash * 0.999)
        if value > 0 and ledger.buy(day, e, r.fill, value, _adv(panel, i, e),
                                    {"stop": r.stop, "t1": r.t1, "fill": r.fill, "entry_idx": i, "phase": "full",
                                     "at_close": bool(r.at_close)}):
            st["filled"] += 1
            if not r.at_close and L[i, cols[e]] <= r.stop:        # rule 21: the stop on the fill day
                ledger.sell(day, e, r.stop, _adv(panel, i, e), "STOP")
                st["hold_days"].append(0)

    for i, day in enumerate(s):
        if day < start or day > end:
            continue
        _delisting_exits(panel, ledger, i, day)
        for e in sorted(queued):
            if e not in ledger.shares:
                queued.discard(e)
            elif np.isfinite(O[i, cols[e]]):
                st["hold_days"].append(i - ledger.meta[e]["entry_idx"])
                ledger.sell(day, e, O[i, cols[e]], _adv(panel, i, e), "TIME_STOP")
                queued.discard(e)
        for e in sorted(ledger.shares):                            # exits on positions held before today
            m, j = ledger.meta[e], cols[e]
            if m["entry_idx"] >= i:
                continue
            o, h, l = O[i, j], H[i, j], L[i, j]
            if np.isfinite(l) and l <= m["stop"]:
                px = o if np.isfinite(o) and o < m["stop"] else m["stop"]
                st["hold_days"].append(i - m["entry_idx"])
                ledger.sell(day, e, px, _adv(panel, i, e), "STOP" if m["phase"] == "full" else "TRAIL")
            elif m["phase"] == "full" and np.isfinite(h) and h >= m["t1"]:
                px = o if np.isfinite(o) and o > m["t1"] else m["t1"]
                ledger.trim(e, px, ledger.shares[e] * px * T1_SHARE, _adv(panel, i, e))
                m["phase"] = "runner"
                st["t1_hits"] += 1
        g = by_t.get(i)
        if g is not None and day < end:
            g = g.sort_values(["at_close", "mom_rank", "entity_id"], ascending=[True, False, True])
            for r in g.itertuples():
                try_buy(i, day, r)
        ledger.mark(day, panel.close.iloc[i])
        for e in ledger.shares:                                    # end-of-day stop updates (rules 19-20)
            m, j = ledger.meta[e], cols[e]
            if SLC[i, j] > m["entry_idx"] and np.isfinite(SLV[i, j]) and SLV[i, j] > m["fill"]:
                m["stop"] = max(m["stop"], m["fill"])
            if m["phase"] == "runner" and np.isfinite(SLV[i, j]) and np.isfinite(ATR[i, j]):
                m["stop"] = max(m["stop"], SLV[i, j] - STOP_BUF * ATR[i, j])
            if day < end and i - m["entry_idx"] + 1 >= TIME_STOP:
                queued.add(e)
    eq, trades = _result(ledger)
    hd = st.pop("hold_days")
    st["avg_hold_days"] = round(float(np.mean(hd)), 1) if hd else None
    return eq, trades, st
