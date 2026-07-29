"""
Falcon — Retroactive Split/Bonus Backward-Adjustment
Run from project root: python tests/apply_split_adjustment.py

Applies market_data/corporate_actions.py's confirm_and_adjust() to every
cached data/technical/*.parquet file -- fixing the unadjusted-price bug
found while building run #3's momentum baseline (see that module's own
docstring for the full story: BAJFINANCE.NS's real ~10x split+bonus on
2025-06-16, NSEProvider has no adjusted-close alternative at all).

Corrects the base OHLCV(+Deliverable_Qty) columns directly --
data/technical/*.parquet already retains them alongside derived
indicators, so no re-fetch from data/raw is needed for any ticker, even
the ~183 that were never raw-cached to begin with. Then re-runs
technical_analysis.indicator_calculator.calculate() on the corrected base
series so every derived indicator (SMA/RSI/MACD/ATR/ADX/Bollinger/OBV) is
consistent with the adjusted prices, not just the raw Close column --
patching Close alone and leaving stale indicator values in place would
just move the inconsistency rather than fix it.

Deliverable_Qty is a share-count quantity like Volume -- scales inversely
with the same factor, same before-event-date mask, per confirmed event.
Delivery_Pct is a ratio of two quantity columns that both scale the same
way, so it's already scale-invariant and is left untouched.
"""
import sys
sys.path.insert(0, ".")

import datetime as dt
import glob
import os

import pandas as pd

from market_data.corporate_actions import confirm_and_adjust, fetch_all_corporate_actions
from technical_analysis.indicator_calculator import indicator_calculator
from technical_analysis.indicator_exporter import indicator_exporter

BASE_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]
PRICE_VOLUME_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def main():
    corporate_actions = fetch_all_corporate_actions(from_date=dt.date(2016, 1, 1), to_date=dt.date.today())
    print(f"Corporate actions loaded: {len(corporate_actions)} market-wide records")

    paths = sorted(glob.glob("data/technical/*.parquet"))
    print(f"Tickers to check: {len(paths)}")

    tickers_corrected: list[str] = []
    total_confirmed_adjustments = 0
    unconfirmed: list[tuple] = []

    for n, path in enumerate(paths, start=1):
        ticker = os.path.basename(path).replace(".parquet", "")
        df = pd.read_parquet(path)
        df["Date"] = pd.to_datetime(df["Date"])
        if df["Date"].dt.tz is not None:
            df["Date"] = df["Date"].dt.tz_localize(None)
        df = df.sort_values("Date").reset_index(drop=True)

        adjusted_base, log = confirm_and_adjust(df[BASE_COLUMNS], ticker, corporate_actions)

        if not log:
            continue

        confirmed_events = [e for e in log if e["confirmed"]]
        for e in log:
            if not e["confirmed"]:
                unconfirmed.append((ticker, str(e["date"].date()), round(e["pct_change"] * 100, 1)))

        if not confirmed_events:
            continue

        corrected = df.copy()
        # Only the numeric columns -- mixing Date (datetime64) into a
        # single .values conversion upcasts the whole block to object
        # dtype, which then fails pandas_ta's numba-compiled SMA/Bollinger
        # calculation (confirmed the hard way: "non-precise type readonly
        # array(pyobject...)"). Date itself is unchanged by
        # confirm_and_adjust() and both frames share the same row order,
        # so it doesn't need reassigning at all.
        corrected[PRICE_VOLUME_COLUMNS] = adjusted_base[PRICE_VOLUME_COLUMNS].values

        if "Deliverable_Qty" in corrected.columns:
            for e in confirmed_events:
                before_mask = corrected["Date"] < e["date"]
                if e["factor"] != 0:
                    corrected.loc[before_mask, "Deliverable_Qty"] = (
                        corrected.loc[before_mask, "Deliverable_Qty"] / e["factor"]
                    ).round()

        recomputed = indicator_calculator.calculate(corrected)
        indicator_exporter.save(ticker, recomputed)

        tickers_corrected.append(ticker)
        total_confirmed_adjustments += len(confirmed_events)

        if n % 50 == 0 or n == len(paths):
            print(f"  [{n}/{len(paths)}] checked, {len(tickers_corrected)} corrected so far...")

    print(f"\n{'=' * 78}")
    print(f"Tickers checked:                              {len(paths)}")
    print(f"Tickers with >=1 confirmed adjustment applied: {len(tickers_corrected)}")
    print(f"Total confirmed adjustments applied:           {total_confirmed_adjustments}")
    print(f"Corrected tickers: {tickers_corrected}")
    print(f"\nUnconfirmed discontinuities remaining (no matching NSE record): {len(unconfirmed)}")
    for u in unconfirmed:
        print(f"  {u}")
    print(f"{'=' * 78}")


if __name__ == "__main__":
    main()
