"""
Falcon -- the PIT dataset rebuilt on the extended bhavcopy file (2000-01-03 -> latest),
written to a separate folder so every stored result keeps using data/pit/.

    python tests/build_pit_v2.py [bhavcopy parquet] [out dir]

Defaults: data/bhavcopy_v2/bhavcopy_equity.parquet -> data/pit_v2/. Same rules as
tests/build_pit_universe.py (market_data/pit_universe.py); corporate-action sources are
every file below that exists; symbol changes use the newest list available.
"""
import sys
sys.path.insert(0, ".")

import os

import numpy as np
import pandas as pd

from market_data.pit_universe import build_adjusted_prices, load_symbol_changes, monthly_universe, primary_rows

ACTIONS = [
    "data/pit_sources/corporate_actions_2000_2004.parquet",
    "data/pit_sources/corporate_actions_2005_2015.parquet",
    "data/corporate_actions_cache.parquet",
    "data/pit_sources/corporate_actions_2026_recent.parquet",
]
CHANGES = ["data/pit_sources/symbol_changes_2026_11.csv", "data/pit_sources/symbol_changes.csv"]


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "data/bhavcopy_v2/bhavcopy_equity.parquet"
    out = sys.argv[2] if len(sys.argv) > 2 else "data/pit_v2"
    os.makedirs(out, exist_ok=True)
    bhav = pd.read_parquet(src, columns=["Date", "Symbol", "ISIN", "Series", "Open", "High", "Low", "Close",
                                         "PrevClose", "Volume", "Turnover"])
    bhav["Date"] = pd.to_datetime(bhav["Date"])
    bhav = bhav[bhav["Series"].isin(["EQ", "BE", "BZ", "BL", "SM", "ST"])]
    lines = [f"bhavcopy rows {len(bhav):,}, {bhav['Date'].nunique()} sessions, {bhav['Date'].min().date()} -> {bhav['Date'].max().date()}"]
    used = [p for p in ACTIONS if os.path.exists(p)]
    actions = pd.concat([pd.read_parquet(p) for p in used], ignore_index=True)
    actions["exDate"] = pd.to_datetime(actions["exDate"], errors="coerce", dayfirst=True)
    actions = actions.drop_duplicates(subset=[c for c in ("symbol", "subject", "exDate") if c in actions.columns])
    lines.append(f"corporate-action files: {used}")
    lines.append(f"corporate-action records {len(actions):,} ({actions['exDate'].min().date()} -> {actions['exDate'].max().date()})")
    cp = next((p for p in CHANGES if os.path.exists(p)), None)
    changes = load_symbol_changes(cp) if cp else None
    lines.append(f"symbol changes: {cp} ({len(changes) if changes else 0} records)")
    universe = monthly_universe(primary_rows(bhav, changes))
    prices, adjustments = build_adjusted_prices(bhav, actions, infer_for=set(universe["entity_id"]), symbol_changes=changes,
                                                early_tolerance=0.10, early_close_tolerance=0.15)   # pre-2006 only, see docs/history_2001_2006_preregistration.md
    prices.to_parquet(f"{out}/prices_adjusted.parquet", index=False)
    adjustments.to_csv(f"{out}/adjustments.csv", index=False)
    universe.to_parquet(f"{out}/universe_monthly.parquet", index=False)
    inferred = adjustments["subject"].astype(str).str.startswith("INFERRED") if len(adjustments) else pd.Series([], dtype=bool)
    lines.append(f"entities {prices['entity_id'].nunique():,}; adjustments {len(adjustments):,} ({int(inferred.sum())} inferred)")
    lines.append(f"monthly universes {universe['month_end'].nunique()} ({universe['month_end'].min().date()} -> {universe['month_end'].max().date()})")
    p = prices[["entity_id", "Date", "Symbol", "Close"]].sort_values(["entity_id", "Date"])
    p["move"] = p.groupby("entity_id")["Close"].pct_change()
    p = p[p["move"].abs() > 0.4]
    ends = np.sort(universe["month_end"].unique())
    k = ends.searchsorted(p["Date"].to_numpy(), side="right") - 1
    p = p[k >= 0].assign(month_end=ends[k[k >= 0]])
    big = p.merge(universe[["month_end", "entity_id"]], on=["month_end", "entity_id"])
    big.to_csv(f"{out}/big_moves_in_universe.csv", index=False)
    by_year = big.groupby(big["Date"].dt.year).size().to_dict()
    lines.append(f"one-day moves > 40% while in the universe: {len(big)}; by year {by_year}")
    text = "\n".join(lines)
    print(text)
    with open(f"{out}/summary.txt", "w", encoding="utf-8") as fh:
        fh.write(text + "\n")


if __name__ == "__main__":
    main()
