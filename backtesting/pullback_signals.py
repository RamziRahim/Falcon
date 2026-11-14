"""
===============================================================================
Falcon AI Swing Trading Platform — pullback signal cells, flags and forward returns
===============================================================================
Script      : pullback_signals.py
Package     : Backtesting

docs/pullback_diagnostics_preregistration.md, Steps 1-2. One row per
(session t, universe stock) that passes a cheap pre-screen (universe member,
finite prices, 6-month momentum in the top 40%), with every pullback rule as a
boolean flag, the loose-set geometry, and the 5/10/15/20-session forward
returns, Nifty 500 forward returns, and 20-session max gain / max drop.
The pre-screen is looser than every set's own momentum rule (top 20%), so no
signal of any set is lost; L3/L0 use mom (top 20%) too.
===============================================================================
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.pit_strategies import Panel
from backtesting.pullback import _rsi

HORIZONS = (5, 10, 15, 20)


def build_cells(panel: Panel, nifty: pd.Series, n500: pd.Series, start, end) -> pd.DataFrame:
    s = panel.sessions
    c = panel.close
    O, H, L, C, V, TO = (x.to_numpy(float) for x in (panel.open, panel.high, panel.low, c, panel.volume, panel.turnover))
    EMA20 = c.ewm(span=20, adjust=False, min_periods=20).mean().to_numpy(float)
    SMA50 = c.rolling(50, min_periods=50).mean().to_numpy(float)
    SMA200 = c.rolling(200, min_periods=200).mean().to_numpy(float)
    HI52 = panel.high.rolling(252, min_periods=200).max().to_numpy(float)
    RSI = _rsi(c).to_numpy(float)
    pc = c.shift(1)
    tr = np.maximum(panel.high - panel.low, np.maximum((panel.high - pc).abs(), (panel.low - pc).abs()))
    ATR = tr.rolling(14, min_periods=14).mean().to_numpy(float)
    VAVG = panel.volume.rolling(50, min_periods=50).mean().shift(1).to_numpy(float)
    TV20 = panel.turnover.rolling(20, min_periods=15).mean().shift(1).to_numpy(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        RAW = TO / V
        MOM = c.shift(10).to_numpy(float) / c.shift(126).to_numpy(float) - 1
        R5 = C / c.shift(5).to_numpy(float) - 1
    cols = {e: j for j, e in enumerate(c.columns)}
    nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
    n50, n200 = nf.rolling(50, min_periods=50).mean(), nf.rolling(200, min_periods=200).mean()
    mkt = ((nf > n200) & (n50 > n50.shift(5))).to_numpy()
    n5 = n500.reindex(n500.index.union(s)).ffill().reindex(s).to_numpy(float)
    T = len(s)
    rows = []
    for t, day in enumerate(s):
        if day < start or day > end or t < 260 or t + 21 >= T:
            continue
        members = [cols[e] for e in panel.universe_on(day) if e in cols]
        if not members:
            continue
        j = np.array(members)
        m = MOM[t, j]
        ok = np.isfinite(m)
        if ok.sum() < 20:
            continue
        pct = pd.Series(m[ok]).rank(pct=True).to_numpy()
        rank = np.full(len(j), np.nan)
        rank[ok] = pct
        keep = rank >= 0.60
        j, rank = j[keep], rank[keep]
        if len(j) == 0:
            continue
        win = H[t - 12: t, j]
        good = np.isfinite(win).all(axis=0) & np.isfinite(C[t, j])
        j, rank, win = j[good], rank[good], win[:, good]
        if len(j) == 0:
            continue
        h = np.argmax(win, axis=0) + t - 12
        dip = t - 1 - h
        out = []
        for q in range(len(j)):
            jj, hh = j[q], h[q]
            seg_l = L[hh + 1: t + 1, jj]
            if not np.isfinite(seg_l).any():
                continue
            k = hh + 1 + int(np.nanargmin(seg_l))
            pl = seg_l[k - hh - 1]
            depth = 1 - pl / H[hh, jj]
            vol_ok = bool(np.nanmean(V[hh + 1: t, jj]) < VAVG[hh, jj]) if dip[q] >= 1 else False
            rmin = np.nanmin(RSI[hh + 1: t, jj]) if dip[q] >= 1 else np.nan
            stop = pl - 0.5 * ATR[t, jj]
            x = C[t, jj]
            fwd = {f"r{k_}": C[t + k_, jj] / x - 1 for k_ in HORIZONS}
            fwd.update({f"n{k_}": n5[t + k_] / n5[t] - 1 for k_ in HORIZONS})
            hi20, lo20 = np.nanmax(H[t + 1: t + 21, jj]), np.nanmin(L[t + 1: t + 21, jj])
            out.append({
                "t": t, "date": day, "entity_id": c.columns[jj], "rank": rank[q],
                "mkt": bool(mkt[t]),
                "liq": bool(RAW[t, jj] > 100 and TV20[t, jj] > 1e8),
                "mom": bool(rank[q] >= 0.80),
                "near52": bool(x >= 0.85 * HI52[t, jj]),
                "trend": bool(x > SMA50[t, jj] and x > SMA200[t, jj] and SMA50[t, jj] > SMA50[t - 10, jj]
                              and SMA200[t, jj] > SMA200[t - 10, jj]),
                "trig": bool(x > H[t - 1, jj]),
                "dip_len": int(dip[q]), "depth_v": float(depth),
                "dip": bool(3 <= dip[q] <= 8), "depth": bool(0.05 <= depth <= 0.12),
                "nearma": bool(pl <= EMA20[k, jj] * 1.01 or pl <= SMA50[k, jj] * 1.01),
                "vol": vol_ok, "rsi": bool(np.isfinite(rmin) and 35 <= rmin <= 50),
                "stop8": bool(np.isfinite(stop) and stop < x and (x - stop) / x <= 0.08),
                "r5neg": bool(R5[t, jj] < 0),
                "atr": ATR[t, jj], "close": x,
                "mfe20": hi20 / x - 1, "mae20": lo20 / x - 1, **fwd})
        rows.extend(out)
    d = pd.DataFrame(rows)
    for k_ in HORIZONS:
        d[f"x{k_}"] = d[f"r{k_}"] - d[f"n{k_}"]
    return d


FLAGS = ["mkt", "liq", "mom", "near52", "trend", "trig", "dip", "depth", "nearma", "vol", "rsi", "stop8"]


def signal_sets(d: pd.DataFrame) -> dict:
    lead = d.mkt & d.liq & d.mom & d.near52 & d.trend
    strict = lead & d.trig & d.dip & d.depth & d.nearma & d.vol & d.rsi & d.stop8
    l1 = lead & d.trig & d.dip & d.depth & d.nearma & d.stop8
    l2 = lead & d.trig & d.dip_len.between(2, 10) & d.depth_v.between(0.03, 0.15)
    l3 = lead & d.trig & d.r5neg
    return {"STRICT": strict, "L1": l1, "L2": l2, "L3": l3, "L0": lead}
