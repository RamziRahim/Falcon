"""
===============================================================================
Falcon AI Swing Trading Platform — Baselines (Part I-4)
===============================================================================
Script      : baselines.py
Package     : Backtesting

Three baselines EXECUTE's episode-level performance has to actually beat
before "the strategy adds value" is a claim rather than an assumption --
docs/backtest_success_criteria.md's criterion 4 is specifically "EXECUTE
beats the random-entry control's 95th percentile, net of costs."

None of these call categorize(), replay_decision_as_of(), or any pattern
detector -- "minimal outcome evaluator" means literally
outcome_measurement.measure_forward_outcome() (already exists, already
tested, already what run #1 itself used to grade every real signal)
applied to entry points chosen by a rule with no market/sector/pattern
logic in it at all. Same universe_histories run #1 already loaded
(data/technical/*.parquet), no new fetch.

1. NIFTY buy-and-hold over the run #1 window -- the simplest "did you
   even need a strategy" bar.
2. Random-entry control -- K draws of (ticker, date) from the same
   universe/window, each given the SAME target/stop distances a typical
   real signal used (so it's a fair comparison against episode-level
   r_multiple, not a strawman with no risk management at all), graded via
   measure_forward_outcome(). Reports the full distribution, not just the
   mean -- criterion 4 specifically wants the 95th percentile.
3. Naive momentum -- on each sampled date, buy whichever universe ticker
   had the best trailing price return over a lookback window, hold a
   fixed period, no target/stop at all (pure price momentum, the
   "would simple trend-following alone have done just as well" bar).
===============================================================================
"""
from __future__ import annotations

import random as _random

import pandas as pd

from backtesting.outcome_measurement import measure_forward_outcome
from config import ROUND_TRIP_COST_PCT


def nifty_buy_hold(benchmark_history: pd.DataFrame, start_date: pd.Timestamp, end_date: pd.Timestamp) -> dict:
    ordered = benchmark_history.sort_values("Date")
    window = ordered[(ordered["Date"] >= start_date) & (ordered["Date"] <= end_date)]

    if len(window) < 2:
        return {"total_return_pct": 0.0, "net_return_pct": 0.0, "cagr_pct": 0.0, "n_days": len(window)}

    start_price = window["Close"].iloc[0]
    end_price = window["Close"].iloc[-1]
    total_return_pct = (end_price - start_price) / start_price * 100
    net_return_pct = total_return_pct - ROUND_TRIP_COST_PCT * 100  # one round trip, buy once and hold

    days = (window["Date"].iloc[-1] - window["Date"].iloc[0]).days
    years = days / 365.25
    cagr_pct = ((end_price / start_price) ** (1 / years) - 1) * 100 if years > 0 else 0.0

    return {
        "total_return_pct": round(total_return_pct, 2),
        "net_return_pct": round(net_return_pct, 2),
        "cagr_pct": round(cagr_pct, 2),
        "n_days": len(window),
    }


def random_entry_control(
    universe_histories: dict[str, pd.DataFrame],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    target_pct: float,
    stop_pct: float,
    k: int = 100,
    max_holding_days: int = 20,
    seed: int = 42,
) -> pd.DataFrame:
    """K draws of (ticker, entry_date) uniformly at random from the same
    universe/window run #1 used, each priced with the SAME target_pct/
    stop_pct distance a real signal typically used (callers should pass
    the actual median from run #1's episodes, not an arbitrary guess), then
    graded via measure_forward_outcome() -- no pattern/score/regime logic
    anywhere in this path."""
    rng = _random.Random(seed)
    tickers = [t for t, h in universe_histories.items() if not h.empty]

    if not tickers:
        return pd.DataFrame(columns=["ticker", "entry_date", "return_pct", "net_return_pct", "exit_reason"])

    rows = []
    attempts = 0
    max_attempts = k * 20  # generous ceiling so a sparse/short-history universe can't spin forever

    while len(rows) < k and attempts < max_attempts:
        attempts += 1
        ticker = rng.choice(tickers)
        history = universe_histories[ticker].sort_values("Date")
        in_window = history[(history["Date"] >= start_date) & (history["Date"] <= end_date)]

        if in_window.empty:
            continue

        entry_row = in_window.sample(n=1, random_state=rng.randint(0, 2**31)).iloc[0]
        entry_date, entry_price = entry_row["Date"], entry_row["Close"]
        target = entry_price * (1 + target_pct / 100)
        stop_loss = entry_price * (1 - stop_pct / 100)

        outcome = measure_forward_outcome(entry_date, entry_price, stop_loss, target, history, max_holding_days)

        if outcome["exit_reason"] == "NO_DATA":
            continue

        net_return_pct = outcome["return_pct"] - ROUND_TRIP_COST_PCT * 100
        rows.append({
            "ticker": ticker, "entry_date": entry_date,
            "return_pct": outcome["return_pct"], "net_return_pct": net_return_pct,
            "exit_reason": outcome["exit_reason"],
        })

    return pd.DataFrame(rows)


def summarize_random_control(draws: pd.DataFrame) -> dict:
    if draws.empty:
        return {"n": 0, "mean_net_return_pct": 0.0, "p50_net_return_pct": 0.0, "p95_net_return_pct": 0.0}

    return {
        "n": len(draws),
        "mean_net_return_pct": round(draws["net_return_pct"].mean(), 2),
        "p50_net_return_pct": round(draws["net_return_pct"].quantile(0.50), 2),
        "p95_net_return_pct": round(draws["net_return_pct"].quantile(0.95), 2),
        "win_rate_pct": round((draws["net_return_pct"] > 0).mean() * 100, 1),
    }


def naive_momentum_baseline(
    universe_histories: dict[str, pd.DataFrame],
    sample_dates: list[pd.Timestamp],
    lookback_days: int = 63,
    max_holding_days: int = 20,
) -> pd.DataFrame:
    """On each date, buys whichever universe ticker had the single best
    trailing `lookback_days`-bar return -- no target/stop, no pattern, no
    regime/sector input, just raw price momentum -- then holds for a fixed
    max_holding_days and records the plain forward return. The bar for
    "does the strategy's pattern/score/ceiling machinery add anything
    beyond just chasing whatever already went up"."""
    rows = []

    for as_of_date in sample_dates:
        best_ticker, best_momentum = None, None

        for ticker, history in universe_histories.items():
            truncated = history[history["Date"] <= as_of_date].sort_values("Date")
            if len(truncated) < lookback_days + 1:
                continue

            past_price = truncated["Close"].iloc[-lookback_days - 1]
            current_price = truncated["Close"].iloc[-1]
            if past_price == 0:
                continue

            momentum = (current_price - past_price) / past_price
            if best_momentum is None or momentum > best_momentum:
                best_ticker, best_momentum = ticker, momentum

        if best_ticker is None:
            continue

        history = universe_histories[best_ticker].sort_values("Date")
        entry_rows = history[history["Date"] == as_of_date]
        if entry_rows.empty:
            continue

        entry_price = entry_rows.iloc[0]["Close"]
        future = history[history["Date"] > as_of_date].sort_values("Date").head(max_holding_days)
        if future.empty:
            continue

        exit_price = future.iloc[-1]["Close"]
        return_pct = (exit_price - entry_price) / entry_price * 100
        net_return_pct = return_pct - ROUND_TRIP_COST_PCT * 100

        rows.append({
            "as_of_date": as_of_date, "ticker": best_ticker,
            "trailing_momentum_pct": round(best_momentum * 100, 2),
            "return_pct": round(return_pct, 2), "net_return_pct": round(net_return_pct, 2),
        })

    return pd.DataFrame(rows)
