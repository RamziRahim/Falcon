"""
Falcon -- sector strength per stock and session (docs/momentum_sector_exits_preregistration.md).

Falcon Momentum's existing sector confirmation (backtesting/falcon_momentum.py), as a boolean
frame (sessions x entities): at each session, using the latest month-end mapping on or before it,
  - a stock matched to an NSE sector index (best 252-session return correlation >= CORR_MIN)
    is strong when that index's 6-month return beats the Nifty 50's and the index is above
    its 50-day average (idx_ok, as in run_falcon_momentum);
  - an unmatched stock is strong when its peer group's 6-month strength percentile
    (peer_strength) is >= PEER_STRONG.
"""
import numpy as np
import pandas as pd

from backtesting.breakout_entries import peer_strength
from backtesting.falcon_momentum import PEER_STRONG, SECTOR_INDICES, sector_maps


def sector_strong(panel, indices: pd.DataFrame, nifty: pd.Series) -> pd.DataFrame:
    s = panel.sessions
    c = panel.close
    idx = indices.reindex(indices.index.union(s)).ffill().reindex(s)
    idx = idx[[x for x in SECTOR_INDICES if x in idx.columns]]
    nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
    n126 = nf / nf.shift(126) - 1
    idx_ok = (idx / idx.shift(126) - 1).gt(n126, axis=0) & (idx > idx.rolling(50, min_periods=50).mean())
    smaps = sector_maps(panel, idx)
    groups = peer_strength(panel, c / c.shift(126) - 1)
    months = sorted(set(smaps) | set(groups))
    out = np.zeros((len(s), c.shape[1]), dtype=bool)
    cols = {e: j for j, e in enumerate(c.columns)}
    ok_np = idx_ok.to_numpy()
    icol = {n: k for k, n in enumerate(idx_ok.columns)}
    for q, m in enumerate(months):
        a = s.searchsorted(m, side="right")                          # sessions after month end m ...
        b = s.searchsorted(months[q + 1], side="right") if q + 1 < len(months) else len(s)
        if a >= b:
            continue
        # the session AT month end m uses the previous mapping; from the next session on, this one
        smap, grp = smaps.get(m, {}), groups.get(m, pd.Series(dtype=float))
        for e, j in cols.items():
            name = smap.get(e)
            if name is not None:
                out[a:b, j] = ok_np[a:b, icol[name]]
            else:
                out[a:b, j] = grp.get(e, 0.0) >= PEER_STRONG
    # sessions on a month end use the mapping formed at that same close (latest on or before the day)
    res = pd.DataFrame(out, index=s, columns=c.columns)
    for m in months:
        if m in s:
            i = s.get_loc(m)
            smap, grp = smaps.get(m, {}), groups.get(m, pd.Series(dtype=float))
            row = np.zeros(c.shape[1], dtype=bool)
            for e, j in cols.items():
                name = smap.get(e)
                row[j] = ok_np[i, icol[name]] if name is not None else grp.get(e, 0.0) >= PEER_STRONG
            res.iloc[i] = row
    return res
