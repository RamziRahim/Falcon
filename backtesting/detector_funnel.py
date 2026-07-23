"""
===============================================================================
Falcon AI Swing Trading Platform — Detector Funnel Diagnostics (Part A-4)
===============================================================================
Script      : detector_funnel.py
Package     : Backtesting

Per-detector precondition-survival counts across a whole backtest run:
each of the 5 continuation-pattern detectors' own invalidated_reason
(None when structurally valid) plus the breakout-recency contract (2.3,
technical_analysis/pattern_system/breakout_recency.py) classify every
(ticker, date) evaluation into exactly one funnel stage, tallied via
collections.Counter. Answers "where are signals actually being filtered
out" per detector -- e.g. does bull-flag/flat-base starvation come from
a genuinely rare structural setup, or from most setups clearing the
structural bar but never confirming price+volume, or from a threshold
that's simply too strict -- not just the final signal count.

Deliberately built on top of 2.3, not before it: without
breakout_within_last_k_bars, a detector's final "breakout confirmed"
stage would silently mix a freshly-confirmed breakout with one that's
simply been sitting above its pivot for weeks -- exactly the persistence
confound this diagnostic exists to detect, so counting it without the
recency split would just inherit the same confound one level up (the
sequencing note this was built in the order it was).
===============================================================================
"""
from __future__ import annotations

from collections import Counter

import pandas as pd

# analyze_ticker()'s own dict keys -> the display name used in reports and
# in pattern_engine.py's persisted PascalCase columns.
DETECTOR_DISPLAY_NAMES = {
    "vcp": "VCP",
    "flat_base": "Flat_Base",
    "cup_handle": "Cup_Handle",
    "triangle": "Ascending_Triangle",
    "bull_flag": "Bull_Flag",
}


def classify_funnel_stage(detector_result: dict) -> str:
    """One label per (ticker, date, detector) evaluation -- exactly one of:
    the detector's own invalidated_reason (a structural precondition that
    failed, e.g. NOT_IN_UPTREND/INSUFFICIENT_HISTORY/BASE_TOO_DEEP),
    SETUP_VALID_NO_BREAKOUT (structure confirmed, price/volume didn't
    clear), BREAKOUT_CONFIRMED_STALE (cleared, but not within the last k
    bars -- a persistence artifact, not a fresh signal), or
    BREAKOUT_CONFIRMED_FRESH."""
    invalidated_reason = detector_result.get("invalidated_reason")
    if invalidated_reason is not None:
        return invalidated_reason

    if not detector_result.get("is_breakout_confirmed"):
        return "SETUP_VALID_NO_BREAKOUT"

    if not detector_result.get("breakout_within_last_k_bars"):
        return "BREAKOUT_CONFIRMED_STALE"

    return "BREAKOUT_CONFIRMED_FRESH"


def build_detector_funnel(analysis: dict) -> dict[str, str]:
    """analysis: analyze_ticker()'s own return dict (has "vcp", "flat_base",
    "cup_handle", "triangle", "bull_flag" sub-dicts) -- one funnel_stage
    label per detector for this single (ticker, date) evaluation."""
    return {
        detector_key: classify_funnel_stage(analysis[detector_key])
        for detector_key in DETECTOR_DISPLAY_NAMES
    }


def tally_funnel(funnel_counts: dict[str, Counter], detector_funnel: dict[str, str] | None) -> None:
    """Mutates funnel_counts in place -- one Counter per detector, keyed by
    funnel_stage label. detector_funnel=None (e.g. a NO_DATA replay result,
    insufficient history to even run detection) is a no-op, not an error --
    there's nothing to attribute to any detector's own preconditions in
    that case."""
    if detector_funnel is None:
        return
    for detector_key, stage in detector_funnel.items():
        funnel_counts.setdefault(detector_key, Counter())[stage] += 1


def funnel_counts_to_dataframe(funnel_counts: dict[str, Counter]) -> pd.DataFrame:
    rows = []
    for detector_key, counter in funnel_counts.items():
        total = sum(counter.values())
        for stage, count in counter.most_common():
            rows.append({
                "detector": DETECTOR_DISPLAY_NAMES.get(detector_key, detector_key),
                "stage": stage,
                "count": count,
                "pct_of_total": round(count / total * 100, 1) if total else 0.0,
            })
    return pd.DataFrame(rows, columns=["detector", "stage", "count", "pct_of_total"])


def print_detector_funnel(funnel_counts: dict[str, Counter]) -> None:
    print("\n" + "=" * 78)
    print("  DETECTOR FUNNEL DIAGNOSTICS (A-4)")
    print("=" * 78)

    table = funnel_counts_to_dataframe(funnel_counts)
    if table.empty:
        print("  (no evaluations recorded)")
        print("=" * 78 + "\n")
        return

    for detector_name in table["detector"].unique():
        sub = table[table["detector"] == detector_name]
        total = int(sub["count"].sum())
        print(f"\n --- {detector_name} (n={total} evaluations) ---")
        for _, row in sub.iterrows():
            print(f"   {row['stage']}: {row['count']} ({row['pct_of_total']}%)")

    print("\n" + "=" * 78 + "\n")
