"""
===============================================================================
Falcon AI Swing Trading Platform — Backtesting Outcome Measurement (Part B)
===============================================================================
Script      : outcome_measurement.py
Package     : Backtesting

Once a historical decision is reconstructed (replay_engine.replay_decision_as_of),
checking what price actually did afterward uses data that already exists in
the downloaded history -- this is what the decision is being tested
*against*, not an input to the decision itself. Not lookahead bias; it's
the actual point of the exercise.
===============================================================================
"""
from __future__ import annotations

import pandas as pd

from config import MAX_HOLDING_TRADING_DAYS

NO_OUTCOME_RESULT = {
    "exit_date": None, "exit_price": None, "exit_reason": "NO_DATA",
    "return_pct": None, "days_held": None, "fill_price": None,
}


FILL_NEXT_OPEN = "next_open"
FILL_AS_GIVEN = "as_given"


def measure_forward_outcome(
    entry_date: pd.Timestamp,
    entry_price: float,
    stop_loss: float,
    target: float,
    full_history: pd.DataFrame,
    max_holding_days: int = MAX_HOLDING_TRADING_DAYS,
    fill: str = FILL_NEXT_OPEN,
) -> dict:
    """
    Walks forward from entry_date up to max_holding_days trading days.

    Fill model (fill=FILL_NEXT_OPEN, the default since 2026-10-20):
    a signal is only known at entry_date's CLOSE, so the position is
    bought at the NEXT trading day's open -- not at entry_price. Run #4
    filled at the pattern pivot instead, which in 46 of 59 taken trades
    was below anything that traded on the signal day (docs/
    known_data_issues.md item 10). stop_loss/target are price LEVELS
    from the trade plan and are kept as-is; returns are measured from the
    actual fill. If the fill opens at/above target or at/below stop the
    trade can't be taken as planned and NO_FILL is returned (exit_reason
    NO_FILL_PAST_TARGET / NO_FILL_BELOW_STOP, other fields None).
    Gaps through a level fill at the open (a stop gapped through costs
    more than the stop; a target gapped through pays the open).

    fill=FILL_AS_GIVEN reproduces the legacy behaviour (enter at
    entry_price, walk from the next day) for comparing against old runs
    only -- never use it for new results.

    Exit rules, whichever comes first:
      - STOP_HIT: Low <= stop_loss (wins a same-day tie with the target;
        intraday order is unknowable from daily bars, so be conservative)
      - TARGET_HIT: High >= target
      - TIME_EXIT: neither -- exit at the close of the last window day.

    Returns dict with exit_date, exit_price, exit_reason, return_pct,
    days_held, fill_price. NO_DATA when entry_date isn't in the history or
    there is no later trading day.
    """
    ordered = full_history.sort_values("Date").reset_index(drop=True)

    entry_matches = ordered.index[ordered["Date"] == entry_date]

    if len(entry_matches) == 0:
        return dict(NO_OUTCOME_RESULT)

    entry_idx = entry_matches[0]
    window = ordered.iloc[entry_idx + 1: entry_idx + 1 + max_holding_days]

    if window.empty:
        return dict(NO_OUTCOME_RESULT)

    if fill == FILL_NEXT_OPEN:
        fill_price = float(window.iloc[0]["Open"])
        if fill_price >= target:
            return {**NO_OUTCOME_RESULT, "exit_reason": "NO_FILL_PAST_TARGET", "fill_price": fill_price}
        if fill_price <= stop_loss:
            return {**NO_OUTCOME_RESULT, "exit_reason": "NO_FILL_BELOW_STOP", "fill_price": fill_price}
    elif fill == FILL_AS_GIVEN:
        fill_price = entry_price
    else:
        raise ValueError(f"Unknown fill model: {fill!r}")

    for offset, (_, row) in enumerate(window.iterrows(), start=1):
        hit_stop = row["Low"] <= stop_loss
        hit_target = row["High"] >= target
        # On the fill day itself the open is the fill, so only later days
        # can gap through a level.
        gap_open = row["Open"] if (fill == FILL_NEXT_OPEN and offset > 1) else None

        if hit_stop:
            exit_price = min(stop_loss, gap_open) if gap_open is not None else stop_loss
            exit_reason = "STOP_HIT"
        elif hit_target:
            exit_price = max(target, gap_open) if gap_open is not None else target
            exit_reason = "TARGET_HIT"
        else:
            continue

        return_pct = ((exit_price - fill_price) / fill_price) * 100
        return {
            "exit_date": row["Date"], "exit_price": exit_price, "exit_reason": exit_reason,
            "return_pct": return_pct, "days_held": offset, "fill_price": fill_price,
        }

    last_row = window.iloc[-1]
    exit_price = last_row["Close"]
    return_pct = ((exit_price - fill_price) / fill_price) * 100

    return {
        "exit_date": last_row["Date"], "exit_price": exit_price, "exit_reason": "TIME_EXIT",
        "return_pct": return_pct, "days_held": len(window), "fill_price": fill_price,
    }
