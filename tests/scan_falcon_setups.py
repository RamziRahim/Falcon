"""
Falcon -- strategy F's scan (docs/s_and_f_preregistration.md): every 5
sessions, run Falcon's unchanged pattern engine on each universe stock's
adjusted history up to that day and record qualifying pre-breakout setups
with Falcon's own pivot / stop / target.

    python tests/scan_falcon_setups.py 2019-01-01 2026-10-30
    python tests/scan_falcon_setups.py 2008-01-01 2017-12-31

Uses all CPU cores but one. Writes data/pit/falcon_setups_<start>_<end>.parquet.
"""
import os
import sys
sys.path.insert(0, ".")

import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

F_SCAN_EVERY = 5


def _scan_entity(args):
    entity, df, scan_positions = args
    from technical_analysis.pattern_engine import analyze_ticker
    from backtesting.breakout_entries import falcon_setup_from_analysis
    out = []
    for pos in scan_positions:
        if pos < 60:
            continue
        window = df.iloc[: pos + 1]
        try:
            analysis = analyze_ticker(window)
        except Exception:                                  # noqa: BLE001 -- a detector edge case skips that day only
            continue
        atr = window["ATR_14"].iloc[-1]
        close = window["Close"].iloc[-1]
        if not (np.isfinite(atr) and np.isfinite(close)):
            continue
        s = falcon_setup_from_analysis(analysis, float(close), float(atr))
        if s:
            out.append({"entity_id": entity, "scan_date": window["Date"].iloc[-1], **s})
    return out


def main():
    start, end = pd.Timestamp(sys.argv[1]), pd.Timestamp(sys.argv[2])
    tech = pd.read_parquet("data/pit/technicals.parquet",
                           columns=["entity_id", "Date", "Open", "High", "Low", "Close", "Volume", "ATR_14"])
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    sessions = np.sort(tech["Date"].unique())
    in_window = sessions[(sessions >= np.datetime64(start)) & (sessions <= np.datetime64(end))]
    scan_days = in_window[::F_SCAN_EVERY]
    month_ends = np.sort(universe["month_end"].unique())
    members = {pd.Timestamp(m): set(g["entity_id"]) for m, g in universe.groupby("month_end")}
    want = {}
    for d in scan_days:
        k = month_ends.searchsorted(d, side="right") - 1
        if k < 0:
            continue
        for e in members[pd.Timestamp(month_ends[k])]:
            want.setdefault(e, []).append(d)
    jobs = []
    for e, g in tech[tech["entity_id"].isin(want)].groupby("entity_id"):
        g = g.sort_values("Date").reset_index(drop=True)
        g["Volume_SMA_20"] = g["Volume"].rolling(window=20).mean()
        pos = g["Date"].searchsorted(pd.to_datetime(want[e]))
        pos = [int(p) for p, d in zip(pos, want[e]) if p < len(g) and g["Date"].iloc[p] == d]
        if pos:
            jobs.append((e, g, pos))
    total = sum(len(j[2]) for j in jobs)
    workers = max(1, (os.cpu_count() or 2) - 1)
    print(f"{len(jobs)} stocks, {len(scan_days)} scan days, {total:,} stock-days to scan on {workers} workers", flush=True)
    t0, rows = time.time(), []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for n, res in enumerate(pool.map(_scan_entity, jobs, chunksize=4), 1):
            rows.extend(res)
            if n % 100 == 0:
                print(f"  {n}/{len(jobs)} stocks, {len(rows)} setups, {time.time() - t0:.0f}s", flush=True)
    out = pd.DataFrame(rows)
    path = f"data/pit/falcon_setups_{start.date()}_{end.date()}.parquet"
    out.to_parquet(path, index=False)
    print(f"Saved {path}: {len(out):,} setups in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
