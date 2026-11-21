"""
Falcon -- extra inputs for the Nov 2026 refresh and the 2000-2006 history
(run on the laptop; needs NSE access; safe to re-run, finished parts are skipped):

    python tests/download_extras_2026_11.py

Writes, without touching any existing file:
  data/pit_sources/corporate_actions_2000_2004.parquet    year by year
  data/pit_sources/corporate_actions_2026_recent.parquet  1 Oct 2026 -> today
  data/pit_sources/indices_2000/<INDEX>.parquet and
  data/pit_sources/indices_2000_2026.parquet              2000-01-01 -> today, 85-day chunks
  data/pit_sources/symbol_changes_2026_11.csv             NSE's current symbol-change list
A short report goes to data/pit_sources/extras_2026_11.log.
"""
import sys
sys.path.insert(0, ".")

import os
import time
from datetime import date, timedelta

import pandas as pd

from tests.download_history_sources import CHUNK_DAYS, INDICES, _index_chunk

OUT = "data/pit_sources"
LOG = os.path.join(OUT, "extras_2026_11.log")


def log(msg):
    print(msg, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(msg + "\n")


def actions(path, spans):
    if os.path.exists(path):
        log(f"  {path} exists -- skipped")
        return
    from nselib import capital_market
    frames = []
    for a, b in spans:
        for attempt in range(3):
            try:
                df = capital_market.corporate_actions_for_equity(from_date=a.strftime("%d-%m-%Y"), to_date=b.strftime("%d-%m-%Y"))
                frames.append(df)
                log(f"  corporate actions {a} -> {b}: {len(df)} records")
                break
            except Exception as ex:                      # noqa: BLE001
                log(f"  corporate actions {a} -> {b}: attempt {attempt + 1} failed ({ex!r})"[:300])
                time.sleep(5)
        time.sleep(1)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not out.empty:
        out["exDate"] = pd.to_datetime(out["exDate"], errors="coerce", dayfirst=True)
    out.to_parquet(path, index=False)
    log(f"  saved {path}: {len(out)} records")


def indices(start=date(2000, 1, 1), end=None):
    end = end or date.today()
    d = os.path.join(OUT, "indices_2000")
    os.makedirs(d, exist_ok=True)
    for name in INDICES:
        path = os.path.join(d, name.replace(" ", "_") + ".parquet")
        if os.path.exists(path):
            log(f"  {name}: exists -- skipped")
            continue
        frames, cursor, failures = [], start, 0
        while cursor <= end:
            chunk_end = min(cursor + timedelta(days=CHUNK_DAYS), end)
            try:
                part = _index_chunk(name, cursor, chunk_end)
                if part is not None:
                    frames.append(part)
            except Exception:                            # noqa: BLE001
                failures += 1
            cursor = chunk_end + timedelta(days=1)
            time.sleep(0.4)
        if frames:
            df = pd.concat(frames).drop_duplicates("Date").sort_values("Date").reset_index(drop=True)
            df.to_parquet(path, index=False)
            log(f"  {name}: {len(df)} days, {df['Date'].min().date()} -> {df['Date'].max().date()} ({failures} failed chunks)")
        else:
            log(f"  {name}: no data ({failures} failed chunks)")
    files = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".parquet")]
    combined = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    path = os.path.join(OUT, "indices_2000_2026.parquet")
    combined.to_parquet(path, index=False)
    log(f"  saved {path}: {combined['Index'].nunique()} indices, {len(combined):,} rows")


def symbol_changes():
    import requests
    path = os.path.join(OUT, "symbol_changes_2026_11.csv")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
               "Referer": "https://www.nseindia.com/"}
    s = requests.Session()
    s.get("https://www.nseindia.com", headers=headers, timeout=30)
    r = s.get("https://nsearchives.nseindia.com/content/equities/symbolchange.csv", headers=headers, timeout=60)
    r.raise_for_status()
    with open(path, "wb") as fh:
        fh.write(r.content)
    log(f"  saved {path} ({len(r.content.splitlines())} lines)")


def main():
    os.makedirs(OUT, exist_ok=True)
    log(f"=== run {pd.Timestamp.now()} ===")
    log("1. Corporate actions 2000-2004")
    actions(os.path.join(OUT, "corporate_actions_2000_2004.parquet"),
            [(date(y, 1, 1), date(y, 12, 31)) for y in range(2000, 2005)])
    log("2. Corporate actions Oct 2026 -> today")
    actions(os.path.join(OUT, "corporate_actions_2026_recent.parquet"), [(date(2026, 10, 1), date.today())])
    log("3. Symbol changes")
    try:
        symbol_changes()
    except Exception as ex:                              # noqa: BLE001
        log(f"  symbol changes failed: {ex!r}"[:300])
    log("4. Index history 2000 -> today")
    indices()
    log("DONE")


if __name__ == "__main__":
    main()
