"""
Falcon paper trading -- bring the point-in-time data up to the latest NSE session
(docs/paper_trading_plan.md, "Daily cycle" step 1). Needs NSE access (laptop or the
Indian-region server). Safe to re-run: every step is incremental or a full re-fetch of a
small file.

    python paper/data_update.py            # up to today
    python paper/data_update.py 2026-11-30 # up to a given date

Steps:
  1. NSE bhavcopies from the day after the last one held  (tests/download_bhavcopies.py)
  2. corporate actions 2026-10-01 -> today                 (data/pit_sources/corporate_actions_2026_recent.parquet)
  3. NSE's symbol-change list                               (data/pit_sources/symbol_changes_2026_11.csv)
  4. index closes from 10 days before the last one held    (data/pit_sources/indices_2000_2026.parquet)
  5. full rebuild of data/pit_v2                            (tests/build_pit_v2.py, the backtest data build)
Writes data/pit_v2/update_done.txt with the last session on success.
"""
import sys
sys.path.insert(0, ".")

import os
import subprocess
import time
from datetime import date, datetime, timedelta

import pandas as pd

PY = sys.executable
SRC = "data/pit_sources"
LOG = "data/pit_v2/update.log"


def log(msg):
    os.makedirs("data/pit_v2", exist_ok=True)
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def run(args):
    log("run: " + " ".join(args))
    r = subprocess.run(args, capture_output=True, text=True)
    tail = (r.stdout or "")[-1500:] + (r.stderr or "")[-1500:]
    log(f"exit {r.returncode}; tail:\n{tail}")
    if r.returncode != 0:
        raise SystemExit(f"step failed: {' '.join(args)}")


def bhavcopies(until: date):
    path = "data/bhavcopy/bhavcopy_equity.parquet"
    last = pd.read_parquet(path, columns=["Date"])["Date"].max()
    start = (pd.Timestamp(last) + pd.Timedelta(days=1)).date()
    if start > until:
        log(f"bhavcopies: up to date ({pd.Timestamp(last).date()})")
        return
    before = pd.read_parquet(path)
    run([PY, "tests/download_bhavcopies.py", start.isoformat(), until.isoformat()])
    after = pd.read_parquet(path)
    if pd.Timestamp(after["Date"].min()) > pd.Timestamp(before["Date"].min()):
        # The downloader rebuilds the combined file from data/bhavcopy/days/. A machine seeded with
        # the combined file only (the Oracle server) has just the new days there, so append them to
        # the history instead of letting them replace it.
        fresh = after[pd.to_datetime(after["Date"]) > pd.Timestamp(last)]
        merged = pd.concat([before, fresh[before.columns]], ignore_index=True)
        merged.to_parquet(path, index=False)
        log(f"bhavcopies: appended {fresh['Date'].nunique()} new day(s) to the history "
            f"({len(before):,} + {len(fresh):,} rows)")
    final = pd.read_parquet(path, columns=["Date"])["Date"]
    if pd.Timestamp(final.min()) > pd.Timestamp(before["Date"].min()) or len(final) < len(before):
        raise SystemExit("bhavcopy history shrank; stopping before the build")


def corporate_actions(until: date):
    from nselib import capital_market
    for attempt in range(3):
        try:
            df = capital_market.corporate_actions_for_equity(from_date="01-10-2026", to_date=until.strftime("%d-%m-%Y"))
            df["exDate"] = pd.to_datetime(df["exDate"], errors="coerce", dayfirst=True)
            df.to_parquet(f"{SRC}/corporate_actions_2026_recent.parquet", index=False)
            log(f"corporate actions 2026-10-01 -> {until}: {len(df)} records")
            return
        except Exception as ex:                          # noqa: BLE001
            log(f"corporate actions attempt {attempt + 1} failed: {ex!r}"[:300])
            time.sleep(5)
    raise SystemExit("corporate actions failed")


def symbol_changes():
    from tests.download_extras_2026_11 import symbol_changes as fetch
    fetch()


def indices(until: date):
    from tests.download_history_sources import INDICES, _index_chunk
    path = f"{SRC}/indices_2000_2026.parquet"
    have = pd.read_parquet(path)
    have["Date"] = pd.to_datetime(have["Date"])
    frames, failed = [have], []
    for name in INDICES:
        last = have.loc[have["Index"] == name, "Date"].max()
        start = (last - pd.Timedelta(days=10)).date() if pd.notna(last) else date(2000, 1, 1)
        try:
            part = _index_chunk(name, start, until)
            if part is not None and len(part):
                part["Date"] = pd.to_datetime(part["Date"])
                frames.append(part)
        except Exception as ex:                          # noqa: BLE001
            failed.append(f"{name}: {ex!r}"[:120])
        time.sleep(0.4)
    out = pd.concat(frames, ignore_index=True).drop_duplicates(["Index", "Date"], keep="last").sort_values(["Index", "Date"])
    out.to_parquet(path, index=False)
    log(f"indices: {out['Index'].nunique()} indices, last {out['Date'].max().date()}; failed: {failed or 'none'}")
    if any(n.startswith("NIFTY 50:") for n in failed):
        raise SystemExit("Nifty 50 update failed")


def delivery(until: date):
    """NSE security-wise delivery for the conviction score (docs/conviction_sizing_preregistration.md).
    Logged only: a failure never stops the update; the score then flags delivery as missing."""
    path = "data/delivery/delivery_equity.parquet"
    try:
        last = pd.read_parquet(path, columns=["Date"])["Date"].max() if os.path.exists(path) else None
        start = (pd.Timestamp(last) + pd.Timedelta(days=1)).date() if last is not None else until - timedelta(days=60)
        if start > until:
            log(f"delivery: up to date ({pd.Timestamp(last).date()})")
            return
        r = subprocess.run([PY, "tests/download_delivery.py", start.isoformat(), until.isoformat()],
                           capture_output=True, text=True, timeout=1800)
        log(f"delivery {start} -> {until}: exit {r.returncode}; {(r.stdout or '')[-300:]}{(r.stderr or '')[-300:]}")
    except Exception as ex:                              # noqa: BLE001
        log(f"delivery failed, score will flag it missing: {ex!r}"[:300])


def main():
    until = datetime.strptime(sys.argv[1], "%Y-%m-%d").date() if len(sys.argv) > 1 else date.today()
    done = "data/pit_v2/update_done.txt"
    if os.path.exists(done):
        os.remove(done)
    log(f"=== update to {until} ===")
    bhavcopies(until)
    corporate_actions(until)
    try:
        symbol_changes()
    except Exception as ex:                              # noqa: BLE001 -- the build falls back to the previous list
        log(f"symbol changes failed, previous list kept: {ex!r}"[:300])
    indices(until)
    delivery(until)
    run([PY, "tests/build_pit_v2.py", "data/bhavcopy/bhavcopy_equity.parquet", "data/pit_v2"])
    last = pd.read_parquet("data/pit_v2/prices_adjusted.parquet", columns=["Date"])["Date"].max()
    with open(done, "w", encoding="utf-8") as fh:
        fh.write(str(pd.Timestamp(last).date()))
    log(f"done: data/pit_v2 last session {pd.Timestamp(last).date()}")


if __name__ == "__main__":
    main()
