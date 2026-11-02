"""
Falcon -- technical indicators on the survivorship-free adjusted prices.

    python tests/build_pit_technicals.py

For every stock that was ever in a monthly top-500 universe, computes the
same indicator set the live app uses (technical_analysis.indicator_calculator:
SMA/EMA 20/50/150/200, RSI 14, MACD, ATR 14, ADX/DI 14, OBV, Bollinger 20,2)
on its split/bonus-adjusted daily prices, plus:
  Turnover        traded value that day (rupees)
  Symbol          the symbol the stock traded under THAT day
  in_universe     True if the stock was in the latest month-end universe on or before that day

All indicators are trailing (no look-ahead). Prices are backward-adjusted, so
absolute price LEVELS before a split are not what traded that day (ratios,
returns and indicators are unaffected) -- don't use a fixed rupee price
filter on old dates.

Writes data/pit/technicals.parquet (indicator columns as float32).
"""
import sys
sys.path.insert(0, ".")

import time

import numpy as np
import pandas as pd

from technical_analysis.indicator_calculator import indicator_calculator

PRICES = "data/pit/prices_adjusted.parquet"
UNIVERSE = "data/pit/universe_monthly.parquet"
OUT = "data/pit/technicals.parquet"
KEEP_FLOAT64 = {"Open", "High", "Low", "Close", "Volume", "Turnover"}


def main():
    prices = pd.read_parquet(PRICES)
    universe = pd.read_parquet(UNIVERSE)
    ever = set(universe["entity_id"])
    members = universe.groupby("entity_id")["month_end"].apply(lambda s: np.sort(s.to_numpy()))
    month_ends = np.sort(universe["month_end"].unique())
    frames, t0 = [], time.time()
    groups = prices[prices["entity_id"].isin(ever)].groupby("entity_id")
    for n, (entity, rows) in enumerate(groups, 1):
        rows = rows.sort_values("Date").reset_index(drop=True)
        base = rows[["Date", "Open", "High", "Low", "Close", "Volume"]].copy()
        ind = indicator_calculator.calculate(base) if len(base) >= 30 else base
        ind["Turnover"] = rows["Turnover"].to_numpy()
        ind["Symbol"] = rows["Symbol"].to_numpy()
        ind["entity_id"] = entity
        ind["current_symbol"] = rows["current_symbol"].iloc[-1]
        # latest month end on or before each day -> was the stock a member then?
        idx = np.searchsorted(month_ends, rows["Date"].to_numpy(), side="right") - 1
        latest = np.where(idx >= 0, month_ends[np.clip(idx, 0, None)], np.datetime64("NaT"))
        ind["in_universe"] = np.isin(latest, members.get(entity, np.array([], dtype=month_ends.dtype)))
        for col in ind.columns:
            if col not in KEEP_FLOAT64 and pd.api.types.is_numeric_dtype(ind[col]) and ind[col].dtype != bool:
                ind[col] = pd.to_numeric(ind[col], errors="coerce").astype("float32")
        frames.append(ind)
        if n % 200 == 0:
            print(f"  {n}/{len(groups)} stocks, {time.time() - t0:.0f}s", flush=True)
    out = pd.concat(frames, ignore_index=True)
    out.to_parquet(OUT, index=False)
    print(f"Saved {OUT}: {out['entity_id'].nunique():,} stocks, {len(out):,} rows, "
          f"{out['Date'].min().date()} -> {out['Date'].max().date()}, columns: {list(out.columns)}")


if __name__ == "__main__":
    main()
