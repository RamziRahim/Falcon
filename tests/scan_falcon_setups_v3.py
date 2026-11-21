"""
Falcon -- pattern engine v3 scan (docs/falcon_v3_patterns_preregistration.md rules 1-2).
Every 5 sessions (same scan days as tests/scan_falcon_setups.py), run classify_nse_stock on
each universe stock's last 400 adjusted sessions up to the scan day; keep REAL_PATTERN and
UNSURE verdicts with their pivot and stop.

    python tests/scan_falcon_setups_v3.py 2019-01-01 2026-10-30
Writes data/pit/falcon_setups_v3_<start>_<end>.parquet.
"""
import sys
sys.path.insert(0, ".")

import time

import numpy as np
import pandas as pd

from backtesting.pit_strategies import make_panel
from technical_analysis.pattern_system_v3.engine import classify_nse_stock

F_SCAN_EVERY, HISTORY = 5, 400


def main():
    start, end = pd.Timestamp(sys.argv[1]), pd.Timestamp(sys.argv[2])
    tech_dates = pd.read_parquet("data/pit/technicals.parquet", columns=["Date"])["Date"]
    sessions = np.sort(tech_dates.unique())
    in_window = sessions[(sessions >= np.datetime64(start)) & (sessions <= np.datetime64(end))]
    scan_days = in_window[::F_SCAN_EVERY]
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    month_ends = np.sort(universe["month_end"].unique())
    members = {pd.Timestamp(m): set(g["entity_id"]) for m, g in universe.groupby("month_end")}
    panel = make_panel(pd.read_parquet("data/pit/prices_adjusted.parquet"), universe)
    pos = {d: k for k, d in enumerate(panel.sessions)}
    cols = {e: j for j, e in enumerate(panel.close.columns)}
    arr = {k: getattr(panel, k.lower()).to_numpy(float) for k in ("Open", "High", "Low", "Close", "Volume")}
    rows, n_calls, t0 = [], 0, time.time()
    for n, d in enumerate(scan_days, 1):
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
            n_calls += 1
            try:
                sig = classify_nse_stock(df)
            except Exception:                                  # noqa: BLE001 -- an edge case skips that stock-day only
                continue
            if sig.verdict in ("REAL_PATTERN", "UNSURE"):
                rows.append({"entity_id": e, "scan_date": d, "verdict": sig.verdict, "pattern": sig.pattern_type,
                             "pivot": sig.breakout_level, "stop": sig.stop_loss, "risk_pct": sig.risk_pct,
                             "dist_pct": sig.dist_to_pivot_pct, "score": sig.score})
        if n % 50 == 0:
            print(f"  {n}/{len(scan_days)} scan days, {n_calls:,} stock-days, {len(rows)} setups, {time.time() - t0:.0f}s", flush=True)
    out = pd.DataFrame(rows)
    path = f"data/pit/falcon_setups_v3_{start.date()}_{end.date()}.parquet"
    out.to_parquet(path, index=False)
    print(f"Saved {path}: {len(out):,} setups from {n_calls:,} stock-days in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
