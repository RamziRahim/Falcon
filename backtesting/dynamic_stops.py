"""
Confluence stop for monthly momentum (docs/momentum_risk_sizing_preregistration.md).

conf_candidates(panel) -> dict of four DataFrames (panel.sessions x entities), each giving, for
session i, a candidate support level known before session i's open:
  c1 previous calendar week's low; c2 lowest low of the 20 sessions to i-1;
  c3 close(i-1) - 2 x ATR(14)(i-1) (Wilder); c4 weekly S1 level valid for session i.
choose_stop(P, levels) applies the frozen rule and returns (stop, branch).
"""
import numpy as np
import pandas as pd

from backtesting.weekly_support import _weekly, weekly_support_levels

VALID_LO, VALID_HI, BAND, BELOW, FALLBACK = 0.85, 0.97, 0.02, 0.01, 0.10


def _prev_week_low(panel) -> pd.DataFrame:
    wk, _, L, _ = _weekly(panel)
    pos = pd.Series(np.arange(len(L.index)), index=L.index)
    prev = pos.reindex(wk).to_numpy() - 1
    arr = np.full((len(panel.sessions), L.shape[1]), np.nan, dtype=np.float32)
    ok = prev >= 0
    arr[ok] = L.to_numpy(np.float32)[prev[ok]]
    return pd.DataFrame(arr, index=panel.sessions, columns=L.columns)


def conf_candidates(panel) -> dict:
    cols = panel.close.columns
    c1 = _prev_week_low(panel).reindex(columns=cols)
    c2 = panel.low.rolling(20, min_periods=20).min().shift(1).astype(np.float32)
    pc = panel.close.shift(1)
    tr = pd.DataFrame(np.fmax(np.fmax((panel.high - panel.low).to_numpy(float), (panel.high - pc).abs().to_numpy(float)),
                              (panel.low - pc).abs().to_numpy(float)), index=panel.close.index, columns=cols)
    atr = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    c3 = (panel.close - 2 * atr).shift(1).astype(np.float32)
    c4 = weekly_support_levels(panel, ("S1",))["S1"].reindex(columns=cols).astype(np.float32)
    return {"c1": c1, "c2": c2, "c3": c3, "c4": c4}


def choose_stop(P: float, levels: dict):
    """levels: {"c1": x, ...} for one stock and session. Returns (stop, branch) with branch in
    {"cluster", "atr", "pct"}."""
    valid = {k: float(v) for k, v in levels.items() if v is not None and np.isfinite(v) and VALID_LO * P <= v < VALID_HI * P}
    if valid:
        band = BAND * P
        best, best_n, best_lv = None, 0, -np.inf
        for k, v in valid.items():
            members = [u for u in valid.values() if abs(u - v) <= band]
            n = len(members)
            if n > best_n or (n == best_n and v > best_lv):
                best, best_n, best_lv = members, n, v
        if best_n >= 2:
            return min(best) * (1 - BELOW), "cluster"
        if "c3" in valid:
            return valid["c3"], "atr"
    return P * (1 - FALLBACK), "pct"
