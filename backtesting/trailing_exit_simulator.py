"""
===============================================================================
Falcon AI Swing Trading Platform — Trailing-Exit Backtest Experiment
===============================================================================
Script      : trailing_exit_simulator.py
Package     : Backtesting

Simulates a Qullamaggie-style alternative exit rule -- partial profit-
taking early, then trailing the remainder on a moving average -- against
the SAME entries, SAME original stop, SAME everything else already
validated by run #4. Pure post-processing research comparison: does not
touch categorize(), get_entry_target_stop(), or the live scan path, and
is never wired into any production decision.

Motivating finding: the naive momentum baseline's average winner (12.25%)
beat Falcon's own average winner (10.37%) on run #4/Gate 3 data, despite
Falcon's better win rate and Calmar -- a fixed measured-move target caps
upside the moment it's hit. This tests whether trailing the remainder
instead lets winners run further, at whatever cost to win rate/portfolio
risk that trade-off carries -- see tests/run_trailing_exit_experiment.py
for the full replay/comparison this module feeds.
===============================================================================
"""
from __future__ import annotations

import pandas as pd

NO_DATA_RESULT = {
    "partial_exit_date": None,
    "partial_exit_price": None,
    "remainder_exit_date": None,
    "remainder_exit_price": None,
    "remainder_exit_reason": "NO_DATA",
    "blended_return_pct": None,
    "never_hit_partial_trigger": None,
}


def simulate_trailing_exit(
    entry_price: float,
    entry_date: pd.Timestamp,
    price_history: pd.DataFrame,
    partial_exit_gain_pct: float = 8.0,
    partial_exit_fraction: float = 0.5,
    trailing_ma_period: int = 20,
    max_holding_days: int = 40,
    hard_stop_price: float | None = None,
) -> dict:
    """
    Simulates an alternative exit: sell `partial_exit_fraction` of the
    position the first day price closes >= entry_price * (1 +
    partial_exit_gain_pct/100); the remainder is then held and exited the
    first day price closes below the `trailing_ma_period`-day moving
    average, OR max_holding_days elapses, OR hard_stop_price is hit at
    any point (whichever comes first -- the original structural stop is
    NEVER removed, it stays live for the full remaining position the
    entire time, including after the partial exit).

    Sequencing per day, same conservative same-day tie-break philosophy
    as outcome_measurement.measure_forward_outcome() (a stop always wins
    a same-day ambiguity rather than the more optimistic alternative):
      1. hard_stop_price is checked FIRST every day (Low <= hard_stop_price),
         both before and after the partial trigger -- if it fires before
         the partial trigger, the ENTIRE position exits there
         (never_hit_partial_trigger=True); if it fires after, only the
         remainder does.
      2. Before the partial trigger has fired: the only other thing
         checked is the partial-exit condition itself (Close >=
         partial_exit_gain_pct above entry). The trailing MA is NOT
         checked yet -- there's nothing to trail until profit has
         actually been banked, and a trade that never reaches the
         partial-exit gain must "behave exactly as the original backtest
         did (stop or time-stop)", which a from-day-1 MA check would
         violate (it could exit a trade the original stop/time-stop
         never would have).
      3. After the partial trigger has fired: the trailing MA cross
         (Close < the trailing_ma_period-day SMA, computed here with no
         lookahead -- never off a precomputed fixed-window column, so
         any period can be tested) is checked each day the hard stop
         didn't already fire.
      4. If neither ends the trade within max_holding_days trading days
         of entry_date (a single time budget for the whole trade
         lifetime, not reset at the partial exit -- same window
         measure_forward_outcome() uses), the remainder exits at the
         Close of the last available day in that window ("TIME_STOP").

    blended_return_pct is the gross, weighted-average return across
    both legs (partial_exit_fraction at the partial price, the rest at
    the remainder price) -- callers applying a round-trip cost/r_multiple
    conversion should do so the same way the original episode's
    gross_return_pct already is (see episode_builder.py), not double it
    for the extra selling leg -- this experiment intentionally keeps the
    cost model identical to the original for a fair comparison.

    Returns
    -------
    dict : partial_exit_date/partial_exit_price (Timestamp/float | None,
    None when the partial trigger never fired), remainder_exit_date
    (Timestamp), remainder_exit_price (float), remainder_exit_reason
    ("TRAILING_MA" | "TIME_STOP" | "HARD_STOP"), blended_return_pct
    (float), never_hit_partial_trigger (bool). Fails closed to
    NO_DATA_RESULT (remainder_exit_reason="NO_DATA", every other field
    None) when entry_date isn't found in price_history, or there's no
    trading day at all after it -- same convention as
    outcome_measurement.measure_forward_outcome()'s own NO_DATA case.
    """
    ordered = price_history.sort_values("Date").reset_index(drop=True)
    ordered["_trailing_ma"] = ordered["Close"].rolling(trailing_ma_period).mean()

    entry_matches = ordered.index[ordered["Date"] == entry_date]
    if len(entry_matches) == 0:
        return dict(NO_DATA_RESULT)

    entry_idx = entry_matches[0]
    window = ordered.iloc[entry_idx + 1: entry_idx + 1 + max_holding_days]

    if window.empty:
        return dict(NO_DATA_RESULT)

    partial_trigger_price = entry_price * (1 + partial_exit_gain_pct / 100)

    partial_exit_date = None
    partial_exit_price = None
    partial_triggered = False

    for _, row in window.iterrows():
        if hard_stop_price is not None and row["Low"] <= hard_stop_price:
            return _finalize(
                entry_price, partial_exit_date, partial_exit_price, partial_triggered,
                partial_exit_fraction, row["Date"], hard_stop_price, "HARD_STOP",
            )

        if not partial_triggered:
            if row["Close"] >= partial_trigger_price:
                partial_triggered = True
                partial_exit_date = row["Date"]
                partial_exit_price = row["Close"]
            continue

        ma_value = row["_trailing_ma"]
        if pd.notna(ma_value) and row["Close"] < ma_value:
            return _finalize(
                entry_price, partial_exit_date, partial_exit_price, partial_triggered,
                partial_exit_fraction, row["Date"], row["Close"], "TRAILING_MA",
            )

    last_row = window.iloc[-1]
    return _finalize(
        entry_price, partial_exit_date, partial_exit_price, partial_triggered,
        partial_exit_fraction, last_row["Date"], last_row["Close"], "TIME_STOP",
    )


def _finalize(
    entry_price: float,
    partial_exit_date,
    partial_exit_price,
    partial_triggered: bool,
    partial_exit_fraction: float,
    remainder_exit_date,
    remainder_exit_price: float,
    remainder_exit_reason: str,
) -> dict:
    remainder_return_pct = (remainder_exit_price - entry_price) / entry_price * 100

    if partial_triggered:
        partial_return_pct = (partial_exit_price - entry_price) / entry_price * 100
        blended_return_pct = (
            partial_exit_fraction * partial_return_pct
            + (1 - partial_exit_fraction) * remainder_return_pct
        )
    else:
        blended_return_pct = remainder_return_pct

    return {
        "partial_exit_date": partial_exit_date,
        "partial_exit_price": partial_exit_price,
        "remainder_exit_date": remainder_exit_date,
        "remainder_exit_price": remainder_exit_price,
        "remainder_exit_reason": remainder_exit_reason,
        "blended_return_pct": blended_return_pct,
        "never_hit_partial_trigger": not partial_triggered,
    }
