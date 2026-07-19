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

NO_OUTCOME_RESULT = {
    "exit_date": None, "exit_price": None, "exit_reason": "NO_DATA",
    "return_pct": None, "days_held": None,
}


def measure_forward_outcome(
    entry_date: pd.Timestamp,
    entry_price: float,
    stop_loss: float,
    target: float,
    full_history: pd.DataFrame,
    max_holding_days: int = 20,
) -> dict:
    """
    Walks forward from entry_date up to max_holding_days trading days.
    Returns whichever comes first:
      - TARGET_HIT: High >= target on some day within the window
      - STOP_HIT: Low <= stop_loss on some day within the window
      - TIME_EXIT: neither hit -- exit at the close on the last available
        day of the window (day max_holding_days, or fewer if the
        downloaded history doesn't extend that far past entry_date)

    If both target and stop are touched on the SAME day (a real
    possibility with daily bars -- can't tell which happened first
    intraday), resolves conservatively to STOP_HIT, not TARGET_HIT.
    Optimistic tie-breaking would systematically overstate performance.

    Returns
    -------
    dict with keys: exit_date, exit_price, exit_reason
    ("TARGET_HIT"/"STOP_HIT"/"TIME_EXIT"/"NO_DATA"), return_pct, days_held.
    "NO_DATA" (all other fields None) when entry_date isn't found in
    full_history, or there's no trading day at all after it.
    """
    ordered = full_history.sort_values("Date").reset_index(drop=True)

    entry_matches = ordered.index[ordered["Date"] == entry_date]

    if len(entry_matches) == 0:
        return dict(NO_OUTCOME_RESULT)

    entry_idx = entry_matches[0]
    window = ordered.iloc[entry_idx + 1: entry_idx + 1 + max_holding_days]

    if window.empty:
        return dict(NO_OUTCOME_RESULT)

    for offset, (_, row) in enumerate(window.iterrows(), start=1):
        hit_stop = row["Low"] <= stop_loss
        hit_target = row["High"] >= target

        if hit_stop:
            # Wins the same-day tie against hit_target too -- see
            # docstring above.
            exit_price, exit_reason = stop_loss, "STOP_HIT"
        elif hit_target:
            exit_price, exit_reason = target, "TARGET_HIT"
        else:
            continue

        return_pct = ((exit_price - entry_price) / entry_price) * 100
        return {
            "exit_date": row["Date"], "exit_price": exit_price, "exit_reason": exit_reason,
            "return_pct": return_pct, "days_held": offset,
        }

    last_row = window.iloc[-1]
    exit_price = last_row["Close"]
    return_pct = ((exit_price - entry_price) / entry_price) * 100

    return {
        "exit_date": last_row["Date"], "exit_price": exit_price, "exit_reason": "TIME_EXIT",
        "return_pct": return_pct, "days_held": len(window),
    }
