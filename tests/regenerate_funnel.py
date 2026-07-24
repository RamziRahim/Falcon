"""
Falcon — Detector Funnel Regeneration (corrected run #2)
Run from project root: python tests/regenerate_funnel.py

Regenerates the detector funnel diagnostic (backtesting/detector_funnel.py,
A-4) against every (ticker, entry_date) evaluation in
data/backtest_results_run2_corrected.csv -- run #2's original funnel
output was only ever printed to the stdout of that ~11-hour background
run, never written to disk, so there's nothing to diff against; this
regenerates it fresh from the same cached data/technical/*.parquet
histories the salvage script used.

Detection-only per (ticker, date) -- same as tests/salvage_run2.py's
_reprice(), NOT a full replay (no universe-wide RS/sector scoring,
which the funnel doesn't depend on). Still ~17k detection passes
(indicator recompute + all 5 detectors), which is the genuinely
unavoidable cost here -- empirically ~0.5s/row, so a couple of hours,
not the original run's ~11.
"""
import sys
import time
sys.path.insert(0, ".")

import pandas as pd

from technical_analysis.indicator_calculator import indicator_calculator
from technical_analysis.pattern_engine import analyze_ticker
from scoring.relative_volume import calculate as calculate_relative_volume
from backtesting.detector_funnel import build_detector_funnel, tally_funnel, funnel_counts_to_dataframe, print_detector_funnel

CORRECTED_PATH = "data/backtest_results_run2_corrected.csv"
OUTPUT_PATH = "data/detector_funnel_run2_corrected.csv"
CHECKPOINT_EVERY = 1000


def _truncate(df: pd.DataFrame, as_of_date: pd.Timestamp) -> pd.DataFrame:
    ordered = df.sort_values("Date").reset_index(drop=True)
    return ordered[ordered["Date"] <= as_of_date].reset_index(drop=True)


def _load_history(ticker: str) -> pd.DataFrame:
    df = pd.read_parquet(f"data/technical/{ticker}.parquet")
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values("Date").reset_index(drop=True)


def main():
    trades = pd.read_csv(CORRECTED_PATH)
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    print(f"Total (ticker, entry_date) evaluations: {len(trades)}")

    history_cache: dict = {}
    funnel_counts: dict = {}
    skipped_no_data = 0
    t0 = time.time()

    for n, (_, row) in enumerate(trades.iterrows(), start=1):
        ticker, entry_date = row["ticker"], row["entry_date"]

        if ticker not in history_cache:
            history_cache[ticker] = _load_history(ticker)
        truncated = _truncate(history_cache[ticker], entry_date)

        if len(truncated) < 20:
            skipped_no_data += 1
            continue

        enriched = indicator_calculator.calculate(truncated)
        enriched = calculate_relative_volume(enriched)
        analysis = analyze_ticker(enriched)
        tally_funnel(funnel_counts, build_detector_funnel(analysis))

        if n % CHECKPOINT_EVERY == 0 or n == len(trades):
            elapsed = time.time() - t0
            rate = n / elapsed
            remaining = (len(trades) - n) / rate if rate > 0 else 0
            print(f"  {n}/{len(trades)} ({elapsed/60:.1f} min elapsed, "
                  f"~{remaining/60:.1f} min remaining)")
            funnel_counts_to_dataframe(funnel_counts).to_csv(OUTPUT_PATH, index=False)

    print(f"\nSkipped (insufficient truncated history): {skipped_no_data}")
    print_detector_funnel(funnel_counts)

    funnel_counts_to_dataframe(funnel_counts).to_csv(OUTPUT_PATH, index=False)
    print(f"Saved -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
