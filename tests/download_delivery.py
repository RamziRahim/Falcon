"""
Falcon -- download NSE's daily security-wise delivery position (every stock, every day)
for the conviction-sizing test (docs/conviction_sizing_preregistration.md).

Run from the project root on a machine that can reach NSE (laptop or the Indian-region
server). Resumable: finished days are skipped, so it is safe to stop and re-run.

    python tests/download_delivery.py                       # 2007-01-01 .. today
    python tests/download_delivery.py 2007-01-01 2026-11-27

The bhavcopies Falcon already holds (tests/download_bhavcopies.py) have no delivery
columns, so this is a separate file per day:
  1. MTO_DDMMYYYY.DAT   (nsearchives .../archives/equities/mto/), all years;
  2. sec_bhavdata_full_DDMMYYYY.csv (nsearchives .../products/content/), as a fallback.

Output:
  data/delivery/days/YYYYMMDD.parquet   one file per trading day
  data/delivery/delivery_equity.parquet all days: Date, Symbol, Series, TradedQty, DelivQty, DelivPct
  data/delivery/download_log.csv        status per weekday (ok / holiday_or_missing / error)
"""
import sys
sys.path.insert(0, ".")

import io
import os
import time
from datetime import date, datetime, timedelta

import pandas as pd

OUT_DIR = "data/delivery"
DAYS_DIR = os.path.join(OUT_DIR, "days")
COMBINED = os.path.join(OUT_DIR, "delivery_equity.parquet")
LOG_PATH = os.path.join(OUT_DIR, "download_log.csv")
PAUSE_SECONDS = 0.35
COLUMNS = ["Date", "Symbol", "Series", "TradedQty", "DelivQty", "DelivPct"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9", "Referer": "https://www.nseindia.com/",
}


def mto_url(d: date) -> str:
    return f"https://nsearchives.nseindia.com/archives/equities/mto/MTO_{d.strftime('%d%m%Y')}.DAT"


def full_url(d: date) -> str:
    return f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{d.strftime('%d%m%Y')}.csv"


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.strip().replace({"-": None, "": None}), errors="coerce")


def parse_mto(text: str, d: date) -> pd.DataFrame:
    """Data lines start with record type 20:
    20,<sr no>,<symbol>,<series>,<qty traded>,<deliverable qty>,<% deliverable>"""
    rows = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 7 and parts[0] == "20":
            rows.append(parts[2:7])
    df = pd.DataFrame(rows, columns=["Symbol", "Series", "TradedQty", "DelivQty", "DelivPct"])
    for c in ("TradedQty", "DelivQty", "DelivPct"):
        df[c] = _num(df[c])
    df.insert(0, "Date", pd.Timestamp(d))
    return df[COLUMNS]


def parse_full(text: str, d: date) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(text), dtype=str)
    df.columns = [c.strip().upper() for c in df.columns]
    out = pd.DataFrame({"Date": pd.Timestamp(d), "Symbol": df["SYMBOL"].str.strip(), "Series": df["SERIES"].str.strip(),
                        "TradedQty": _num(df["TTL_TRD_QNTY"]), "DelivQty": _num(df["DELIV_QTY"]),
                        "DelivPct": _num(df["DELIV_PER"])})
    return out[COLUMNS]


def _get(session, url):
    r = session.get(url, headers=HEADERS, timeout=30)
    if r.status_code in (403, 404) or not r.content or r.content.lstrip()[:1] == b"<":
        return None
    r.raise_for_status()
    return r.content.decode("utf-8", errors="replace")


def fetch_day(session, d: date) -> pd.DataFrame | None:
    for url, parse in ((mto_url(d), parse_mto), (full_url(d), parse_full)):
        text = _get(session, url)
        if text:
            df = parse(text, d)
            if len(df):
                return df
        time.sleep(PAUSE_SECONDS)
    return None


def main():
    import requests
    start = datetime.strptime(sys.argv[1], "%Y-%m-%d").date() if len(sys.argv) > 1 else date(2007, 1, 1)
    end = datetime.strptime(sys.argv[2], "%Y-%m-%d").date() if len(sys.argv) > 2 else date.today()
    os.makedirs(DAYS_DIR, exist_ok=True)
    session = requests.Session()
    session.get("https://www.nseindia.com", headers=HEADERS, timeout=30)

    days = [start + timedelta(n) for n in range((end - start).days + 1)]
    days = [d for d in days if d.weekday() < 5]
    log, t0 = [], time.time()
    for i, d in enumerate(days, 1):
        path = os.path.join(DAYS_DIR, f"{d.strftime('%Y%m%d')}.parquet")
        if os.path.exists(path):
            log.append((d, "ok", "cached"))
            continue
        try:
            df = fetch_day(session, d)
            if df is None:
                log.append((d, "holiday_or_missing", ""))
            else:
                df.to_parquet(path, index=False)
                log.append((d, "ok", len(df)))
        except Exception as ex:                       # keep going; re-run retries errors
            log.append((d, "error", repr(ex)[:200]))
            time.sleep(5)
            session = requests.Session()
            session.get("https://www.nseindia.com", headers=HEADERS, timeout=30)
        time.sleep(PAUSE_SECONDS)
        if i % 50 == 0 or i == len(days):
            rate = (time.time() - t0) / i
            print(f"  [{i}/{len(days)}] {d}  ~{rate * (len(days) - i) / 60:.0f} min left", flush=True)

    pd.DataFrame(log, columns=["date", "status", "detail"]).to_csv(LOG_PATH, index=False)
    print(f"\nDay statuses: {pd.Series([s for _, s, _ in log]).value_counts().to_dict()}")
    files = sorted(f for f in os.listdir(DAYS_DIR) if f.endswith(".parquet"))
    combined = pd.concat([pd.read_parquet(os.path.join(DAYS_DIR, f)) for f in files], ignore_index=True)
    combined.to_parquet(COMBINED, index=False)
    print(f"Saved {COMBINED}: {len(combined):,} rows, {combined['Date'].nunique()} days, "
          f"{combined['Date'].min().date()} -> {combined['Date'].max().date()}")


if __name__ == "__main__":
    main()
