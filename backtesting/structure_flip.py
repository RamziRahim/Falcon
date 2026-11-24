"""
Weekly / monthly structure flip (docs/structure_flip_preregistration.md).

find_signals(panel, tf) -> list of setups per the frozen rules, each known at the close of the
bar on which its higher low (HL) is confirmed:
  {entity, sig_idx, cancel_idx, hl, hh, fall}
  sig_idx    session index of that bar's last session (entries from sig_idx + 1)
  cancel_idx last session index on which an entry is still allowed
swing_lows(panel, tf) -> {entity: [(confirm_session_idx, low), ...]} for the structure exit.
run_flip(panel, start, end, tf, entry, exit_rule, signals, lows) -> (equity, trades)
"""
import numpy as np
import pandas as pd

from backtesting.pit_strategies import CostModel, Ledger, _adv, _delisting_exits, _result

K = {"W": 2, "M": 1}
EXPIRY = {"W": 13, "M": 6}
SLOTS, STOP_BUF = 20, 0.01


def _bars(panel, tf):
    s = panel.sessions
    per = s.to_period("W-SUN" if tf == "W" else "M")
    h = panel.high.groupby(per).max()
    l = panel.low.groupby(per).min()
    c = panel.close.groupby(per).last()
    pos = pd.Series(np.arange(len(s)), index=s).groupby(per).max()       # last session index of each bar
    return h, l, c, pos.reindex(h.index).to_numpy()


def _swings(x, k, high):
    n, out = len(x), []
    for j in range(k, n - k):
        nb = np.r_[x[j - k:j], x[j + 1:j + 1 + k]]
        if (high and (x[j] > nb).all()) or (not high and (x[j] < nb).all()):
            out.append(j)
    return out


def _per_entity(panel, tf):
    h, l, c, end = _bars(panel, tf)
    H, L, C = h.to_numpy(float), l.to_numpy(float), c.to_numpy(float)
    for j, e in enumerate(h.columns):
        ok = np.isfinite(H[:, j]) & np.isfinite(L[:, j]) & np.isfinite(C[:, j])
        idx = np.flatnonzero(ok)
        if len(idx) < 8:
            continue
        yield e, H[idx, j], L[idx, j], C[idx, j], end[idx]


def swing_lows(panel, tf):
    k, out = K[tf], {}
    for e, hh, ll, cc, end in _per_entity(panel, tf):
        out[e] = [(int(end[j + k]), float(ll[j])) for j in _swings(ll, k, False)]
    return out


def find_signals(panel, tf):
    k, exp, sigs = K[tf], EXPIRY[tf], []
    for e, hh, ll, cc, end in _per_entity(panel, tf):
        n = len(cc)
        sh = {j + k: j for j in _swings(hh, k, True)}        # confirmation bar -> swing bar
        sl = {j + k: j for j in _swings(ll, k, False)}
        highs, lows = [], []                                 # confirmed swing bars, in order
        state, brk = None, None
        for b in range(n):
            if state == "broken":
                if cc[b] < brk["L2"]:
                    state = None
            if b in sh:
                highs.append(sh[b])
            if b in sl:
                j = sl[b]
                lows.append(j)
                if state == "broken" and j >= brk["bar"]:
                    if ll[j] > brk["L2"]:
                        hl = float(ll[j])
                        hhv = float(hh[brk["bar"]:b + 1].max())
                        cancel = None
                        for q in range(b + 1, min(n, b + 1 + exp)):
                            if cc[q] < hl:
                                cancel = int(end[q])
                                break
                        if cancel is None:
                            cancel = int(end[min(n - 1, b + exp)])
                        sigs.append({"entity": e, "sig_idx": int(end[b]), "cancel_idx": cancel, "hl": hl, "hh": hhv,
                                     "fall": brk["fall"]})
                    state = None
            if state is None and len(highs) >= 2 and len(lows) >= 2:
                h1, h2 = hh[highs[-2]], hh[highs[-1]]
                l1, l2 = ll[lows[-2]], ll[lows[-1]]
                if h1 > h2 and l1 > l2 and cc[b] > h2:
                    lowest = float(ll[highs[-2]:b + 1].min())
                    state, brk = "broken", {"bar": b, "L2": float(l2), "fall": float((h1 - lowest) / h1)}
    return sigs


def run_flip(panel, start, end, tf, entry, exit_rule, signals, lows, cost=None, stats=None):
    assert entry in ("a", "b") and exit_rule in ("STR", "R2", "R3")
    ledger = Ledger(cost or CostModel())
    sessions = panel.sessions
    st = stats if stats is not None else {}
    by_day = {}
    for s_ in signals:
        by_day.setdefault(s_["sig_idx"] + 1, []).append(s_)
    pending = []                                   # (b) buy-stops alive
    rmult = {"R2": 2.0, "R3": 3.0}.get(exit_rule)
    for i, day in enumerate(sessions):
        if day < start or day > end:
            continue
        _delisting_exits(panel, ledger, i, day)
        opens, highs, lows_, closes = (panel.open.iloc[i], panel.high.iloc[i], panel.low.iloc[i], panel.close.iloc[i])
        if exit_rule == "STR":                     # raise stops on higher swing lows confirmed before today
            for e in ledger.shares:
                m = ledger.meta[e]
                for ci, lv in lows.get(e, ()):
                    if m["sig_idx"] < ci < i and lv * (1 - STOP_BUF) > m["stop"]:
                        m["stop"] = lv * (1 - STOP_BUF)
        new = []
        uni_ok = lambda s_: s_["entity"] in panel.universe_on(sessions[s_["sig_idx"]])
        for s_ in by_day.get(i, []):
            if not uni_ok(s_):
                continue
            st["signals"] = st.get("signals", 0) + 1
            if entry == "a":
                o = opens.get(s_["entity"], np.nan)
                if np.isfinite(o) and o > s_["hl"] * (1 - STOP_BUF):
                    new.append((s_, float(o)))
            else:
                pending.append(s_)
        if entry == "b":
            keep = []
            for s_ in pending:
                if i > s_["cancel_idx"] or s_["entity"] in ledger.shares:
                    continue
                hi, o = highs.get(s_["entity"], np.nan), opens.get(s_["entity"], np.nan)
                if np.isfinite(hi) and np.isfinite(o) and hi > s_["hh"]:
                    new.append((s_, float(max(o, s_["hh"]))))
                else:
                    keep.append(s_)
            pending = keep
        new.sort(key=lambda t: (-t[0]["fall"], str(t[0]["entity"])))
        for s_, px in new:
            e = s_["entity"]
            if e in ledger.shares:
                continue
            if len(ledger.shares) >= SLOTS:
                st["slot_full_skips"] = st.get("slot_full_skips", 0) + 1
                continue
            eq_now = ledger.cash + sum(ledger.value(x, opens) for x in ledger.shares)
            stop = s_["hl"] * (1 - STOP_BUF)
            if px <= stop:
                continue
            extra = {"stop": stop, "entry_idx": i, "sig_idx": s_["sig_idx"],
                     "target": px + rmult * (px - stop) if rmult else None}
            if ledger.buy(day, e, px, min(eq_now / SLOTS, ledger.cash * 0.995), _adv(panel, i, e), extra):
                st["entries"] = st.get("entries", 0) + 1
                st["risk_sum"] = st.get("risk_sum", 0.0) + (px - stop) / px
        for e in list(ledger.shares):
            m = ledger.meta[e]
            lo, o = lows_.get(e, np.nan), opens.get(e, np.nan)
            if np.isfinite(lo) and lo <= m["stop"]:
                gap = m["entry_idx"] < i and np.isfinite(o) and o < m["stop"]
                ledger.sell(day, e, o if gap else m["stop"], _adv(panel, i, e), "STOP")
                continue
            if m.get("target") is not None:
                hi = highs.get(e, np.nan)
                if np.isfinite(hi) and hi >= m["target"]:
                    gap = m["entry_idx"] < i and np.isfinite(o) and o > m["target"]
                    ledger.sell(day, e, o if gap else m["target"], _adv(panel, i, e), "TARGET")
        ledger.mark(day, closes)
    return _result(ledger)
