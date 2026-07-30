"""
Falcon — Corruption Exposure Checks (narrow, targeted, post-processing only)
Run from project root: python tests/check_corruption_exposure.py

Two checks on the ~34 tickers found to have unconfirmed price
discontinuities (market_data/corporate_actions.py's confirm_and_adjust()
correctly left these alone -- no matching NSE corporate action record,
confirmed separately to be real data corruption, e.g. NTPC.NS showing
Rs 10.65/Rs 306 on scattered Jan-2024 days against a real price of
~Rs 1,100-1,300 that month):

1. Lookback-window exposure: for each of run #3's 459 real
   (EXECUTE/ALERT_WATCHLIST) trades, does the TRADED TICKER's own
   indicator lookback (SMA_200/EMA_200, the longest rolling window) or
   RS_Rating point-return reference dates (scoring/relative_strength.py's
   _window_return -- a two-point calculation, not a rolling average: only
   the exact "now" and "window-days-ago" dates matter, not every day
   between) touch one of ITS OWN corrupted dates -- even dates well
   before the trade's own entry.

2. Cross-sectional exposure: at each of the 101 distinct entry dates
   real trades actually used, does excluding any corrupted-and-actually-
   distorted ticker from the RS_Rating ranking population change the
   percentile rank of the ticker that was actually traded that date.
   Uses relative_strength.py's own compute_returns()/percentile_rank()
   directly (the real production functions), not a reimplementation.
"""
import sys
sys.path.insert(0, ".")

import glob
import os

import pandas as pd

from market_data.corporate_actions import detect_discontinuities, fetch_all_corporate_actions, _symbol_actions
from scoring.relative_strength import WINDOW_2M, WINDOW_3M, WINDOW_6M, WINDOW_9M, WINDOW_12M, compute_returns, percentile_rank

RUN3_PATH = "data/backtest_results_run3_wide_universe.csv"
SMA_EMA_LONGEST_WINDOW = 200
RS_WINDOWS = [WINDOW_2M, WINDOW_3M, WINDOW_6M, WINDOW_9M, WINDOW_12M]
RS_WEIGHTS = {"Return_3M": 0.4, "Return_6M": 0.2, "Return_9M": 0.2, "Return_12M": 0.2}


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


def _corrupted_dates_map(universe: dict[str, pd.DataFrame], corporate_actions: pd.DataFrame) -> dict[str, set]:
    corrupted = {}
    for ticker, hist in universe.items():
        discontinuities = detect_discontinuities(hist[["Date", "Close"]], threshold=0.40)
        if discontinuities.empty:
            continue
        symbol_actions = _symbol_actions(corporate_actions, ticker)
        bad_dates = set()
        for _, row in discontinuities.iterrows():
            event_date = pd.Timestamp(row["Date"])
            matches = symbol_actions[
                (symbol_actions["exDate"] >= event_date - pd.Timedelta(days=3))
                & (symbol_actions["exDate"] <= event_date + pd.Timedelta(days=3))
            ]
            if matches.empty:
                bad_dates.add(event_date.date())
        if bad_dates:
            corrupted[ticker] = bad_dates
    return corrupted


def _reference_dates_for_ticker(history: pd.DataFrame, entry_date: pd.Timestamp) -> set:
    """Every date this ticker's OWN indicator/RS calculation actually
    reads at entry_date: the full trailing SMA_200/EMA_200 window (every
    day matters for a rolling average), plus the RS point-return
    reference dates (only these exact two-point positions matter, per
    _window_return's own docstring/implementation)."""
    truncated = history[history["Date"] <= entry_date].sort_values("Date")
    if truncated.empty:
        return set()

    dates = set(truncated["Date"].tail(SMA_EMA_LONGEST_WINDOW).dt.date)
    dates.add(truncated["Date"].iloc[-1].date())  # "now" reference for every RS window

    for window in RS_WINDOWS:
        if len(truncated) > window:
            dates.add(truncated["Date"].iloc[-(window + 1)].date())

    return dates


def check_1_lookback_exposure(real_trades: pd.DataFrame, universe: dict, corrupted: dict) -> pd.DataFrame:
    rows = []
    for row in real_trades.itertuples():
        ticker, entry_date = row.ticker, row.entry_date
        if ticker not in universe or ticker not in corrupted:
            continue
        ref_dates = _reference_dates_for_ticker(universe[ticker], entry_date)
        touched = ref_dates & corrupted[ticker]
        if touched:
            rows.append({"ticker": ticker, "entry_date": entry_date.date(), "touched_dates": sorted(touched)})
    return pd.DataFrame(rows)


def check_2_cross_sectional_exposure(real_trades: pd.DataFrame, universe: dict, corrupted: dict) -> pd.DataFrame:
    rows = []
    distinct_dates = sorted(real_trades["entry_date"].unique())

    for n, entry_date in enumerate(distinct_dates, start=1):
        entry_date = pd.Timestamp(entry_date)
        traded_tickers_today = set(real_trades[real_trades["entry_date"] == entry_date]["ticker"])

        truncated_universe = {
            t: h[h["Date"] <= entry_date] for t, h in universe.items()
            if len(h[h["Date"] <= entry_date]) >= 250
        }
        if not truncated_universe:
            continue

        returns = compute_returns(truncated_universe)
        weighted = sum(returns[col] * w for col, w in RS_WEIGHTS.items())

        distorting = set()
        for ticker in corrupted:
            if ticker not in truncated_universe:
                continue
            ref_dates = _reference_dates_for_ticker(truncated_universe[ticker], entry_date)
            if ref_dates & corrupted[ticker]:
                distorting.add(ticker)

        pct_full = percentile_rank(weighted)
        pct_excl = percentile_rank(weighted.drop(index=[t for t in distorting if t in weighted.index]))

        for ticker in traded_tickers_today:
            if ticker not in pct_full.index:
                continue
            full_rank = pct_full.get(ticker)
            excl_rank = pct_excl.get(ticker)
            if pd.isna(full_rank) or pd.isna(excl_rank):
                continue
            delta = excl_rank - full_rank
            rows.append({
                "entry_date": entry_date.date(), "ticker": ticker,
                "rank_with_corrupted": full_rank, "rank_excluding_distorting": excl_rank,
                "delta": delta, "n_distorting_that_date": len(distorting),
            })

        if n % 25 == 0 or n == len(distinct_dates):
            print(f"  [{n}/{len(distinct_dates)}] entry dates checked...")

    return pd.DataFrame(rows)


def main():
    universe = _load_universe()
    print(f"Universe loaded: {len(universe)} tickers")

    import datetime as dt
    corporate_actions = fetch_all_corporate_actions(from_date=dt.date(2016, 1, 1), to_date=dt.date.today())

    corrupted = _corrupted_dates_map(universe, corporate_actions)
    print(f"Tickers with unconfirmed (corrupted) dates: {len(corrupted)}")

    trades = pd.read_csv(RUN3_PATH, low_memory=False)
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    real_trades = trades[trades["category"].isin(["EXECUTE", "ALERT_WATCHLIST"])].copy()
    print(f"Real trades: {len(real_trades)}, distinct entry dates: {real_trades['entry_date'].nunique()}")

    print("\n" + "=" * 78)
    print("  CHECK 1 -- OWN-TICKER INDICATOR/RS LOOKBACK EXPOSURE")
    print("=" * 78)
    check1 = check_1_lookback_exposure(real_trades, universe, corrupted)
    print(f"Real trades whose entry-date lookback window touches their own corrupted date: {len(check1)} of {len(real_trades)}")
    if not check1.empty:
        print(check1.to_string(index=False))

    print("\n" + "=" * 78)
    print("  CHECK 2 -- CROSS-SECTIONAL RS PERCENTILE-RANK EXPOSURE")
    print("=" * 78)
    check2 = check_2_cross_sectional_exposure(real_trades, universe, corrupted)
    if check2.empty:
        print("No traded ticker's percentile rank was computable on any date with a distorting ticker present.")
    else:
        print(f"Traded-ticker/date rows checked: {len(check2)}")
        print(f"Max |delta| (percentile points): {check2['delta'].abs().max()}")
        print(f"Rows with any delta != 0: {(check2['delta'] != 0).sum()}")
        meaningful = check2[check2["delta"].abs() >= 3]
        print(f"Rows with |delta| >= 3 percentile points: {len(meaningful)}")
        if not meaningful.empty:
            print(meaningful.to_string(index=False))
        else:
            print(check2[check2["delta"] != 0].to_string(index=False) if (check2["delta"] != 0).any() else "  (all deltas exactly 0)")

    check1.to_csv("data/corruption_check1_lookback_exposure.csv", index=False)
    check2.to_csv("data/corruption_check2_cross_sectional_exposure.csv", index=False)
    print(f"\n{'=' * 78}")
    print("Saved -> data/corruption_check1_lookback_exposure.csv, data/corruption_check2_cross_sectional_exposure.csv")


if __name__ == "__main__":
    main()
