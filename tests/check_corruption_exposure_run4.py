"""
Falcon — Corruption Exposure Re-check at Run #4 Scale
Run from project root: python tests/check_corruption_exposure_run4.py

Same standing item (docs/known_data_issues.md #1, the ~34-ticker price
corruption) re-verified at a THIRD, larger scale: run #4's own real
(EXECUTE/ALERT_WATCHLIST) episode population -- every ticker/date that
actually fed the +82.74% headline number, not the narrower 265-row
Phase-4 fitting-set population the model was calibrated on. Reuses
check_1_lookback_exposure()/check_2_cross_sectional_exposure() from
tests/check_corruption_exposure.py UNCHANGED (the real production
logic), exactly as tests/check_corruption_exposure_phase4.py already
did for the fitting-set scale -- only the input population changes here.
"""
import sys
sys.path.insert(0, ".")

import datetime as dt

import pandas as pd

from market_data.corporate_actions import fetch_all_corporate_actions
from tests.check_corruption_exposure import (
    _corrupted_dates_map,
    _load_universe,
    check_1_lookback_exposure,
    check_2_cross_sectional_exposure,
)

RUN4_PATH = "data/backtest_results_run4_calibrated_model.csv"


def main():
    trades = pd.read_csv(RUN4_PATH, low_memory=False)
    trades["entry_date"] = pd.to_datetime(trades["entry_date"], format="mixed")

    real_trades = trades[trades["category"].isin(["EXECUTE", "ALERT_WATCHLIST"])][["ticker", "entry_date"]].copy()
    print(f"Run #4 real-trade population: {len(real_trades)} rows, "
          f"{real_trades['entry_date'].nunique()} distinct entry dates "
          f"(every EXECUTE/ALERT_WATCHLIST signal the new categorize() produced -- the full population "
          f"feeding both portfolio-sim readings, not just the 59 taken EXECUTE episodes).")

    universe = _load_universe()
    print(f"Universe loaded: {len(universe)} tickers")

    corporate_actions = fetch_all_corporate_actions(from_date=dt.date(2016, 1, 1), to_date=dt.date.today())
    corrupted = _corrupted_dates_map(universe, corporate_actions)
    print(f"Tickers with unconfirmed (corrupted) dates: {len(corrupted)}")

    print("\n" + "=" * 78)
    print("  CHECK 1 -- OWN-TICKER INDICATOR/RS LOOKBACK EXPOSURE (run #4 scale)")
    print("=" * 78)
    check1 = check_1_lookback_exposure(real_trades, universe, corrupted)
    print(f"Real-trade rows whose entry-date lookback window touches their own corrupted date: "
          f"{len(check1)} of {len(real_trades)}")
    if not check1.empty:
        print(check1.to_string(index=False))

    print("\n" + "=" * 78)
    print("  CHECK 2 -- CROSS-SECTIONAL RS PERCENTILE-RANK EXPOSURE (run #4 scale)")
    print("=" * 78)
    check2 = check_2_cross_sectional_exposure(real_trades, universe, corrupted)
    if check2.empty:
        print("No real-trade ticker's percentile rank was computable on any date with a distorting ticker present.")
    else:
        print(f"Real-trade ticker/date rows checked: {len(check2)}")
        print(f"Max |delta| (percentile points): {check2['delta'].abs().max()}")
        print(f"Rows with any delta != 0: {(check2['delta'] != 0).sum()}")
        meaningful = check2[check2["delta"].abs() >= 3]
        print(f"Rows with |delta| >= 3 percentile points: {len(meaningful)}")
        if not meaningful.empty:
            print(meaningful.to_string(index=False))

    check1.to_csv("data/corruption_check_run4_scale_check1.csv", index=False)
    check2.to_csv("data/corruption_check_run4_scale_check2.csv", index=False)
    print(f"\n{'=' * 78}")
    print("Saved -> data/corruption_check_run4_scale_check1.csv, data/corruption_check_run4_scale_check2.csv")


if __name__ == "__main__":
    main()
