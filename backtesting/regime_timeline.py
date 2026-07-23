"""
===============================================================================
Falcon AI Swing Trading Platform — Regime Timeline + Attribution (Part A-2)
===============================================================================
Script      : regime_timeline.py
Package     : Backtesting

Reconstructs, for every calendar day the NIFTY benchmark has data, which
market_regime_verdict (FAVORABLE/CAUTION/UNFAVORABLE) that date would have
produced and WHY (DOWNTREND vs CHOPPY trend vs distribution_days>=3), then
summarizes what fraction of the run #1 window each cause covers and finds
contiguous runs of each verdict -- the piece Gate 1 needs to judge whether
the 25 UNFAVORABLE-capped episodes (see ceiling attribution) reflect a
handful of dates doing all the work or genuinely distinct risk-off periods.

Not a re-run of the replay engine (master execution spec standing rule 3):
market_verdict only ever depended on the single NIFTY benchmark series
truncated to as_of_date (backtesting/replay_engine.py's
replay_decision_as_of(), step 3) -- never on any per-ticker candidate,
pattern, or score. Reusing _truncate()/_trend_state_of_truncated() from
replay_engine.py and count_distribution_days()/get_market_regime_verdict()
from their real modules guarantees byte-for-byte the same verdict run #1
actually used for a given date, without touching the (expensive,
per-ticker) replay path at all.

Daily granularity, not run #1's 5-trading-day-per-ticker sampling cadence:
regime is a market-wide property, identical for every ticker sampled on a
given date, so a daily timeline gives a strictly more complete answer to
"do these episodes cluster" than replaying run #1's own per-ticker
sampling schedule would.
===============================================================================
"""
from __future__ import annotations

import pandas as pd

from backtesting.replay_engine import _trend_state_of_truncated, _truncate
from decision_engine.leadership_decision_engine import get_market_regime_verdict
from scoring.market_regime import count_distribution_days


def _cause(nifty_trend_state: str, distribution_days: int) -> str:
    """Mirrors get_market_regime_verdict()'s own branching exactly --
    see that function's docstring for the design rationale."""
    if nifty_trend_state == "DOWNTREND":
        return "DOWNTREND"

    reasons = []
    if nifty_trend_state == "CHOPPY":
        reasons.append("CHOPPY trend")
    if distribution_days >= 3:
        reasons.append(f"distribution_days={distribution_days}>=3")

    return " + ".join(reasons) if reasons else "UPTREND, distribution_days<3"


def build_regime_timeline(
    benchmark_history: pd.DataFrame, start_date: pd.Timestamp, end_date: pd.Timestamp
) -> pd.DataFrame:
    """One row per calendar day in [start_date, end_date] that the
    benchmark has a bar for -- market_regime_verdict + cause, reconstructed
    exactly as replay_decision_as_of() would have computed it for that date."""
    ordered = benchmark_history.sort_values("Date").reset_index(drop=True)
    window = ordered[(ordered["Date"] >= start_date) & (ordered["Date"] <= end_date)]

    rows = []
    for as_of_date in window["Date"]:
        truncated = _truncate(benchmark_history, as_of_date)
        distribution_days = count_distribution_days(truncated)
        nifty_trend_state = _trend_state_of_truncated(truncated)

        if nifty_trend_state != "UNKNOWN" and distribution_days is not None:
            verdict = get_market_regime_verdict(nifty_trend_state, distribution_days)
            cause = _cause(nifty_trend_state, distribution_days)
        else:
            # Same conservative fallback replay_decision_as_of() itself uses
            # when regime can't be determined for this date.
            verdict = "UNFAVORABLE"
            cause = "insufficient benchmark history"

        rows.append({
            "date": as_of_date,
            "nifty_trend_state": nifty_trend_state,
            "distribution_days": distribution_days,
            "market_regime_verdict": verdict,
            "cause": cause,
        })

    return pd.DataFrame(rows)


def summarize_regime_timeline(timeline: pd.DataFrame) -> dict:
    """% of the window per verdict and per cause -- the denominator for
    'is UNFAVORABLE a rare edge case or a large chunk of the window'."""
    if timeline.empty:
        return {"by_verdict": pd.DataFrame(), "by_cause": pd.DataFrame(), "total_days": 0}

    total = len(timeline)

    by_verdict = (
        timeline["market_regime_verdict"].value_counts()
        .rename_axis("verdict").reset_index(name="n_days")
    )
    by_verdict["pct_of_window"] = (by_verdict["n_days"] / total * 100).round(1)

    by_cause = (
        timeline["cause"].value_counts()
        .rename_axis("cause").reset_index(name="n_days")
    )
    by_cause["pct_of_window"] = (by_cause["n_days"] / total * 100).round(1)

    return {"by_verdict": by_verdict, "by_cause": by_cause, "total_days": total}


def find_contiguous_periods(timeline: pd.DataFrame, verdict: str) -> list[dict]:
    """Contiguous runs of `verdict` across the (daily, chronologically
    ordered) timeline -- a gap of even one day with a different verdict
    ends the run. Returns one dict per run: start_date, end_date, n_days."""
    if timeline.empty:
        return []

    ordered = timeline.sort_values("date").reset_index(drop=True)
    is_match = ordered["market_regime_verdict"] == verdict

    periods = []
    run_start = None

    for i, matched in enumerate(is_match):
        if matched and run_start is None:
            run_start = i
        elif not matched and run_start is not None:
            periods.append((run_start, i - 1))
            run_start = None

    if run_start is not None:
        periods.append((run_start, len(ordered) - 1))

    return [
        {
            "start_date": ordered["date"].iloc[start],
            "end_date": ordered["date"].iloc[end],
            "n_days": end - start + 1,
        }
        for start, end in periods
    ]


def attribute_episodes_to_periods(
    episodes: pd.DataFrame, periods: list[dict], date_column: str = "episode_start_date"
) -> pd.DataFrame:
    """For a set of episodes (typically pre-filtered to one regime/cause,
    e.g. the ceiling-attribution 'capped' + UNFAVORABLE-market subset),
    tags each episode with which contiguous period (by index, chronological
    order) its entry date falls into, then reports episode count per
    period -- if 25 episodes all show period_index=0, they're one cluster;
    if they spread across 8 different period_index values, they're
    genuinely distinct occurrences."""
    if episodes.empty or not periods:
        return pd.DataFrame(columns=["period_index", "start_date", "end_date", "n_days", "n_episodes"])

    def _period_index(entry_date) -> int | None:
        for i, period in enumerate(periods):
            if period["start_date"] <= entry_date <= period["end_date"]:
                return i
        return None

    working = episodes.copy()
    working["period_index"] = working[date_column].apply(_period_index)

    rows = []
    for i, period in enumerate(periods):
        n_episodes = int((working["period_index"] == i).sum())
        if n_episodes == 0:
            continue
        rows.append({
            "period_index": i,
            "start_date": period["start_date"],
            "end_date": period["end_date"],
            "n_days": period["n_days"],
            "n_episodes": n_episodes,
        })

    return pd.DataFrame(rows)
