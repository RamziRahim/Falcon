"""
===============================================================================
Falcon AI Swing Trading Platform — VWAP Reclaim (Informational Confluence)
===============================================================================
Script      : vwap_reclaim.py
Package     : Technical Analysis

Computes today's running intraday VWAP from 1-minute bars and checks
whether price dipped below it earlier today and has since reclaimed it --
a genuinely different, non-overlapping timeframe of information from every
other signal in this codebase, all of which read daily bars.

Version 1 only: purely informational, same treatment as the existing
LOW_DELIVERY_CONVICTION / TECHNICALLY_OVEREXTENDED fakeout-risk flags
(ui/dashboard_data.py's get_fakeout_risk_flags()) -- this module only
computes the number. It is never called from compute_score(),
categorize(), or anything else that decides category/predicted_p; see
services/scan_pipeline_service.py's own wiring for where this is attached
to a candidate record, strictly downstream of categorization.

yfinance's intraday bars carry no native VWAP field (confirmed live,
2026-09-05 -- checked before writing this), so VWAP is computed here from
typical price ((High+Low+Close)/3), the standard formula.

Investigated live before this module was written (2026-09-05, real NSE
tickers via yfinance): 1-minute bar coverage is real but genuinely uneven
across tickers -- a thinner name (ANURAS.NS) was missing 39% of its
session's bars across 54 separate gaps (up to 11 minutes each), while
several others returned a full session. MIN_COVERAGE_RATIO below exists
specifically because of that finding: a name with "enough elapsed time"
but too many missing bars can still produce a VWAP built on a fraction of
the day's real trades, which is not the same failure mode as "too early
in the session" (MIN_BARS_REQUIRED) and needs its own fail-closed check.
===============================================================================
"""
from __future__ import annotations

import pandas as pd

REQUIRED_COLUMNS = ["Datetime", "High", "Low", "Close", "Volume"]

# Below this many real 1-minute bars, VWAP is too young to mean anything --
# the "very early in the trading session" fail-closed case the spec calls
# out explicitly. Distinct from MIN_COVERAGE_RATIO below (that one catches
# a *sparse*, not just *young*, session).
MIN_BARS_REQUIRED = 15

# See module docstring -- confirmed live that coverage gaps are real and
# can be large on thinner names. A session missing more than 30% of its
# expected 1-minute bars (given the elapsed time its own first/last
# timestamps span) is judged too gappy to trust, even if MIN_BARS_REQUIRED
# is technically satisfied.
MIN_COVERAGE_RATIO = 0.70

NO_RECLAIM_RESULT = {
    "vwap_reclaimed": False,
    "currently_above_vwap": False,
    "vwap_value": None,
    "dipped_below_vwap_today": False,
    "invalidated_reason": None,
}


def compute_vwap_reclaim_status(intraday_bars: pd.DataFrame) -> dict:
    """
    Computes today's running VWAP from intraday bars and checks whether
    price dipped below it and has since reclaimed it.

    Parameters
    ----------
    intraday_bars : pd.DataFrame
        Today's 1-minute bars so far, with columns Datetime/High/Low/
        Close/Volume (Datetime need not be pre-sorted -- sorted here).

    Definition
    ----------
    VWAP = cumulative(typical_price * volume) / cumulative(volume) for
    the trading day so far, typical_price = (High+Low+Close)/3.

    "Reclaimed" = Close was below the running VWAP at some earlier bar
    today AND the latest Close is now above the latest VWAP. A candidate
    that has been above VWAP all day (never dipped) is NOT a "reclaim" --
    it's a different, simpler state (currently_above_vwap=True,
    dipped_below_vwap_today=False), reported distinctly rather than
    conflated with a genuine recovery.

    Returns
    -------
    dict : vwap_reclaimed (bool), currently_above_vwap (bool), vwap_value
    (float | None), dipped_below_vwap_today (bool), invalidated_reason
    (str | None). Fails closed (invalidated_reason set, every other field
    at its NO_RECLAIM_RESULT default) when there are too few real bars
    yet, coverage is too gapped to trust, or the data is missing/malformed.
    """
    if intraday_bars is None or intraday_bars.empty:
        return _invalidated("no_intraday_bars")

    missing_columns = [c for c in REQUIRED_COLUMNS if c not in intraday_bars.columns]
    if missing_columns:
        return _invalidated("missing_required_columns")

    df = intraday_bars.copy()
    df["Datetime"] = pd.to_datetime(df["Datetime"], errors="coerce")
    for col in ["High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=REQUIRED_COLUMNS)

    if df.empty:
        return _invalidated("malformed_data")

    df = df.sort_values("Datetime").reset_index(drop=True)

    # Zero/negative prices or volume are not real trading data -- fail
    # closed rather than let them silently distort the cumulative VWAP.
    if (df[["High", "Low", "Close"]] <= 0).to_numpy().any() or (df["Volume"] < 0).any():
        return _invalidated("malformed_data")

    if len(df) < MIN_BARS_REQUIRED:
        return _invalidated("insufficient_bars_early_session")

    elapsed_minutes = (
        (df["Datetime"].iloc[-1] - df["Datetime"].iloc[0]).total_seconds() / 60.0 + 1.0
    )
    coverage_ratio = (len(df) / elapsed_minutes) if elapsed_minutes > 0 else 0.0

    if coverage_ratio < MIN_COVERAGE_RATIO:
        return _invalidated("insufficient_bar_coverage")

    total_volume = df["Volume"].sum()
    if total_volume <= 0:
        return _invalidated("malformed_data")

    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3.0
    cumulative_pv = (typical_price * df["Volume"]).cumsum()
    cumulative_volume = df["Volume"].cumsum()
    vwap_series = cumulative_pv / cumulative_volume

    current_close = float(df["Close"].iloc[-1])
    current_vwap = float(vwap_series.iloc[-1])

    dipped_below_today = bool((df["Close"] < vwap_series).any())
    currently_above = bool(current_close > current_vwap)

    return {
        "vwap_reclaimed": bool(dipped_below_today and currently_above),
        "currently_above_vwap": currently_above,
        "vwap_value": round(current_vwap, 2),
        "dipped_below_vwap_today": dipped_below_today,
        "invalidated_reason": None,
    }


def _invalidated(reason: str) -> dict:
    result = dict(NO_RECLAIM_RESULT)
    result["invalidated_reason"] = reason
    return result
