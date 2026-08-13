"""
Falcon — Backtest Run Script
Run from project root: python tests/run_backtest.py

Flip ENABLE_MICROSTRUCTURE_SIGNALS below to True to include the
liquidity-sweep/FVG confidence-score bonuses (see
decision_engine/leadership_decision_engine.py's own docstring); leave it
False to reproduce every prior backtest run's exact behavior.
"""
import sys, glob, os
sys.path.insert(0, ".")

import pandas as pd
from datetime import date, timedelta
from backtesting.backtest_runner import run_backtest, print_backtest_summary, populate_sector_cache
from backtesting.detector_funnel import print_detector_funnel
from scoring.benchmark import get_benchmark_history
from scoring.market_regime import get_vix_history
from scoring.sector_map import sector_map
from tests.backfill_rs_macd import _fetch_sector_index_history_chunked

ENABLE_MICROSTRUCTURE_SIGNALS = False

# A-1 (2.5): fraction of AVOID decisions to record with a hypothetical
# forward outcome. 1.0 records every one -- drop to e.g. 0.3 if AVOID
# volume turns out to swamp runtime (AVOID is typically the largest
# category). See run_backtest()'s own docstring for what sampled_avoid
# means downstream.
AVOID_SAMPLE_RATE = 1.0

# Universe widening: "existing_cache" (default) leaves data/technical/
# exactly as-is, same behavior every prior run used. "wide" ensures the
# full Nifty 500 constituent list (backtesting/universe_builder.py's
# build_wide_backtest_universe()) is cached before loading -- ~500
# tickers vs. the prior ~185. Idempotent either way: once everything's
# cached, flipping this back and forth costs nothing (see
# ensure_wide_universe_cached()'s own docstring for why the delta
# check is cheap on a second call).
UNIVERSE_MODE = "wide"  # or "existing_cache"

if UNIVERSE_MODE == "wide":
    from tests.prepare_wide_universe import ensure_wide_universe_cached
    print("Universe mode: wide -- ensuring the full Nifty 500 list is cached first...")
    ensure_wide_universe_cached()
    print()

# ── 1. Load universe from whatever is in data/technical/ ──────────────────────
print("Loading universe from data/technical/...")

universe_histories = {}
skipped = []

for path in sorted(glob.glob("data/technical/*.parquet")):
    ticker = os.path.basename(path).replace(".parquet", "")
    try:
        df = pd.read_parquet(path)
        df["Date"] = pd.to_datetime(df["Date"])
        # Defensive: start_date/end_date below are tz-naive Timestamps: a
        # tz-aware Date column crashes _sampled_dates_for_ticker()'s
        # comparison outright rather than silently misbehaving (confirmed
        # the hard way -- ^NSEI briefly ended up in data/technical/ with a
        # tz-aware Date column and crashed the very first widened-universe
        # run). Every ticker actually meant to be here should already be
        # tz-naive; this just makes that an enforced invariant instead of
        # an assumption.
        if df["Date"].dt.tz is not None:
            df["Date"] = df["Date"].dt.tz_localize(None)
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
# the VIX fetch above. CHUNKED (not a single big request): confirmed live
# during the Phase 4 RS_Rating/MACD backfill that get_sector_index_history()
# silently truncates EVERY request, regardless of requested span, to
# ~100 calendar days from its own from_date (see scoring/sector_indices.py's
# corrected module docstring) -- a single 4-year request here would badly
# truncate RS_Rating's sector-index input for most of this replay's own
# window, which the new categorize() now depends on directly (RS_Rating is
# one of the frozen model's own fitted features, not just a compute_score()
# input as before Phase 4.6). ─────────────────────────────────────────────
print("\nLoading sector index histories (chunked)...")
distinct_sectors = {sector_map.get_sector(ticker) for ticker in universe_histories}
sector_index_histories = {}
for sector in distinct_sectors:
    history = _fetch_sector_index_history_chunked(sector, start, end)
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
print(f"Microstructure signals (liquidity sweep + FVG): {'ON' if ENABLE_MICROSTRUCTURE_SIGNALS else 'off'}")
print("\nStarting backtest — progress + a computed time-remaining estimate "
      "will be logged every 10 sampled dates. Go make chai. ☕")

# ── 5. Run ─────────────────────────────────────────────────────────────────────
funnel_counts: dict = {}
trades = run_backtest(
    universe_histories=universe_histories,
    benchmark_history=benchmark_history,
    vix_history=vix_history,
    start_date=start_date,
    end_date=end_date,
    sample_every_n_days=5,
    sector_index_histories=sector_index_histories,
    enable_microstructure_signals=ENABLE_MICROSTRUCTURE_SIGNALS,
    funnel_counts=funnel_counts,
    avoid_sample_rate=AVOID_SAMPLE_RATE,
)

# ── 6. Save raw results ────────────────────────────────────────────────────────
# Phase 4.6: this script now runs through the NEW production categorize()
# (calibrated model, no hard regime/sector ceiling) -- output path changed
# from run #3's own filename so this run's results land in a new file
# rather than silently overwriting run #3's historical data. Run #3 stays
# on disk as historical context; this becomes the new canonical baseline.
output_path = (
    "data/backtest_results_run4_calibrated_model.csv" if UNIVERSE_MODE == "wide" else "data/backtest_results.csv"
)
trades.to_csv(output_path, index=False)
print(f"\nRaw trade log saved → {output_path}  ({len(trades)} trades)")

# ── 6b. Detector funnel diagnostics (A-4) ──────────────────────────────────────
print_detector_funnel(funnel_counts)

# ── 7. Print summary ───────────────────────────────────────────────────────────
print_backtest_summary(trades)
