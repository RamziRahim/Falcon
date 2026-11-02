"""
Falcon -- download the extra inputs for a clean 2007-onwards history
(run on the laptop; needs NSE access; safe to re-run, finished parts are
skipped):

    python tests/download_history_sources.py

1. NSE corporate actions 2005-2015, year by year
   -> data/pit_sources/corporate_actions_2005_2015.parquet
   (data/corporate_actions_cache.parquet already covers 2016 onwards)
2. Daily index history 2006 -> today for the broad and sector indices,
   fetched in 85-day chunks (NSE's index API silently truncates longer
   requests, see tests/backfill_rs_macd.py)
   -> data/pit_sources/indices.parquet  (Index, Date, Open, High, Low, Close)

The stock prices themselves come from tests/download_bhavcopies.py.
"""
import sys
sys.path.insert(0, ".")

import os
import time
from datetime import date, timedelta

import pandas as pd

OUT = "data/pit_sources"
ACTIONS_PATH = os.path.join(OUT, "corporate_actions_2005_2015.parquet")
INDEX_DIR = os.path.join(OUT, "indices")
INDICES_PATH = os.path.join(OUT, "indices.parquet")
INDICES = [
    "NIFTY 50", "NIFTY NEXT 50", "NIFTY 100", "NIFTY 200", "NIFTY 500",
    "NIFTY MIDCAP 100", "NIFTY SMALLCAP 100", "NIFTY BANK", "NIFTY IT", "NIFTY FINANCIAL SERVICES",
    "NIFTY PHARMA", "NIFTY AUTO", "NIFTY FMCG", "NIFTY METAL", "NIFTY ENERGY", "NIFTY REALTY",
    "NIFTY MEDIA", "NIFTY INFRA", "NIFTY PSU BANK", "NIFTY INDIA MANUFACTURING",
]
CHUNK_DAYS = 85


def download_actions():
    if os.path.exists(ACTIONS_PATH):
        print(f"  {ACTIONS_PATH} exists -- skipped")
        return
    from nselib import capital_market
    frames = []
    for year in range(2005, 2016):
        for attempt in range(3):
            try:
                df = capital_market.corporate_actions_for_equity(from_date=f"01-01-{year}", to_date=f"31-12-{year}")
                frames.append(df)
                print(f"  corporate actions {year}: {len(df)} records")
                break
            except Exception as ex:                      # noqa: BLE001
                print(f"  corporate actions {year}: attempt {attempt + 1} failed ({ex})")
                time.sleep(5)
        time.sleep(1)
    actions = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not actions.empty:
        actions["exDate"] = pd.to_datetime(actions["exDate"], errors="coerce", dayfirst=True)
    actions.to_parquet(ACTIONS_PATH, index=False)
    print(f"  saved {ACTIONS_PATH}: {len(actions)} records")


def _index_chunk(name, start, end):
    from nselib import capital_market
    raw = capital_market.index_data(index=name, from_date=start.strftime("%d-%m-%Y"), to_date=end.strftime("%d-%m-%Y"))
    if raw is None or raw.empty:
        return None
    return pd.DataFrame({
        "Index": name,
        "Date": pd.to_datetime(raw["TIMESTAMP"], format="%d-%b-%Y"),
        "Open": pd.to_numeric(raw["OPEN_INDEX_VAL"], errors="coerce"),
        "High": pd.to_numeric(raw["HIGH_INDEX_VAL"], errors="coerce"),
        "Low": pd.to_numeric(raw["LOW_INDEX_VAL"], errors="coerce"),
        "Close": pd.to_numeric(raw["CLOSE_INDEX_VAL"], errors="coerce"),
    })


def download_indices(start=date(2006, 1, 1), end=None):
    end = end or date.today()
    os.makedirs(INDEX_DIR, exist_ok=True)
    for name in INDICES:
        path = os.path.join(INDEX_DIR, name.replace(" ", "_") + ".parquet")
        if os.path.exists(path):
            print(f"  {name}: exists -- skipped")
            continue
        frames, cursor, failures = [], start, 0
        while cursor <= end:
            chunk_end = min(cursor + timedelta(days=CHUNK_DAYS), end)
            try:
                part = _index_chunk(name, cursor, chunk_end)
                if part is not None:
                    frames.append(part)
            except Exception:                            # noqa: BLE001 (index may not exist that far back)
                failures += 1
            cursor = chunk_end + timedelta(days=1)
            time.sleep(0.4)
        if frames:
            df = pd.concat(frames).drop_duplicates("Date").sort_values("Date").reset_index(drop=True)
            df.to_parquet(path, index=False)
            print(f"  {name}: {len(df)} days, {df['Date'].min().date()} -> {df['Date'].max().date()}"
                  f"{f' ({failures} empty/failed chunks)' if failures else ''}")
        else:
            print(f"  {name}: no data")
    files = [os.path.join(INDEX_DIR, f) for f in os.listdir(INDEX_DIR) if f.endswith(".parquet")]
    combined = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    combined.to_parquet(INDICES_PATH, index=False)
    print(f"  saved {INDICES_PATH}: {combined['Index'].nunique()} indices, {len(combined):,} rows")


def main():
    os.makedirs(OUT, exist_ok=True)
    print("1. Corporate actions 2005-2015")
    download_actions()
    print("2. Index history")
    download_indices()


if __name__ == "__main__":
    main()
