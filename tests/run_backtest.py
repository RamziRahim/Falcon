"""
Falcon — Backtest Run Script
Run from project root: python tests/run_backtest.py
"""
import sys, glob, os
sys.path.insert(0, ".")

import pandas as pd
from datetime import date, timedelta
from backtesting.backtest_runner import run_backtest, print_backtest_summary, populate_sector_cache
from scoring.benchmark import get_benchmark_history
from scoring.market_regime import get_vix_history
from scoring.sector_map import sector_map
from scoring.sector_indices import get_sector_index_history

# ── 1. Load universe from whatever is in data/technical/ ──────────────────────
print("Loading universe from data/technical/...")

universe_histories = {}
skipped = []

for path in sorted(glob.glob("data/technical/*.parquet")):
    ticker = os.path.basename(path).replace(".parquet", "")
    try:
        df = pd.read_parquet(path)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date").reset_index(drop=True)
        if len(df) >= 250:  # need enough history for the 2-year window + pattern lookback
            universe_histories[ticker] = df
        else:
            skipped.append(ticker)
    except Exception as ex:
        skipped.append(ticker)
        print(f"  Could not load {ticker}: {ex}")

print(f"  Loaded: {len(universe_histories)} tickers")
if skipped:
    print(f"  Skipped (too short): {skipped}")

# ── 1b. Populate the sector cache before any lookups happen in the replay
# loop -- without this, every sector lookup would silently return
# "Unknown" on its first (uncached) call within this run. ────────────────
print("\nPopulating sector cache...")
populate_sector_cache(list(universe_histories.keys()))

# ── 2. Load benchmark (NIFTY 50) history ──────────────────────────────────────
print("\nLoading benchmark history...")
benchmark_history = get_benchmark_history()
benchmark_history["Date"] = pd.to_datetime(
    benchmark_history["Date"] if "Date" in benchmark_history.columns else benchmark_history.index
).dt.tz_localize(None)
print(f"  Benchmark rows: {len(benchmark_history)}")

# ── 3. Load VIX history ────────────────────────────────────────────────────────
print("\nLoading VIX history...")
end = date.today()
start = end - timedelta(days=365 * 4)
vix_history = get_vix_history(
    from_date=start.strftime("%d-%m-%Y"),
    to_date=end.strftime("%d-%m-%Y"),
)
if vix_history is not None and not vix_history.empty:
    date_col = [c for c in vix_history.columns if "date" in c.lower() or "timestamp" in c.lower()]
    if date_col:
        vix_history[date_col[0]] = pd.to_datetime(vix_history[date_col[0]]).dt.tz_localize(None)
print(f"  VIX rows: {len(vix_history) if vix_history is not None else 0}")

# ── 3b. Load real sector index histories -- one fetch per distinct sector
# actually present in the universe (sector cache is warm from step 1b, so
# these lookups don't hit the network), reusing the same 4-year buffer as
# the VIX fetch above. ─────────────────────────────────────────────────────
print("\nLoading sector index histories...")
distinct_sectors = {sector_map.get_sector(ticker) for ticker in universe_histories}
sector_index_histories = {}
for sector in distinct_sectors:
    history = get_sector_index_history(
        sector, from_date=start.strftime("%d-%m-%Y"), to_date=end.strftime("%d-%m-%Y"),
    )
    if history is not None:
        sector_index_histories[sector] = history
print(f"  Sector indices resolved: {len(sector_index_histories)}/{len(distinct_sectors)} "
      f"({sorted(distinct_sectors - sector_index_histories.keys())} unmapped or fetch failed)")

# ── 4. Define the 2-year test window ──────────────────────────────────────────
end_date   = pd.Timestamp(date.today())
start_date = pd.Timestamp(date.today() - timedelta(days=365 * 2))
print(f"\nTest window: {start_date.date()} → {end_date.date()}")
print(f"Universe:    {len(universe_histories)} tickers")
print(f"Sampling:    every 5 trading days")
print("\nStarting backtest — this will take ~70 minutes. Go make chai. ☕")

# ── 5. Run ─────────────────────────────────────────────────────────────────────
trades = run_backtest(
    universe_histories=universe_histories,
    benchmark_history=benchmark_history,
    vix_history=vix_history,
    start_date=start_date,
    end_date=end_date,
    sample_every_n_days=5,
    sector_index_histories=sector_index_histories,
)

# ── 6. Save raw results ────────────────────────────────────────────────────────
output_path = "data/backtest_results.csv"
trades.to_csv(output_path, index=False)
print(f"\nRaw trade log saved → {output_path}  ({len(trades)} trades)")

# ── 7. Print summary ───────────────────────────────────────────────────────────
print_backtest_summary(trades)
