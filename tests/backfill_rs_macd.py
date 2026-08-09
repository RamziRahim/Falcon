"""
Falcon — RS_Rating/MACD Backfill onto the v2 Episode Log
Run from project root: python tests/backfill_rs_macd.py

Persists the two spec-required inputs (docs/FALCON_V2_REDESIGN.md
section 5: "these features + regime + sector + RS + MACD") that were
never in run #3's trade-record schema at all -- scoped and approved
separately from Phase 4.1-4.3's own backfill.

RS_Rating: reuses backtesting/replay_engine.py's own
build_scored_universe_as_of() directly -- the exact function the live
replay itself called, not a reimplementation -- once per DISTINCT entry
date across the fitting set (78 dates, not 265; many episodes share a
sampled date), truncating the full universe/benchmark/sector-index
histories internally exactly as the replay did. Needs live sector index
history (no local cache exists), fetched once per distinct sector (11)
up front, same as tests/run_backtest.py's own step 3b. NOT a full replay
re-run -- no pattern detection, no categorize() call, just the
universe-wide RS/sector-ranking step build_scored_universe_as_of() does
on its own.

MACD signal: technical_analysis/pattern_system/macd_signal.py's
get_macd_signal(), a pure per-ticker function needing only the truncated
own-history dataframe (MACD_Hist is already a persisted column in every
data/technical/*.parquet file) -- confirmed trivial, no network, same
per-episode truncation Phase 4.3's own backfill already does.
"""
import sys
sys.path.insert(0, ".")

import glob
import os
from datetime import date, timedelta

import pandas as pd

from backtesting.backtest_runner import populate_sector_cache
from backtesting.replay_engine import build_scored_universe_as_of
from scoring.benchmark import get_benchmark_history
from scoring.sector_indices import get_sector_index_history
from scoring.sector_map import sector_map
from technical_analysis.pattern_system.macd_signal import get_macd_signal

EPISODE_LOG_PATH = "data/run3_episodes_with_v2_features.csv"

# CONFIRMED REAL LIMITATION (live-tested, see scoring/sector_indices.py's
# own docstring for the earlier, looser version of this finding):
# capital_market.index_data() silently caps EVERY single request -- 60-day,
# 365-day, or 4-year -- at ~70 rows / ~100 calendar days measured from its
# OWN from_date, regardless of the requested span, with no exception raised.
# A naive single 4-year request or even a single 365-day request both
# silently truncated to the same stale window. Verified live: 85-day
# chunks, fetched sequentially and concatenated/deduped by Date, produce
# gap-free coverage (785 rows over ~3.17 years for NIFTY IT, zero gaps
# wider than a long weekend) all the way through "today". Kept well under
# the ~100-day observed cap for safety margin.
SECTOR_INDEX_CHUNK_DAYS = 85


def _fetch_sector_index_history_chunked(sector: str, start: date, end: date) -> pd.DataFrame | None:
    frames = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=SECTOR_INDEX_CHUNK_DAYS), end)
        chunk = get_sector_index_history(
            sector, from_date=cursor.strftime("%d-%m-%Y"), to_date=chunk_end.strftime("%d-%m-%Y"),
        )
        if chunk is not None and not chunk.empty:
            frames.append(chunk)
        cursor = chunk_end + timedelta(days=1)
    if not frames:
        return None
    return (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(subset="Date")
        .sort_values("Date")
        .reset_index(drop=True)
    )


def _load_universe() -> dict[str, pd.DataFrame]:
    universe = {}
    for path in sorted(glob.glob("data/technical/*.parquet")):
        ticker = os.path.basename(path).replace(".parquet", "")
        df = pd.read_parquet(path)
        df["Date"] = pd.to_datetime(df["Date"])
        if df["Date"].dt.tz is not None:
            df["Date"] = df["Date"].dt.tz_localize(None)
        df = df.sort_values("Date").reset_index(drop=True)
        if len(df) >= 250:
            universe[ticker] = df
    return universe


def main():
    log = pd.read_csv(EPISODE_LOG_PATH, low_memory=False)
    log["episode_start_date"] = pd.to_datetime(log["episode_start_date"])

    real = log[log["category"].isin(["EXECUTE", "ALERT_WATCHLIST"])].copy()
    fitting_set = real[~real["excluded_insufficient_history"]].copy()
    distinct_dates = sorted(fitting_set["episode_start_date"].unique())
    print(f"Fitting-set episodes: {len(fitting_set)}  |  distinct entry dates: {len(distinct_dates)}")

    universe = _load_universe()
    print(f"Universe loaded: {len(universe)} tickers")

    populate_sector_cache(list(universe.keys()))
    distinct_sectors = {sector_map.get_sector(t) for t in universe}
    distinct_sectors.discard("Unknown")
    print(f"Distinct sectors: {sorted(distinct_sectors)}")

    end = date.today()
    # Earliest fitting-set entry date is 2024-07-25 -- start well before that
    # to cover its own 252-trading-day trailing RS lookback plus margin.
    start = date(2023, 6, 1)
    sector_index_histories = {}
    for sector in distinct_sectors:
        history = _fetch_sector_index_history_chunked(sector, start, end)
        if history is not None:
            sector_index_histories[sector] = history
            print(f"  {sector}: {len(history)} rows, {history['Date'].min().date()} -> {history['Date'].max().date()}")
    print(f"Sector indices resolved: {len(sector_index_histories)}/{len(distinct_sectors)}")

    benchmark_history = get_benchmark_history()
    benchmark_history["Date"] = pd.to_datetime(
        benchmark_history["Date"] if "Date" in benchmark_history.columns else benchmark_history.index
    ).dt.tz_localize(None)

    # ---- RS_Rating: once per distinct date, reused across every episode
    # sharing that date. ----
    rs_rating_by_date_ticker: dict[tuple, float] = {}
    for n, as_of_date in enumerate(distinct_dates, start=1):
        _, _, rs_ratings = build_scored_universe_as_of(as_of_date, universe, benchmark_history, sector_index_histories)
        for ticker, value in rs_ratings.items():
            rs_rating_by_date_ticker[(as_of_date, ticker)] = value
        if n % 10 == 0 or n == len(distinct_dates):
            print(f"  RS_Rating: [{n}/{len(distinct_dates)}] dates done")

    # ---- MACD signal: per episode directly, no universe needed. ----
    macd_by_row = {}
    for row in fitting_set.itertuples():
        history = universe.get(row.ticker)
        if history is None:
            macd_by_row[row.Index] = None
            continue
        truncated = history[history["Date"] <= row.episode_start_date]
        macd_by_row[row.Index] = get_macd_signal(truncated) if len(truncated) >= 15 else None

    log["RS_Rating"] = log.apply(
        lambda r: rs_rating_by_date_ticker.get((r["episode_start_date"], r["ticker"])), axis=1,
    )
    log["macd_signal"] = pd.Series(macd_by_row)

    log.to_csv(EPISODE_LOG_PATH, index=False)
    print(f"\nSaved RS_Rating + macd_signal -> {EPISODE_LOG_PATH}")

    coverage = fitting_set.apply(
        lambda r: (r["episode_start_date"], r["ticker"]) in rs_rating_by_date_ticker
        and rs_rating_by_date_ticker[(r["episode_start_date"], r["ticker"])] is not None
        and not pd.isna(rs_rating_by_date_ticker[(r["episode_start_date"], r["ticker"])]),
        axis=1,
    )
    print(f"RS_Rating coverage on fitting set: {coverage.sum()}/{len(fitting_set)}")
    macd_coverage = sum(macd_by_row.get(i) is not None for i in fitting_set.index)
    print(f"macd_signal coverage on fitting set: {macd_coverage}/{len(fitting_set)}")


if __name__ == "__main__":
    main()
