"""
Falcon -- build the survivorship-free research dataset from the downloaded
bhavcopies (run tests/download_bhavcopies.py first).

    python tests/build_pit_universe.py

Writes:
  data/pit/prices_adjusted.parquet   every stock, every day, split/bonus-adjusted
  data/pit/universe_monthly.parquet  top 500 by liquidity at each month end
  data/pit/adjustments.csv           every corporate-action adjustment applied
  data/pit/summary.txt               the diagnostics printed below
See market_data/pit_universe.py for the rules.
"""
import sys
sys.path.insert(0, ".")

import glob
import os

import pandas as pd

from market_data.pit_universe import build_adjusted_prices, last_trading_dates, monthly_universe, primary_rows

SRC = "data/bhavcopy/bhavcopy_equity.parquet"
ACTIONS = [
    "data/corporate_actions_cache.parquet",                    # market_data/corporate_actions.py, 2016 onwards
    "data/pit_sources/corporate_actions_2005_2015.parquet",    # tests/download_history_sources.py
]
OUT = "data/pit"


def main():
    os.makedirs(OUT, exist_ok=True)
    bhav = pd.read_parquet(SRC)
    bhav["Date"] = pd.to_datetime(bhav["Date"])
    lines = [f"bhavcopy rows {len(bhav):,}, {bhav['Date'].nunique()} sessions, "
             f"{bhav['Date'].min().date()} -> {bhav['Date'].max().date()}"]

    actions = pd.concat([pd.read_parquet(p) for p in ACTIONS if os.path.exists(p)], ignore_index=True)
    actions["exDate"] = pd.to_datetime(actions["exDate"], errors="coerce", dayfirst=True)
    lines.append(f"corporate-action records {len(actions):,} ({actions['exDate'].min().date()} -> {actions['exDate'].max().date()})")

    # The universe depends only on traded value, series and activity (none
    # of which split adjustment changes), so it is built first and used to
    # decide which stocks get unrecorded-split inference.
    universe = monthly_universe(primary_rows(bhav))
    prices, adjustments = build_adjusted_prices(bhav, actions, infer_for=set(universe["entity_id"]))
    prices.to_parquet(f"{OUT}/prices_adjusted.parquet", index=False)
    adjustments.to_csv(f"{OUT}/adjustments.csv", index=False)
    lines.append(f"entities {prices['entity_id'].nunique():,}; split/bonus adjustments applied {len(adjustments):,} "
                 f"({int(adjustments['suspect'].sum()) if len(adjustments) else 0} where the observed open/close ratio disagrees with the record, "
                 f"{int(adjustments['subject'].astype(str).str.startswith('INFERRED').sum()) if len(adjustments) else 0} inferred from standard-ratio gaps)")

    universe.to_parquet(f"{OUT}/universe_monthly.parquet", index=False)
    lines.append(f"monthly universes {universe['month_end'].nunique()} "
                 f"({universe['month_end'].min().date()} -> {universe['month_end'].max().date()}), "
                 f"{universe['entity_id'].nunique():,} distinct stocks ever in the universe")

    # Sanity: big one-day moves left after adjustment (real crashes/rallies, or a missed action)
    p = prices.sort_values(["entity_id", "Date"])
    move = p.groupby("entity_id")["Close"].pct_change()
    in_uni = p["entity_id"].isin(universe["entity_id"].unique())
    lines.append(f"one-day moves > 40% among universe stocks after adjustment: {int(((move.abs() > 0.4) & in_uni).sum())}")

    # Survivorship: how much of each year's universe is missing from today's data/technical/
    today = {os.path.basename(f)[:-11] for f in glob.glob("data/technical/*.NS.parquet")}
    last = last_trading_dates(prices)
    end = prices["Date"].max()
    for year, grp in universe.groupby(universe["month_end"].dt.year):
        ids = grp["entity_id"].unique()
        cur = prices.drop_duplicates("entity_id").set_index("entity_id")["current_symbol"]
        not_today = sum(cur[e] not in today for e in ids)
        stopped = sum(last[e] < end - pd.Timedelta(days=30) for e in ids)
        lines.append(f"  {year}: {len(ids)} stocks ever in universe; {not_today} not in today's data/technical; "
                     f"{stopped} stopped trading before {end.date()}")

    text = "\n".join(lines)
    print(text)
    with open(f"{OUT}/summary.txt", "w", encoding="utf-8") as fh:
        fh.write(text + "\n")


if __name__ == "__main__":
    main()
