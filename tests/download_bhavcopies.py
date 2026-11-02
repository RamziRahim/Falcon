"""
Falcon -- download NSE daily bhavcopies (every listed stock, every day) for
a survivorship-bias-free history.

Run from the project root (needs internet; ~1,700 trading days, roughly
30-60 minutes; safe to stop and re-run -- finished days are skipped):

    python tests/download_bhavcopies.py                 # 2018-01-01 .. 2024-12-31
    python tests/download_bhavcopies.py 2018-01-01 2024-12-31

Why: data/technical/ only holds stocks that are in TODAY's Nifty 500, so any
test on 2019-2024 silently leaves out every company that later collapsed,
was delisted or dropped out -- it flatters any strategy. A bhavcopy is
NSE's own end-of-day file for the WHOLE market on that date, including
companies that no longer exist, so a universe built from it is point-in-time.

Output:
  data/bhavcopy/days/YYYYMMDD.parquet   one file per trading day (resumable)
  data/bhavcopy/bhavcopy_equity.parquet all days combined, equity series only:
      Date, Symbol, ISIN, Series, Open, High, Low, Close, PrevClose,
      Volume, Turnover
  data/bhavcopy/download_log.csv        status per calendar day
                                         (ok / holiday_or_missing / error)

Two NSE formats, both handled: the legacy archive
(content/historical/EQUITIES/YYYY/MON/cmDDMONYYYYbhav.csv.zip) and the
UDiFF common bhavcopy (content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip)
NSE switched to in July 2024. Each day tries the expected format first and
the other as a fallback.
"""
import sys
sys.path.insert(0, ".")

import io
import os
import time
import zipfile
from datetime import date, datetime, timedelta

import pandas as pd
import requests

OUT_DIR = "data/bhavcopy"
DAYS_DIR = os.path.join(OUT_DIR, "days")
COMBINED = os.path.join(OUT_DIR, "bhavcopy_equity.parquet")
LOG_PATH = os.path.join(OUT_DIR, "download_log.csv")
EQUITY_SERIES = {"EQ", "BE", "BZ", "BL", "SM", "ST"}
UDIFF_FROM = date(2024, 7, 8)
PAUSE_SECONDS = 0.35

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9", "Referer": "https://www.nseindia.com/",
}


def _legacy_url(d: date) -> str:
    mon = d.strftime("%b").upper()
    return (f"https://nsearchives.nseindia.com/content/historical/EQUITIES/{d.year}/{mon}/"
            f"cm{d.strftime('%d')}{mon}{d.year}bhav.csv.zip")


def _udiff_url(d: date) -> str:
    return f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{d.strftime('%Y%m%d')}_F_0000.csv.zip"


def _parse_legacy(df: pd.DataFrame, d: date) -> pd.DataFrame:
    df.columns = [c.strip().upper() for c in df.columns]
    return pd.DataFrame({
        "Date": pd.Timestamp(d), "Symbol": df["SYMBOL"].str.strip(), "ISIN": df.get("ISIN"),
        "Series": df["SERIES"].str.strip(), "Open": df["OPEN"], "High": df["HIGH"], "Low": df["LOW"],
        "Close": df["CLOSE"], "PrevClose": df["PREVCLOSE"], "Volume": df["TOTTRDQTY"], "Turnover": df["TOTTRDVAL"],
    })


def _parse_udiff(df: pd.DataFrame, d: date) -> pd.DataFrame:
    df = df[df["FinInstrmTp"].astype(str).str.strip() == "STK"] if "FinInstrmTp" in df.columns else df
    return pd.DataFrame({
        "Date": pd.Timestamp(d), "Symbol": df["TckrSymb"].str.strip(), "ISIN": df.get("ISIN"),
        "Series": df["SctySrs"].astype(str).str.strip(), "Open": df["OpnPric"], "High": df["HghPric"],
        "Low": df["LwPric"], "Close": df["ClsPric"], "PrevClose": df["PrvsClsgPric"],
        "Volume": df["TtlTradgVol"], "Turnover": df["TtlTrfVal"],
    })


def _fetch(session: requests.Session, url: str) -> pd.DataFrame | None:
    r = session.get(url, headers=HEADERS, timeout=30)
    if r.status_code in (403, 404) or not r.content or r.content[:2] != b"PK":
        return None
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        name = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
        return pd.read_csv(z.open(name))


def fetch_day(session: requests.Session, d: date) -> pd.DataFrame | None:
    order = [("udiff", _udiff_url, _parse_udiff), ("legacy", _legacy_url, _parse_legacy)]
    if d < UDIFF_FROM:
        order.reverse()
    for _, url_fn, parse in order:
        raw = _fetch(session, url_fn(d))
        if raw is not None and not raw.empty:
            out = parse(raw, d)
            return out[out["Series"].isin(EQUITY_SERIES)].reset_index(drop=True)
        time.sleep(PAUSE_SECONDS)
    return None


def main():
    start = datetime.strptime(sys.argv[1], "%Y-%m-%d").date() if len(sys.argv) > 1 else date(2018, 1, 1)
    end = datetime.strptime(sys.argv[2], "%Y-%m-%d").date() if len(sys.argv) > 2 else date(2024, 12, 31)
    os.makedirs(DAYS_DIR, exist_ok=True)

    session = requests.Session()
    session.get("https://www.nseindia.com", headers=HEADERS, timeout=30)   # cookies

    log = []
    days = [start + timedelta(n) for n in range((end - start).days + 1)]
    days = [d for d in days if d.weekday() < 5]
    t0 = time.time()
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
    statuses = pd.Series([s for _, s, _ in log]).value_counts().to_dict()
    print(f"\nDay statuses: {statuses}")

    files = sorted(f for f in os.listdir(DAYS_DIR) if f.endswith(".parquet"))
    combined = pd.concat([pd.read_parquet(os.path.join(DAYS_DIR, f)) for f in files], ignore_index=True)
    combined.to_parquet(COMBINED, index=False)
    print(f"Saved {COMBINED}: {len(combined):,} rows, {combined['Date'].nunique()} trading days, "
          f"{combined['ISIN'].nunique():,} distinct ISINs, {combined['Date'].min().date()} -> {combined['Date'].max().date()}")
    if statuses.get("error"):
        print("Some days errored (network). Re-run the same command to retry just those.")


if __name__ == "__main__":
    main()
