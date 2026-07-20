"""
===============================================================================
Falcon AI Swing Trading Platform — NSE vs Yahoo Data Divergence Check
===============================================================================
Script      : data_source_comparison.py
Package     : Backtesting

A small, standalone diagnostic script, not a production module -- meant to
produce real numbers for a decision (loosen the 1.5x breakout-volume
threshold? trust one source's coverage over the other?), not to become
part of the ongoing pipeline. Same spirit as run_full_pipeline.py.

-------------------------------------------------------------------------
Confirmed live before writing the comparison logic, not guessed
-------------------------------------------------------------------------
1. corporate_actions_for_equity() genuinely confirms split/bonus events
   for 4 of the 6 sample tickers already -- no synthetic substitution
   needed:
     PERSISTENT  28-Mar-2024  Face Value Split 10 -> 5
     RELIANCE    28-Oct-2024  Bonus 1:1
     COFORGE     04-Jun-2025  Face Value Split 10 -> 2
     HDFCBANK    26-Aug-2025  Bonus 1:1
   TCS and POLYCAB have none in this window -- exactly the "expect small
   divergence" control group the sample was designed to include.

2. NSEProvider.get_history() and YahooProvider.get_history() return
   incompatible Date dtypes: NSE is tz-naive (datetime64[ns]), Yahoo is
   tz-aware (datetime64[ns, Asia/Kolkata]). Merging on "Date" without
   stripping Yahoo's tz produces a silent zero-match merge, not an error
   -- every row would misleadingly show up as "only in NSE" or "only in
   Yahoo". Normalized here before merging.

3. NSEProvider.get_history() pads any request under 30 days to a 30-day
   window regardless of the requested start_date (see its own
   "Expanding request boundary" log line) -- confirmed live it can
   return MORE days than requested. Both frames are trimmed to the
   originally-requested [start_date, end_date] after fetching, so that
   padding artifact doesn't get counted as a real source-completeness gap.

4. The price divergence this script exists to measure is real and large,
   confirmed directly: for RELIANCE around its Oct-2024 bonus, NSE's raw
   Close (~2741) is roughly double Yahoo's (~1369) for the same calendar
   dates. This is because yfinance's returned Close is ALWAYS
   split-adjusted across the ticker's full history, regardless of the
   auto_adjust flag (auto_adjust only toggles dividend adjustment) --
   while NSE's raw feed reports the actual as-traded historical price,
   never retroactively adjusted for a later corporate action. Pre-event
   dates should show a large, systematic close_pct_diff for split/bonus
   tickers; post-event dates should not. TCS/POLYCAB (no confirmed event
   in-window) are the control to compare against.
===============================================================================
"""
from __future__ import annotations

import datetime

import pandas as pd

from market_data.providers.nse_provider import NSEProvider
from market_data.providers.yahoo_provider import YahooProvider

SAMPLE_TICKERS = [
    # Large-cap Nifty 50 -- expect the smallest divergence, most liquid,
    # most reliably covered by both sources. RELIANCE and HDFCBANK also
    # each carry a confirmed 1:1 bonus in-window (see module docstring).
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS",
    # Nifty Midcap 150 -- more likely to surface data-quality gaps.
    # PERSISTENT and COFORGE also each carry a confirmed face-value split.
    "PERSISTENT.NS", "COFORGE.NS", "POLYCAB.NS",
]

# Confirmed via capital_market.corporate_actions_for_equity() -- see
# module docstring. Symbol -> (ex_date, description).
KNOWN_CORPORATE_ACTIONS = {
    "PERSISTENT.NS": ("2024-03-28", "Face Value Split 10 -> 5"),
    "RELIANCE.NS": ("2024-10-28", "Bonus 1:1"),
    "COFORGE.NS": ("2025-06-04", "Face Value Split 10 -> 2"),
    "HDFCBANK.NS": ("2025-08-26", "Bonus 1:1"),
}

DISCONTINUITY_THRESHOLD_PCT = 15.0


def verify_known_corporate_actions(tickers: list[str], from_date: str, to_date: str) -> pd.DataFrame:
    """
    Confirms at least one genuine split/bonus event exists in the sample
    by checking the real NSE corporate-actions feed -- not just trusting
    KNOWN_CORPORATE_ACTIONS' hardcoded snapshot, in case it's gone stale.
    from_date/to_date: 'dd-mm-YYYY' (nselib's own format).
    """
    from nselib import capital_market

    actions = capital_market.corporate_actions_for_equity(from_date=from_date, to_date=to_date)
    bare_symbols = [t.replace(".NS", "") for t in tickers]

    mask = actions["symbol"].isin(bare_symbols) & actions["subject"].str.contains(
        "Split|Bonus", case=False, na=False
    )
    found = actions[mask][["symbol", "exDate", "subject"]].reset_index(drop=True)

    if found.empty:
        raise AssertionError(
            "No split/bonus event found for any sample ticker in this date range -- "
            "the corporate-action-cliff test needs at least one to be meaningful."
        )

    return found


def _trim_to_range(df: pd.DataFrame, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
    """Undoes NSEProvider's own 30-day minimum-window padding (see module
    docstring) so it doesn't get counted as a real source-completeness gap."""
    start_ts, end_ts = pd.Timestamp(start_date), pd.Timestamp(end_date)
    return df[(df["Date"] >= start_ts) & (df["Date"] <= end_ts)].reset_index(drop=True)


def compare_sources(ticker: str, start_date: datetime.date, end_date: datetime.date) -> dict:
    nse_df = NSEProvider().get_history(ticker, start_date, end_date)
    yahoo_df = YahooProvider().get_history(ticker, start_date, end_date)

    # Yahoo's Date is tz-aware (Asia/Kolkata); NSE's is tz-naive -- must
    # match before merging on Date, or "both" is silently always empty.
    yahoo_df = yahoo_df.copy()
    yahoo_df["Date"] = pd.to_datetime(yahoo_df["Date"]).dt.tz_localize(None)

    nse_df = _trim_to_range(nse_df, start_date, end_date)
    yahoo_df = _trim_to_range(yahoo_df, start_date, end_date)

    merged = nse_df.merge(yahoo_df, on="Date", suffixes=("_nse", "_yahoo"), how="outer", indicator=True)
    merged = merged.sort_values("Date").reset_index(drop=True)

    only_nse = int((merged["_merge"] == "left_only").sum())
    only_yahoo = int((merged["_merge"] == "right_only").sum())

    both = merged[merged["_merge"] == "both"].copy()

    if both.empty:
        return {
            "ticker": ticker, "days_only_in_nse": only_nse, "days_only_in_yahoo": only_yahoo,
            "close_pct_diff_mean": None, "close_pct_diff_max_abs": None,
            "volume_pct_diff_mean": None, "volume_pct_diff_max_abs": None,
            "suspicious_discontinuity_days": 0, "suspicious_dates": [],
        }

    both["close_pct_diff"] = ((both["Close_yahoo"] - both["Close_nse"]) / both["Close_nse"]) * 100
    both["volume_pct_diff"] = ((both["Volume_yahoo"] - both["Volume_nse"]) / both["Volume_nse"]) * 100

    # Flag single-day discontinuities unique to one source -- the direct
    # test for an unhandled corporate-action cliff showing up in only one
    # provider's data.
    both["nse_daily_move_pct"] = both["Close_nse"].pct_change() * 100
    both["yahoo_daily_move_pct"] = both["Close_yahoo"].pct_change() * 100
    suspicious_days = both[
        (both["nse_daily_move_pct"].abs() > DISCONTINUITY_THRESHOLD_PCT)
        != (both["yahoo_daily_move_pct"].abs() > DISCONTINUITY_THRESHOLD_PCT)
    ]

    return {
        "ticker": ticker,
        "days_only_in_nse": only_nse,
        "days_only_in_yahoo": only_yahoo,
        "close_pct_diff_mean": both["close_pct_diff"].mean(),
        "close_pct_diff_max_abs": both["close_pct_diff"].abs().max(),
        "volume_pct_diff_mean": both["volume_pct_diff"].mean(),
        "volume_pct_diff_max_abs": both["volume_pct_diff"].abs().max(),
        "suspicious_discontinuity_days": len(suspicious_days),
        "suspicious_dates": suspicious_days["Date"].dt.strftime("%Y-%m-%d").tolist() if len(suspicious_days) else [],
    }


def run_comparison(
    tickers: list[str] = SAMPLE_TICKERS,
    start_date: datetime.date = datetime.date(2024, 1, 1),
    end_date: datetime.date = datetime.date(2025, 12, 1),
) -> pd.DataFrame:
    verified = verify_known_corporate_actions(
        tickers, start_date.strftime("%d-%m-%Y"), end_date.strftime("%d-%m-%Y")
    )
    print("Confirmed split/bonus events in sample (live NSE corporate-actions feed):")
    print(verified.to_string(index=False))
    print()

    results = [compare_sources(t, start_date, end_date) for t in tickers]
    df = pd.DataFrame(results)
    print(df.to_string())
    return df


if __name__ == "__main__":
    run_comparison()
