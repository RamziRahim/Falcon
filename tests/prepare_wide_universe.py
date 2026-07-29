"""
Falcon — Wide (Nifty 500) Universe Preparation
Run from project root: python tests/prepare_wide_universe.py

Fetches/caches OHLCV + indicators for the delta between the current
cached universe and the full Nifty 500 constituent list
(backtesting/universe_builder.py's build_wide_backtest_universe()), so
tests/run_backtest.py's existing data/technical/*.parquet glob-loader
picks up the widened universe automatically -- no runner change needed
for that part, it already reads whatever's on disk.

-------------------------------------------------------------------------
Why this does NOT call DataCollectionEngine().run() directly
-------------------------------------------------------------------------
market_data/cache_synchronizer.py's synchronize() DELETES any data/raw
cache entry not present in whatever symbol list is passed to it --
confirmed the hard way earlier this session (a 2-ticker sanity-check call
wiped 41 of 43 raw cache files, including the Nifty 50 benchmark's own
cache, because the candidate list passed was just those 2 tickers, not
the full existing+new set). DataCollectionEngine.run() always routes
through that synchronize() step and is a single blocking call with no
batch/progress hook -- calling it once with the full candidate set would
be safe but a ~40+ minute black box; calling it repeatedly with small
batches would be fast-failing but unsafe (each partial batch would look
like "delete everything else" to synchronize()).

This script instead calls the exact underlying pieces
DataCollectionEngine.run() itself uses -- downloader.download(),
market_data_validator.validate_history(), cache_manager.update() -- in
batches of BATCH_SIZE, bypassing cache_synchronizer.synchronize()
entirely. None of those three has any delete-logic in it at all (the only
destructive code path lives in synchronize()), so this is strictly safer
than a single DataCollectionEngine.run() call, not a shortcut around
its safety, and gives real per-batch checkpointing besides.

The union (existing_cached_symbols | wide_universe) is still computed and
printed below -- not for deletion-safety (nothing here can delete
anything), but because it's what determines to_fetch (candidate_set minus
what's already in data/technical), i.e. what actually needs downloading.

Note: ^NSEI (the Nifty 50 benchmark)'s raw cache was one of the 41 files
accidentally deleted earlier this session. It's deliberately NOT
re-fetched here -- scoring/benchmark.py's get_benchmark_history() already
self-heals it (checks cache_manager.exists() and refetches on its own
next call), and ^NSEI isn't a Nifty 500 constituent so it wouldn't
naturally appear in this candidate set anyway.
"""
import sys
import time
sys.path.insert(0, ".")

import glob
import os

from backtesting.universe_builder import build_wide_backtest_universe
from config import NIFTY50
from market_data.cache_manager import cache_manager
from market_data.downloader import downloader
from market_data.data_validator import market_data_validator
from technical_analysis.indicator_engine import IndicatorEngine

BATCH_SIZE = 25

# scoring/benchmark.py's get_benchmark_history() manages NIFTY50's (^NSEI)
# own raw cache independently (self-heals on its own next call) -- it is
# NOT a tradeable ticker and must never end up in data/technical/ as if
# it were one. existing_raw (cache_manager.list_symbols()) reads
# data/raw/*.parquet indiscriminately and WILL include it whenever the
# benchmark's own cache happens to already exist there, which pulled it
# into a real run's candidate set once already: it got downloaded via the
# generic equity provider path (not get_benchmark_history()'s own
# tz-naive-normalized fetch), came back tz-AWARE, and crashed
# backtest_runner.py's date-range comparison against every real (tz-naive)
# ticker the first time run_backtest() ran against the widened universe.
_NON_EQUITY_SYMBOLS = {NIFTY50}


def _existing_technical_symbols() -> set[str]:
    return {os.path.basename(p).replace(".parquet", "") for p in glob.glob("data/technical/*.parquet")}


def ensure_wide_universe_cached(batch_size: int = BATCH_SIZE, verbose: bool = True) -> dict:
    """Fetches/caches OHLCV + indicators for whatever's missing from the
    full Nifty 500 constituent list -- see module docstring for the full
    reasoning (why this bypasses DataCollectionEngine.run() entirely).
    Idempotent and cheap to call when nothing's missing: to_fetch is
    computed fresh each call, so a second call after everything's already
    cached just does the two list-fetches (nselib/nsearchives CSVs) and
    returns immediately, no network calls for OHLCV at all.

    Importable so tests/run_backtest.py can call it directly as an
    opt-in universe-widening step, not just as this module's standalone
    script -- same function either way, never two implementations of the
    same fetch logic.

    Returns
    -------
    dict : {"to_fetch": int, "downloaded": int, "failed": int,
    "failed_symbols": list[(symbol, reason)], "technical_count_before": int,
    "technical_count_after": int}
    """
    existing_raw = set(cache_manager.list_symbols()) - _NON_EQUITY_SYMBOLS  # currently in data/raw
    existing_technical = _existing_technical_symbols()          # currently in data/technical
    wide_universe = set(build_wide_backtest_universe())         # Nifty 500, alphabetical

    existing_cached_symbols = existing_raw | existing_technical
    candidate_set = sorted((existing_cached_symbols | wide_universe) - _NON_EQUITY_SYMBOLS)

    # Only what's missing from data/technical needs fetching -- anything
    # already there is left alone (not re-downloaded, not recomputed).
    to_fetch = [s for s in candidate_set if s not in existing_technical]

    if verbose:
        print(f"existing_raw:            {len(existing_raw)}")
        print(f"existing_technical:      {len(existing_technical)}")
        print(f"existing_cached (union): {len(existing_cached_symbols)}")
        print(f"wide_universe (Nifty500):{len(wide_universe)}")
        print(f"candidate_set total:     {len(candidate_set)}  (existing_cached_symbols | wide_universe)")
        print(f"to_fetch (new only):     {len(to_fetch)}  (candidate_set - existing_technical)")
        print()

    downloaded, failed = 0, 0
    failed_symbols: list[tuple[str, str]] = []
    t0 = time.time()

    for batch_start in range(0, len(to_fetch), batch_size):
        batch = to_fetch[batch_start:batch_start + batch_size]
        datasets = downloader.download(batch)

        for symbol in batch:
            if symbol not in datasets:
                failed += 1
                failed_symbols.append((symbol, "no data returned (delisted, bad symbol, or rate-limited)"))
                continue

            dataframe = datasets[symbol]
            validation = market_data_validator.validate_history(dataframe)
            if not validation.valid:
                failed += 1
                failed_symbols.append((symbol, f"validation failed: {validation.errors}"))
                continue

            cache_manager.update(symbol, dataframe)
            downloaded += 1

        indicator_result = IndicatorEngine().run(symbols=batch)

        if verbose:
            done = batch_start + len(batch)
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0
            remaining = (len(to_fetch) - done) / rate if rate > 0 else 0
            print(
                f"  [{done}/{len(to_fetch)}] downloaded={downloaded} failed={failed} "
                f"indicator_processed={indicator_result.processed} indicator_skipped={indicator_result.skipped} "
                f"-- {elapsed/60:.1f} min elapsed, ~{remaining/60:.1f} min remaining"
            )

    final_technical_count = len(glob.glob("data/technical/*.parquet"))

    if verbose:
        print(f"\n{'=' * 78}")
        print(f"Total requested (to_fetch):  {len(to_fetch)}")
        print(f"Successfully fetched+cached: {downloaded}")
        print(f"Failed:                      {failed}")
        if failed_symbols:
            print("Failures:")
            for symbol, reason in failed_symbols:
                print(f"  {symbol}: {reason}")
        print(f"\ndata/technical/ count: {len(existing_technical)} -> {final_technical_count}")
        print(f"{'=' * 78}")

    return {
        "to_fetch": len(to_fetch),
        "downloaded": downloaded,
        "failed": failed,
        "failed_symbols": failed_symbols,
        "technical_count_before": len(existing_technical),
        "technical_count_after": final_technical_count,
    }


if __name__ == "__main__":
    ensure_wide_universe_cached()
