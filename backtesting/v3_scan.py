"""
Falcon -- the v3 pattern scan as a function (same logic as tests/scan_falcon_setups_v3.py:
every 5th session from `start`, classify_nse_stock on each universe stock's last 400 adjusted
sessions; keep REAL_PATTERN and UNSURE with pivot and stop). Used by the paper engine.
"""
import numpy as np
import pandas as pd

from technical_analysis.pattern_system_v3.engine import classify_nse_stock

F_SCAN_EVERY, HISTORY = 5, 400


def scan_setups(panel, universe: pd.DataFrame, start, end) -> pd.DataFrame:
    sessions = np.asarray(panel.sessions.values)
    in_window = sessions[(sessions >= np.datetime64(pd.Timestamp(start))) & (sessions <= np.datetime64(pd.Timestamp(end)))]
    scan_days = in_window[::F_SCAN_EVERY]
    month_ends = np.sort(pd.to_datetime(universe["month_end"]).unique())
    members = {pd.Timestamp(m): set(g["entity_id"]) for m, g in universe.assign(month_end=pd.to_datetime(universe["month_end"])).groupby("month_end")}
    pos = {d: k for k, d in enumerate(panel.sessions)}
    cols = {e: j for j, e in enumerate(panel.close.columns)}
    arr = {k: getattr(panel, k.lower()).to_numpy(float) for k in ("Open", "High", "Low", "Close", "Volume")}
    rows = []
    for d in scan_days:
        d = pd.Timestamp(d)
        k = month_ends.searchsorted(np.datetime64(d), side="right") - 1
        if k < 0 or d not in pos:
            continue
        t = pos[d]
        for e in sorted(members[pd.Timestamp(month_ends[k])]):
            j = cols.get(e)
            if j is None or not np.isfinite(arr["Close"][t, j]):
                continue
            a = max(0, t - HISTORY + 1)
            df = pd.DataFrame({c: v[a:t + 1, j] for c, v in arr.items()}).dropna().reset_index(drop=True)
            if len(df) < 220:
                continue
            try:
                sig = classify_nse_stock(df)
            except Exception:                                  # noqa: BLE001 -- an edge case skips that stock-day only
                continue
            if sig.verdict in ("REAL_PATTERN", "UNSURE"):
                rows.append({"entity_id": e, "scan_date": d, "verdict": sig.verdict, "pattern": sig.pattern_type,
                             "pivot": sig.breakout_level, "stop": sig.stop_loss, "risk_pct": sig.risk_pct,
                             "dist_pct": sig.dist_to_pivot_pct, "score": sig.score})
    cols_out = ["entity_id", "scan_date", "verdict", "pattern", "pivot", "stop", "risk_pct", "dist_pct", "score"]
    return pd.DataFrame(rows, columns=cols_out)
