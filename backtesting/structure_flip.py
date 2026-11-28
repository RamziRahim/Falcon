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

K = {"W": 2, "M": 1, "D": 3}                 # "D": docs/daily_flip_weekly_trend_preregistration.md
EXPIRY = {"W": 13, "M": 6, "D": 65}
SLOTS, STOP_BUF = 20, 0.01


def _period(sessions, tf):
    return sessions.to_period("W-SUN" if tf == "W" else ("D" if tf == "D" else "M"))


def _bars(panel, tf):
    s = panel.sessions
    if tf == "D":                                  # every session is its own bar
        return panel.high, panel.low, panel.close, np.arange(len(s))
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


def find_signals(panel, tf, second=False, expiry=None, hl1_bars=26):
    """second=True (docs/weekly_flip_exits_preregistration.md): after HL1, wait for a close above HH1
    (highest high from the break to HL1's confirmation), then a swing low confirmed after that close
    and above HL1 (HL2); the setup's hl / hh are then HL2 / the highest high from the HH2 close to
    HL2's confirmation, cancelled on a close below HL2 or after EXPIRY bars."""
    k, exp, sigs = K[tf], (expiry if expiry is not None else EXPIRY[tf]), []
    for e, hh, ll, cc, end in _per_entity(panel, tf):
        n = len(cc)
        sh = {j + k: j for j in _swings(hh, k, True)}        # confirmation bar -> swing bar
        sl = {j + k: j for j in _swings(ll, k, False)}
        highs, lows = [], []                                 # confirmed swing bars, in order
        state, brk = None, None

        def emit(b, hl, hhv, fall):
            cancel = None
            for q in range(b + 1, min(n, b + 1 + exp)):
                if cc[q] < hl:
                    cancel = int(end[q])
                    break
            if cancel is None:
                cancel = int(end[min(n - 1, b + exp)])
            sigs.append({"entity": e, "sig_idx": int(end[b]), "cancel_idx": cancel, "hl": hl, "hh": hhv, "fall": fall})

        for b in range(n):
            if state == "broken" and cc[b] < brk["L2"]:
                state = None
            if state in ("hl1", "hh2") and cc[b] < brk["hl1"]:
                state = None
            if state == "hl1" and b - brk["hl1_bar"] > hl1_bars:
                state = None
            if b in sh:
                highs.append(sh[b])
            if b in sl:
                j = sl[b]
                lows.append(j)
                if state == "broken" and j >= brk["bar"]:
                    if ll[j] > brk["L2"]:
                        hl, hhv = float(ll[j]), float(hh[brk["bar"]:b + 1].max())
                        if not second:
                            emit(b, hl, hhv, brk["fall"])
                            state = None
                        else:
                            brk.update(hl1=hl, hh1=hhv, hl1_bar=b)
                            state = "hl1"
                    else:
                        state = None
                elif state == "hh2" and j >= brk["hh2_bar"]:
                    if ll[j] > brk["hl1"]:
                        emit(b, float(ll[j]), float(hh[brk["hh2_bar"]:b + 1].max()), brk["fall"])
                    state = None
            if state == "hl1" and b > brk["hl1_bar"] and cc[b] > brk["hh1"]:
                state, brk["hh2_bar"] = "hh2", b
            if state is None and len(highs) >= 2 and len(lows) >= 2:
                h1, h2 = hh[highs[-2]], hh[highs[-1]]
                l1, l2 = ll[lows[-2]], ll[lows[-1]]
                if h1 > h2 and l1 > l2 and cc[b] > h2:
                    lowest = float(ll[highs[-2]:b + 1].min())
                    state, brk = "broken", {"bar": b, "L2": float(l2), "fall": float((h1 - lowest) / h1)}
    return sigs


def _first_after(lw, idx):
    """Position of the first swing low confirmed after session idx (lw is in confirmation order)."""
    lo, hi = 0, len(lw)
    while lo < hi:
        mid = (lo + hi) // 2
        if lw[mid][0] <= idx:
            lo = mid + 1
        else:
            hi = mid
    return lo


def run_flip(panel, start, end, tf, entry, exit_rule, signals, lows, cost=None, stats=None, time_exit=130):
    assert entry in ("a", "b") and exit_rule in ("STR", "R2", "R3", "T26", "LL", "H2", "H3")
    ledger = Ledger(cost or CostModel())
    sessions = panel.sessions
    st = stats if stats is not None else {}
    by_day = {}
    for s_ in signals:
        by_day.setdefault(s_["sig_idx"] + 1, []).append(s_)
    pending = []                                   # (b) buy-stops alive
    rmult = {"R2": 2.0, "R3": 3.0, "H2": 2.0, "H3": 3.0}.get(exit_rule)
    hmult = {"H2": 1.0, "H3": 1.5}.get(exit_rule)
    per = _period(sessions, tf)
    bar_end = np.r_[per[1:] != per[:-1], True]
    for i, day in enumerate(sessions):
        if day < start or day > end:
            continue
        _delisting_exits(panel, ledger, i, day)
        opens, highs, lows_, closes = (panel.open.iloc[i], panel.high.iloc[i], panel.low.iloc[i], panel.close.iloc[i])
        for e in list(ledger.shares):              # T26 time exit and LL exit at today's open
            m = ledger.meta[e]
            o = opens.get(e, np.nan)
            if not np.isfinite(o):
                continue
            if exit_rule == "T26" and i - m["entry_idx"] >= time_exit:
                ledger.sell(day, e, o, _adv(panel, i, e), "TIME")
            elif exit_rule == "LL" and m.get("ll_exit"):
                ledger.sell(day, e, o, _adv(panel, i, e), "LOWER_LOW")
        for e in ledger.shares:                    # moved stops go live from the session after the move
            m = ledger.meta[e]
            if m.get("pending_stop") is not None and m["pending_from"] <= i:
                m["stop"] = max(m["stop"], m.pop("pending_stop"))
        if exit_rule == "STR":                     # raise stops on higher swing lows confirmed before today
            for e in ledger.shares:
                m = ledger.meta[e]
                lw, p_ = lows.get(e, ()), m.setdefault("p_str", _first_after(lows.get(e, ()), m["sig_idx"]))
                while p_ < len(lw) and lw[p_][0] < i:
                    if lw[p_][1] * (1 - STOP_BUF) > m["stop"]:
                        m["stop"] = lw[p_][1] * (1 - STOP_BUF)
                    p_ += 1
                m["p_str"] = p_
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
            extra = {"stop": stop, "entry_idx": i, "sig_idx": s_["sig_idx"], "ref_low": s_["hl"], "px": px,
                     "target": px + rmult * (px - stop) if rmult else None,
                     "half_level": px + hmult * (px - stop) if hmult else None}
            if ledger.buy(day, e, px, min(eq_now / SLOTS, ledger.cash * 0.995), _adv(panel, i, e), extra):
                st["entries"] = st.get("entries", 0) + 1
                st["risk_sum"] = st.get("risk_sum", 0.0) + (px - stop) / px
                rk = (px - stop) / px
                band = "risk_lt5" if rk < 0.05 else ("risk_5to10" if rk < 0.10 else "risk_ge10")
                st[band] = st.get(band, 0) + 1
        for e in list(ledger.shares):
            m = ledger.meta[e]
            lo, o = lows_.get(e, np.nan), opens.get(e, np.nan)
            if np.isfinite(lo) and lo <= m["stop"]:
                gap = m["entry_idx"] < i and np.isfinite(o) and o < m["stop"]
                ledger.sell(day, e, o if gap else m["stop"], _adv(panel, i, e), "STOP")
                continue
            hi = highs.get(e, np.nan)
            if m.get("half_level") is not None and not m.get("half_done") and np.isfinite(hi) and hi >= m["half_level"]:
                gap = m["entry_idx"] < i and np.isfinite(o) and o > m["half_level"]
                pxh = o if gap else m["half_level"]
                ledger.trim(e, pxh, ledger.shares[e] * pxh / 2, _adv(panel, i, e))
                m["half_done"] = True
                m["pending_stop"], m["pending_from"] = m["px"], i + 1
                st["half_exits"] = st.get("half_exits", 0) + 1
            if m.get("target") is not None and np.isfinite(hi) and hi >= m["target"]:
                gap = m["entry_idx"] < i and np.isfinite(o) and o > m["target"]
                ledger.sell(day, e, o if gap else m["target"], _adv(panel, i, e), "TARGET")
        if exit_rule == "LL":                      # a completed bar closing below the latest confirmed swing low
            for e in ledger.shares:
                m = ledger.meta[e]
                lw, p_ = lows.get(e, ()), m.setdefault("p_ll", _first_after(lows.get(e, ()), m["sig_idx"]))
                while p_ < len(lw) and lw[p_][0] <= i:
                    m["ref_low"] = lw[p_][1]
                    p_ += 1
                m["p_ll"] = p_
                c_ = closes.get(e, np.nan)
                if bar_end[i] and np.isfinite(c_) and c_ < m["ref_low"]:
                    m["ll_exit"] = True
        ledger.mark(day, closes)
    return _result(ledger)


def monthly_uptrend(panel, kind, tf="M"):
    """docs/weekly_flip_trend_filter_preregistration.md. Returns {entity: (ends, up)}: ends = last
    session index of each completed monthly bar (ascending), up = bool array, the stock's monthly
    trend at the close of that month.
      FS  last two confirmed monthly swing highs rising and last two confirmed swing lows rising
          (k = 1, a swing confirmed one month after its bar)
      FR  in the top 100 of that month's PIT universe by the 12-1 score (as A10) at the month's last session
      FM  monthly close > 10-month SMA of monthly closes, and that SMA > the previous month's"""
    assert kind in ("FS", "FR", "FM")
    out = {}
    if kind == "FR":
        from backtesting.pit_strategies import MOM_LOOKBACK, MOM_SKIP
        s = panel.sessions
        closes_ff = panel.close.ffill(limit=5)
        month_end = [i for i in range(len(s)) if i + 1 == len(s) or s[i + 1].month != s[i].month]
        top = {}
        for i in month_end:
            if i < MOM_LOOKBACK:
                continue
            members = [e for e in panel.universe_on(s[i]) if e in closes_ff.columns]
            mom = (closes_ff.iloc[i - MOM_SKIP][members] / closes_ff.iloc[i - MOM_LOOKBACK][members] - 1).dropna()
            top[i] = set(mom.sort_values(ascending=False).head(100).index)
        ends = np.array(sorted(top), dtype=int)
        for e in panel.close.columns:
            out[e] = (ends, np.array([e in top[i] for i in ends], dtype=bool))
        return out
    k = K[tf]
    for e, hh, ll, cc, end in _per_entity(panel, tf):
        n = len(cc)
        up = np.zeros(n, dtype=bool)
        if kind == "FS":
            sh = {j + k: j for j in _swings(hh, k, True)}
            sl = {j + k: j for j in _swings(ll, k, False)}
            highs, lows = [], []
            for b in range(n):
                if b in sh:
                    highs.append(hh[sh[b]])
                if b in sl:
                    lows.append(ll[sl[b]])
                up[b] = len(highs) >= 2 and len(lows) >= 2 and highs[-1] > highs[-2] and lows[-1] > lows[-2]
        else:
            sma = pd.Series(cc).rolling(10).mean().to_numpy()
            for b in range(10, n):
                up[b] = cc[b] > sma[b] and sma[b] > sma[b - 1]
        out[e] = (np.asarray(end, dtype=int), up)
    return out


def filter_signals(signals, trend):
    """Keeps setups whose stock was in a monthly uptrend at the last completed month whose final
    session is on or before the setup's sig_idx (trend from monthly_uptrend)."""
    kept = []
    for s_ in signals:
        t = trend.get(s_["entity"])
        if t is None:
            continue
        ends, up = t
        k = np.searchsorted(ends, s_["sig_idx"], side="right") - 1
        if k >= 0 and up[k]:
            kept.append(s_)
    return kept


def weekly_uptrend(panel, kind):
    """docs/daily_flip_weekly_trend_preregistration.md: FS / FM on weekly bars (swings k = 2; 10-week
    average rising), FR unchanged (monthly 12-1 top 100). Same output shape as monthly_uptrend."""
    return monthly_uptrend(panel, kind, tf="M" if kind == "FR" else "W")
