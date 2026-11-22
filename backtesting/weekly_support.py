"""
Falcon -- weekly support levels for docs/momentum_weekly_support_preregistration.md.

weekly_support_levels(panel, kind) returns a DataFrame (panel.sessions x entities): the limit
price valid for each session, computed only from calendar weeks (Mon-Fri) that closed before
that session's week. kind:
  "S1"  broken prior high: most recent confirmed weekly swing high that a later weekly close
        rose above and that is below the latest weekly close
  "S2"  average of the last 10 weekly closes
  "S3"  last higher low: most recent confirmed weekly swing low, only if higher than the
        confirmed swing low before it
  "S4"  confluence: of S1, S2, S3 that exist and are below the latest weekly close, the
        midpoint of the closest pair within 3% of each other (measured from the higher one)
A weekly swing high is a week whose high is above the highs of the 2 weeks before and the 2
after; it is confirmed (usable) once the second following week has closed. Swing lows mirror.
"""
import numpy as np
import pandas as pd

SWING_W, AVG_WEEKS, CONFLUENCE = 2, 10, 0.03


def _weekly(panel):
    wk = panel.sessions.to_period("W-SUN")
    h = panel.high.groupby(wk).max()
    l = panel.low.groupby(wk).min()
    c = panel.close.groupby(wk).last()
    return wk, h, l, c


def _swings(x: np.ndarray, high: bool):
    """indices k of swing highs (or lows) in x; confirmed at k + SWING_W."""
    n, out = len(x), []
    for k in range(SWING_W, n - SWING_W):
        v = x[k]
        if not np.isfinite(v):
            continue
        nb = np.r_[x[k - SWING_W:k], x[k + 1:k + 1 + SWING_W]]
        if not np.isfinite(nb).all():
            continue
        if (high and (v > nb).all()) or (not high and (v < nb).all()):
            out.append(k)
    return out


def _levels_one(h, l, c):
    """weekly arrays -> dict kind -> array of levels as of each week's close."""
    n = len(c)
    s1, s3 = np.full(n, np.nan), np.full(n, np.nan)
    s2 = pd.Series(c).rolling(AVG_WEEKS, min_periods=AVG_WEEKS).mean().to_numpy()
    sh, slo = _swings(h, True), _swings(l, False)
    cz = np.nan_to_num(c, nan=-np.inf)
    brk = []                                         # first week after k whose close is above h[k]
    for k in sh:
        hit = np.nonzero(cz[k + 1:] > h[k])[0]
        brk.append(k + 1 + hit[0] if hit.size else n)
    p_lo = 0
    for m in range(n):
        if not np.isfinite(c[m]):
            continue
        for q in range(len(sh) - 1, -1, -1):         # S1
            k = sh[q]
            if k + SWING_W > m or brk[q] > m:
                continue
            if h[k] < c[m]:
                s1[m] = h[k]
                break
        while p_lo < len(slo) and slo[p_lo] + SWING_W <= m:   # S3: confirmed swing lows so far
            p_lo += 1
        if p_lo >= 2 and l[slo[p_lo - 1]] > l[slo[p_lo - 2]]:
            s3[m] = l[slo[p_lo - 1]]
    s4 = np.full(n, np.nan)
    for m in range(n):
        cand = [v for v in (s1[m], s2[m], s3[m]) if np.isfinite(v) and np.isfinite(c[m]) and v < c[m]]
        best = None
        for a in range(len(cand)):
            for b in range(a + 1, len(cand)):
                hi, lo = max(cand[a], cand[b]), min(cand[a], cand[b])
                d = (hi - lo) / hi
                if d <= CONFLUENCE and (best is None or d < best[0]):
                    best = (d, (hi + lo) / 2)
        if best is not None:
            s4[m] = best[1]
    return {"S1": s1, "S2": s2, "S3": s3, "S4": s4}


def weekly_support_levels(panel, kinds=("S1", "S2", "S3", "S4")) -> dict:
    """kind -> DataFrame (panel.sessions x entities) of the level valid for each session."""
    wk, H, L, C = _weekly(panel)
    weeks = C.index
    out = {k: np.full((len(weeks), C.shape[1]), np.nan) for k in kinds}
    for j, e in enumerate(C.columns):
        lv = _levels_one(H[e].to_numpy(float), L[e].to_numpy(float), C[e].to_numpy(float))
        for k in kinds:
            out[k][:, j] = lv[k]
    # level from week m is valid in the sessions of the next week present in the data
    pos = pd.Series(np.arange(len(weeks)), index=weeks)
    prev = pos.reindex(wk).to_numpy() - 1
    res = {}
    for k in kinds:
        arr = np.full((len(panel.sessions), C.shape[1]), np.nan)
        ok = prev >= 0
        arr[ok] = out[k][prev[ok]]
        res[k] = pd.DataFrame(arr, index=panel.sessions, columns=C.columns)
    return res
