"""
===============================================================================
Falcon AI Swing Trading Platform — Corporate Action Backward-Adjustment
===============================================================================
Script      : corporate_actions.py
Package     : Market Data

Backward-adjusts cached OHLCV data for confirmed stock splits/bonus
issues. NSEProvider's underlying nselib feed
(capital_market.price_volume_and_deliverable_position_data) returns NSE's
own raw historical archive -- genuinely unadjusted for corporate actions.
Confirmed directly there is no alternative from this provider at all:
NSEProvider.get_splits()/.get_corporate_actions() are literal
NotImplementedError stubs, and the cached data/technical/*.parquet Close
series carries no Adj Close column whatsoever.

Found the hard way, not guessed: BAJFINANCE.NS's Close dropped from
Rs 9,419.5 to Rs 938.0 overnight on 2025-06-16 while building a momentum
baseline for run #3 (backtesting/baselines.py) -- a real, NSE-documented
"Face Value Split (Sub-Division) - From Rs 2/- Per Share To Re 1/- Per
Share" + "Bonus 4:1" on that exact date (combined ~10x dilution, matching
the observed ratio almost exactly), not a crash. ~35% of the 496-ticker
Nifty 500 universe carries at least one such discontinuity somewhere in
its history.

nselib.capital_market.corporate_actions_for_equity() returns the WHOLE
market's corporate action records for a date range in ONE call -- no
symbol filter parameter exists, and none is needed: fetched and cached
once, reused across every ticker's own adjustment pass rather than
queried per ticker.

-------------------------------------------------------------------------
Detection-then-confirmation, not blind correction
-------------------------------------------------------------------------
A single-day move past DISCONTINUITY_THRESHOLD is only treated as a
corporate action (and adjusted) when a matching NSE-documented record
exists for that symbol within DATE_TOLERANCE_DAYS of the move -- otherwise
it's left untouched and reported back as unconfirmed, not silently
corrected or dropped. An unconfirmed large move could be a genuine crash
or rally, not a data artifact; adjusting it on a guess would corrupt real
price history instead of fixing fake history.

The OBSERVED price ratio on the confirmed date is used as the adjustment
factor, not a ratio parsed out of the action's free-text "subject" field
(e.g. "Bonus 4:1", "Face Value Split ... Rs 2/- To Re 1/-") -- once a
real action is confirmed to exist on that date, the observed jump IS the
split/bonus ratio (to within ordinary day-to-day noise, which is
typically two orders of magnitude smaller than a real split's own
scale). Parsing NSE's inconsistent phrasing for every possible corporate
action type is a separate, more fragile problem this module doesn't need
to solve to get a correct factor.
===============================================================================
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from common.logger import get_logger
from config import DATA_FOLDER

logger = get_logger(__name__)

CORPORATE_ACTIONS_CACHE_PATH = DATA_FOLDER / "corporate_actions_cache.parquet"
DISCONTINUITY_THRESHOLD = 0.40
DATE_TOLERANCE_DAYS = 3


def fetch_all_corporate_actions(
    from_date: dt.date, to_date: dt.date, force_refresh: bool = False,
) -> pd.DataFrame:
    """Whole-market corporate actions for [from_date, to_date], cached to
    disk. Confirmed live: a single call across a full 10-year range
    (2016-2026) returns in seconds (~23,500 rows market-wide) -- no need
    to chunk this by year or by symbol.
    """
    if not force_refresh and CORPORATE_ACTIONS_CACHE_PATH.exists():
        cached = pd.read_parquet(CORPORATE_ACTIONS_CACHE_PATH)
        cached["exDate"] = pd.to_datetime(cached["exDate"], errors="coerce", dayfirst=True)
        return cached

    from nselib import capital_market

    raw = capital_market.corporate_actions_for_equity(
        from_date=from_date.strftime("%d-%m-%Y"), to_date=to_date.strftime("%d-%m-%Y"),
    )
    raw = raw.copy()
    raw["exDate"] = pd.to_datetime(raw["exDate"], errors="coerce", dayfirst=True)

    CORPORATE_ACTIONS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw.to_parquet(CORPORATE_ACTIONS_CACHE_PATH, index=False)
    logger.info(
        "Fetched and cached %d corporate action records (%s to %s).",
        len(raw), from_date, to_date,
    )
    return raw


def detect_discontinuities(df: pd.DataFrame, threshold: float = DISCONTINUITY_THRESHOLD) -> pd.DataFrame:
    """Single-day |% move| in Close past `threshold` -- candidates for
    confirm_and_adjust() to check against real corporate-action records,
    not itself a verdict that any of them are actually splits."""
    ordered = df.sort_values("Date").reset_index(drop=True)
    pct_change = ordered["Close"].pct_change()
    hits = pct_change[pct_change.abs() > threshold]

    return pd.DataFrame({
        "Date": ordered.loc[hits.index, "Date"].values,
        "pct_change": hits.values,
        "close_before": ordered["Close"].shift(1).loc[hits.index].values,
        "close_after": ordered["Close"].loc[hits.index].values,
    })


def _symbol_actions(corporate_actions: pd.DataFrame, symbol: str) -> pd.DataFrame:
    clean_symbol = symbol.upper()
    if clean_symbol.endswith(".NS"):
        clean_symbol = clean_symbol[:-3]
    return corporate_actions[corporate_actions["symbol"].str.upper().str.strip() == clean_symbol]


def confirm_and_adjust(
    df: pd.DataFrame,
    symbol: str,
    corporate_actions: pd.DataFrame,
    threshold: float = DISCONTINUITY_THRESHOLD,
    date_tolerance_days: int = DATE_TOLERANCE_DAYS,
) -> tuple[pd.DataFrame, list[dict]]:
    """Backward-adjusts df's Open/High/Low/Close (and inversely, Volume)
    for every detected discontinuity that has a matching NSE-documented
    corporate action for `symbol` within `date_tolerance_days`. See
    module docstring for why the observed ratio (not parsed text) is the
    adjustment factor, and why unconfirmed discontinuities are left alone.

    Returns
    -------
    (adjusted_df, log) : log is a list of dicts, one per detected
    discontinuity -- {"date", "confirmed": bool, ...}. Empty list means no
    discontinuity was even detected (the common case).
    """
    ordered = df.sort_values("Date").reset_index(drop=True).copy()
    discontinuities = detect_discontinuities(ordered, threshold)

    if discontinuities.empty:
        return ordered, []

    symbol_actions = _symbol_actions(corporate_actions, symbol)
    log: list[dict] = []

    # Latest first: each confirmed adjustment scales everything strictly
    # BEFORE its own date. Applying oldest-to-newest would let a later
    # correction's factor double-apply to dates an earlier correction
    # already scaled.
    for _, row in discontinuities.sort_values("Date", ascending=False).iterrows():
        event_date = pd.Timestamp(row["Date"])
        window_start = event_date - pd.Timedelta(days=date_tolerance_days)
        window_end = event_date + pd.Timedelta(days=date_tolerance_days)
        matches = symbol_actions[
            (symbol_actions["exDate"] >= window_start) & (symbol_actions["exDate"] <= window_end)
        ]

        if matches.empty:
            log.append({
                "date": event_date, "confirmed": False, "pct_change": row["pct_change"],
                "reason": "no matching NSE corporate action record within tolerance",
            })
            continue

        factor = row["close_after"] / row["close_before"]
        before_mask = ordered["Date"] < event_date

        for price_col in ("Open", "High", "Low", "Close"):
            if price_col in ordered.columns:
                ordered.loc[before_mask, price_col] = ordered.loc[before_mask, price_col] * factor

        if "Volume" in ordered.columns and factor != 0:
            adjusted_volume = ordered.loc[before_mask, "Volume"] / factor
            ordered.loc[before_mask, "Volume"] = adjusted_volume.round().astype(ordered["Volume"].dtype)

        log.append({
            "date": event_date, "confirmed": True, "factor": factor,
            "actions": "; ".join(matches["subject"].tolist()),
        })

    return ordered, log


# =============================================================================
# Ingestion-time adjustment (keeps the cache split-adjusted in the live path)
# =============================================================================
#
# confirm_and_adjust() above used to run ONLY as a one-off manual script
# (tests/apply_split_adjustment.py, 2026-07-29). The live pipeline never
# called it, so any ticker whose raw cache was (re)built afterwards --
# cache_synchronizer deletes a symbol's cache the day it leaves the
# candidate universe, and the next scan re-downloads its full history raw --
# silently reverted to UNADJUSTED prices (found 2026-10-20: NAUKRI's cached
# Close was 5.29x run #4's own entry_price). These helpers make adjustment a
# normal part of every cache write.

CORPORATE_ACTIONS_MAX_AGE_DAYS = 1
_ACTIONS_HISTORY_START = dt.date(2016, 1, 1)


def load_corporate_actions(max_age_days: int = CORPORATE_ACTIONS_MAX_AGE_DAYS) -> pd.DataFrame | None:
    """Corporate-actions table for ingestion-time adjustment.

    Refreshes the on-disk cache when it is older than `max_age_days` so a
    split announced after the last refresh is still known. Never raises:
    if the refresh fails the stale cache is used (with a warning), and if
    there is no cache at all, returns None -- the caller then skips
    adjustment rather than failing the whole scan.
    """
    import time

    cache_exists = CORPORATE_ACTIONS_CACHE_PATH.exists()
    stale = True
    if cache_exists:
        age_days = (time.time() - CORPORATE_ACTIONS_CACHE_PATH.stat().st_mtime) / 86400
        stale = age_days > max_age_days

    try:
        if cache_exists and not stale:
            return fetch_all_corporate_actions(_ACTIONS_HISTORY_START, dt.date.today())
        return fetch_all_corporate_actions(_ACTIONS_HISTORY_START, dt.date.today(), force_refresh=True)
    except Exception as ex:  # noqa: BLE001 - network/parse failures must not break a scan
        if cache_exists:
            logger.warning("Corporate-actions refresh failed (%s); using stale cache.", ex)
            return fetch_all_corporate_actions(_ACTIONS_HISTORY_START, dt.date.today())
        logger.warning("Corporate-actions unavailable (%s); skipping ingestion-time adjustment.", ex)
        return None


def merge_and_adjust(
    symbol: str,
    existing: pd.DataFrame | None,
    new_rows: pd.DataFrame,
    corporate_actions: pd.DataFrame | None,
) -> tuple[pd.DataFrame, list[dict]]:
    """Combine cached history with freshly downloaded rows and backward-
    adjust for any confirmed split/bonus visible in the combined series.

    Returns (full_history, confirmed_events). `confirmed_events` is empty
    when nothing needed adjusting; the caller can then keep the cheap
    append-only cache update. When it is non-empty, `full_history` replaces
    the cached file (everything before each event date has been rescaled).

    Idempotent: history that was already adjusted has no remaining
    discontinuity at the event date, so re-running changes nothing.
    """
    if corporate_actions is None or corporate_actions.empty:
        return new_rows, []

    parts = [p for p in (existing, new_rows) if p is not None and not p.empty]
    combined = pd.concat(parts, ignore_index=True)
    combined["Date"] = pd.to_datetime(combined["Date"])
    if combined["Date"].dt.tz is not None:
        combined["Date"] = combined["Date"].dt.tz_localize(None)
    combined = combined.drop_duplicates(subset="Date", keep="last").sort_values("Date").reset_index(drop=True)

    base_columns = [c for c in ("Date", "Open", "High", "Low", "Close", "Volume") if c in combined.columns]
    adjusted_base, log = confirm_and_adjust(combined[base_columns], symbol, corporate_actions)
    confirmed = [e for e in log if e["confirmed"]]

    if not confirmed:
        return combined, []

    result = combined.copy()
    price_volume = [c for c in base_columns if c != "Date"]
    for column in price_volume:
        result[column] = adjusted_base[column].values

    if "Deliverable_Qty" in result.columns:
        for event in confirmed:
            if event["factor"] != 0:
                before = result["Date"] < event["date"]
                result.loc[before, "Deliverable_Qty"] = (
                    result.loc[before, "Deliverable_Qty"] / event["factor"]
                ).round()

    return result, confirmed
