"""
Falcon — Corruption Exposure Re-check at Phase-4 Scale
Run from project root: python tests/check_corruption_exposure_phase4.py

docs/known_data_issues.md item #1 (the ~34-ticker corruption issue) was
verified clean for run #3's 459 traded episodes, but explicitly flagged
as NOT yet re-verified at Phase 4's actual read scale: "Phase 4's
feature-fitting process ... will read the full ~496-ticker universe
across the full tuning split, not just the traded subset." The document's
own resolution path (a): "re-run the same style of exposure check
(tests/check_corruption_exposure.py's methodology, generalized from 'the
459 traded rows' to 'every (ticker, date) the tuning-split feature-fit
actually reads')".

This script does exactly that -- reusing check_1_lookback_exposure() and
check_2_cross_sectional_exposure() from tests/check_corruption_exposure.py
UNCHANGED (the real production logic, not a reimplementation), but
pointed at the 265-row fitting-set population (excluded_insufficient_history
already dropped, both tuning AND validation splits -- 78 distinct dates)
instead of run #3's full 459-row/101-date population. This is the exact
(ticker, date) population tests/backfill_rs_macd.py actually read when it
called build_scored_universe_as_of() to compute RS_Rating -- both splits,
since that backfill covered the whole fitting set, not tuning alone.
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

EPISODE_LOG_PATH = "data/run3_episodes_with_v2_features.csv"


def main():
    log = pd.read_csv(EPISODE_LOG_PATH, low_memory=False)
    log["episode_start_date"] = pd.to_datetime(log["episode_start_date"])

    real = log[log["category"].isin(["EXECUTE", "ALERT_WATCHLIST"])].copy()
    fitting_set = real[~real["excluded_insufficient_history"]].copy()
    # check_1/check_2 expect an "entry_date" column (same shape as run #3's
    # raw trade log) -- fitting_set's own timestamp column is
    # episode_start_date, so rename onto a matching frame rather than
    # touch the shared check functions.
    fitting_trades = fitting_set.rename(columns={"episode_start_date": "entry_date"})[["ticker", "entry_date"]].copy()
    print(f"Phase-4 fitting-set population: {len(fitting_trades)} rows, "
          f"{fitting_trades['entry_date'].nunique()} distinct entry dates "
          f"(tuning + validation splits combined -- the exact population "
          f"backfill_rs_macd.py read).")

    universe = _load_universe()
    print(f"Universe loaded: {len(universe)} tickers")

    corporate_actions = fetch_all_corporate_actions(from_date=dt.date(2016, 1, 1), to_date=dt.date.today())
    corrupted = _corrupted_dates_map(universe, corporate_actions)
    print(f"Tickers with unconfirmed (corrupted) dates: {len(corrupted)}")

    print("\n" + "=" * 78)
    print("  CHECK 1 -- OWN-TICKER INDICATOR/RS LOOKBACK EXPOSURE (Phase-4 scale)")
    print("=" * 78)
    check1 = check_1_lookback_exposure(fitting_trades, universe, corrupted)
    print(f"Fitting-set rows whose entry-date lookback window touches their own corrupted date: "
          f"{len(check1)} of {len(fitting_trades)}")
    if not check1.empty:
        print(check1.to_string(index=False))

    print("\n" + "=" * 78)
    print("  CHECK 2 -- CROSS-SECTIONAL RS PERCENTILE-RANK EXPOSURE (Phase-4 scale)")
    print("=" * 78)
    check2 = check_2_cross_sectional_exposure(fitting_trades, universe, corrupted)
    if check2.empty:
        print("No fitting-set ticker's percentile rank was computable on any date with a distorting ticker present.")
    else:
        print(f"Fitting-set ticker/date rows checked: {len(check2)}")
        print(f"Max |delta| (percentile points): {check2['delta'].abs().max()}")
        print(f"Rows with any delta != 0: {(check2['delta'] != 0).sum()}")
        meaningful = check2[check2["delta"].abs() >= 3]
        print(f"Rows with |delta| >= 3 percentile points: {len(meaningful)}")
        if not meaningful.empty:
            print(meaningful.to_string(index=False))
        else:
            print(check2[check2["delta"] != 0].to_string(index=False) if (check2["delta"] != 0).any() else "  (all deltas exactly 0)")

    check1.to_csv("data/corruption_check_phase4_scale_check1.csv", index=False)
    check2.to_csv("data/corruption_check_phase4_scale_check2.csv", index=False)
    print(f"\n{'=' * 78}")
    print("Saved -> data/corruption_check_phase4_scale_check1.csv, data/corruption_check_phase4_scale_check2.csv")


if __name__ == "__main__":
    main()
