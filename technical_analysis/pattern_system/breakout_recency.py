"""
===============================================================================
Falcon AI Swing Trading Platform — Breakout Recency Contract (Part A-5)
===============================================================================
Script      : breakout_recency.py
Package     : Technical Analysis / Pattern System

Every one of the 5 continuation-pattern detectors (VCP, Flat Base, Cup &
Handle, Ascending Triangle, Bull Flag) confirms a breakout with the exact
same formula, evaluated against only the LATEST bar:

    Close > pivot_level  AND  Volume >= volume_baseline * 1.5

That means a stock that broke out 15 bars ago and has simply stayed above
its pivot with occasionally elevated volume reads identically, on every
subsequently sampled date, to one breaking out for the first time today --
the detector has no notion of "how long has this been true." Every
replay date within that persistence window looks like an independent
fresh signal, which silently inflates both raw signal counts (the
resampling-artifact problem episode_builder.py exists to collapse after
the fact) and, more specifically, detector funnel-diagnostic counts (A-4,
Phase 2.4) if a funnel doesn't share this same recency definition.

compute_breakout_recency() answers "how many bars ago did this specific
breakout condition first become true, in the current unbroken streak" so
callers can tell a fresh breakout from a stale-but-still-true one.

Deliberately reuses each detector's OWN already-computed pivot_level/
volume_baseline (fixed values from the structure identified as of the
current call) rather than re-deriving contraction/base/triangle/flag
structure at every prior bar in the lookback window -- a full historical
re-detection at each bar would need to re-run swing detection and each
pattern's own structure-finding logic once per day in the window, a much
larger change than this contract calls for. This is a legitimate
approximation: pivot/volume-baseline levels are themselves multi-week
structural quantities that don't meaningfully shift within a short (tens
of bars) recency lookback, so holding them fixed while walking backward
doesn't change the answer to "how long has price+volume cleared THIS
level," which is the actual question being asked.
===============================================================================
"""
from __future__ import annotations

import pandas as pd

from config import BREAKOUT_RECENCY_K_BARS


def compute_breakout_recency(
    df: pd.DataFrame,
    pivot_level: float | None,
    volume_baseline: float | None,
    k: int = BREAKOUT_RECENCY_K_BARS,
    max_lookback: int = 60,
) -> dict:
    """
    Returns {"bars_since_breakout": int | None, "breakout_within_last_k_bars": bool}.

    bars_since_breakout is None whenever the latest bar does not itself
    satisfy the breakout condition -- recency is only a meaningful
    question for a bar that IS currently a confirmed breakout; callers
    should already be gating on the detector's own is_breakout_confirmed
    flag. 0 means today is the first day of the current unbroken streak;
    N means the streak (today included) has held for N+1 consecutive bars.

    max_lookback bounds how far back the streak-walk goes (60 trading
    days -- comfortably longer than any real "still fresh" window while
    keeping the walk cheap); a streak longer than that is simply reported
    at the capped value, not an error.
    """
    if pivot_level is None or volume_baseline is None or pd.isna(volume_baseline) or volume_baseline <= 0:
        return {"bars_since_breakout": None, "breakout_within_last_k_bars": False}

    ordered = df.sort_values("Date").reset_index(drop=True)
    n = len(ordered)

    def _condition_holds(row) -> bool:
        return row["Close"] > pivot_level and row["Volume"] >= volume_baseline * 1.5

    if n == 0 or not _condition_holds(ordered.iloc[-1]):
        return {"bars_since_breakout": None, "breakout_within_last_k_bars": False}

    streak = 0
    lookback_floor = max(-1, n - 1 - max_lookback)
    for i in range(n - 1, lookback_floor, -1):
        if _condition_holds(ordered.iloc[i]):
            streak += 1
        else:
            break

    bars_since_breakout = streak - 1
    return {
        "bars_since_breakout": bars_since_breakout,
        "breakout_within_last_k_bars": bars_since_breakout <= k,
    }
