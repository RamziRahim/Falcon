"""
===============================================================================
Falcon AI Swing Trading Platform — Backtest Runner & Aggregation (Parts C+D)
===============================================================================
Script      : backtest_runner.py
Package     : Backtesting

Part C: the full trade record schema (entry, exit, return_pct, days_held,
planned target/stop distances -- profit/loss %, not just win/loss).

Part D: run_backtest() steps through history every `sample_every_n_days`
per ticker (not every single day -- re-running full detection per ticker
per day is expensive and mostly redundant with the adjacent day's answer;
5 is a starting guess, tune once real runtime is known), replays each
sampled date, measures the outcome for anything EXECUTE/ALERT_WATCHLIST,
and returns one row per signal generated. Plus the aggregation functions
(win rate, avg return, avg win/loss, expectancy, sample size, equity curve)
grouped by category / pattern_used / market_regime_verdict.

run_backtest()'s given spec signature was `(universe, start_date, end_date,
sample_every_n_days)` -- extended here with universe_histories/
benchmark_history/vix_history as explicit parameters, since those have to
come from *somewhere* and the abbreviated spec signature didn't show
where; the caller is expected to have already loaded each ticker's OHLCV
history (e.g. from data/technical/*.parquet), scoring.benchmark.get_benchmark_history(),
and scoring.market_regime.get_vix_history() for the backtest's date range.
===============================================================================
"""
from __future__ import annotations

from collections import defaultdict

import pandas as pd

from backtesting.replay_engine import build_scored_universe_as_of, replay_decision_as_of
from backtesting.outcome_measurement import measure_forward_outcome
from decision_engine.leadership_decision_engine import get_best_pattern_points

SIGNAL_CATEGORIES = ("EXECUTE", "ALERT_WATCHLIST")


def _sampled_dates_for_ticker(
    history: pd.DataFrame, start_date: pd.Timestamp, end_date: pd.Timestamp, sample_every_n_days: int
) -> list:
    ordered = history.sort_values("Date")
    in_range = ordered[(ordered["Date"] >= start_date) & (ordered["Date"] <= end_date)]
    return list(in_range["Date"].iloc[::sample_every_n_days])


def _pattern_used(candidate: dict) -> str | None:
    """Which of the 5 patterns actually won the weight-priority selection
    for this candidate -- reuses leadership_decision_engine's own
    selection logic rather than re-deriving it, so this can never
    disagree with what categorize() itself used to price entry/stop/target."""
    _, field_name = get_best_pattern_points(candidate)
    return field_name


def run_backtest(
    universe_histories: dict,
    benchmark_history: pd.DataFrame,
    vix_history: pd.DataFrame | None,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    sample_every_n_days: int = 5,
    max_holding_days: int = 20,
) -> pd.DataFrame:
    """
    Returns one row per signal generated (Part C's schema) across every
    ticker in universe_histories, sampled every sample_every_n_days
    trading days between start_date and end_date.

    Universe-wide RS/sector scoring (build_scored_universe_as_of) is
    computed once per distinct sampled date and reused across every
    ticker sampled on that date -- not once per (ticker, date) pair --
    since it's the same answer for all of them at a fixed as_of_date.
    """
    ticker_sample_dates = {
        ticker: _sampled_dates_for_ticker(history, start_date, end_date, sample_every_n_days)
        for ticker, history in universe_histories.items()
    }

    dates_to_tickers = defaultdict(list)
    for ticker, dates in ticker_sample_dates.items():
        for as_of_date in dates:
            dates_to_tickers[as_of_date].append(ticker)

    trade_records = []

    for as_of_date in sorted(dates_to_tickers.keys()):

        universe_scoring = build_scored_universe_as_of(as_of_date, universe_histories)

        for ticker in dates_to_tickers[as_of_date]:

            full_history = universe_histories[ticker]

            decision = replay_decision_as_of(
                ticker=ticker,
                as_of_date=as_of_date,
                full_history=full_history,
                benchmark_history=benchmark_history,
                universe_histories=universe_histories,
                vix_history=vix_history,
                precomputed_universe_scoring=universe_scoring,
            )

            if decision["category"] not in SIGNAL_CATEGORIES or decision["entry"] is None:
                continue

            outcome = measure_forward_outcome(
                entry_date=as_of_date,
                entry_price=decision["entry"],
                stop_loss=decision["stop_loss"],
                target=decision["target"],
                full_history=full_history,
                max_holding_days=max_holding_days,
            )

            if outcome["exit_reason"] == "NO_DATA":
                continue

            entry_price = decision["entry"]

            trade_records.append({
                "ticker": ticker,
                "entry_date": as_of_date,
                "entry_price": entry_price,
                "category": decision["category"],
                "pattern_used": _pattern_used(decision["supporting_data"]),
                "market_regime_verdict": decision["market_regime_verdict"],
                "sector_health_verdict": decision["sector_health_verdict"],
                "exit_date": outcome["exit_date"],
                "exit_price": outcome["exit_price"],
                "exit_reason": outcome["exit_reason"],
                "return_pct": outcome["return_pct"],
                "days_held": outcome["days_held"],
                "target_pct": ((decision["target"] - entry_price) / entry_price) * 100,
                "stop_pct": ((entry_price - decision["stop_loss"]) / entry_price) * 100,
                # categorize() already computes both of these for every
                # decision -- without them, an ALERT_WATCHLIST row is
                # indistinguishable from "genuinely scored low" vs "strong
                # score, capped by the regime/sector ceiling."
                "confidence_score": decision["confidence_score"],
                "caps_applied": ",".join(decision["caps_applied"]),
            })

    return pd.DataFrame(trade_records)


def compute_expectancy(win_rate: float, avg_win_pct: float, loss_rate: float, avg_loss_pct: float) -> float:
    """Expectancy = (win_rate x avg_win_pct) + (loss_rate x avg_loss_pct) --
    the single most useful summary number: expected return per trade.
    Mathematically exact (not an approximation) when win_rate + loss_rate
    == 1 and avg_win/avg_loss are means over complementary partitions of
    the same trade set -- this is what aggregate_by() below guarantees by
    construction (loss_rate = 1 - win_rate, avg_loss over every non-winning
    trade including exact breakeven)."""
    return (win_rate * avg_win_pct) + (loss_rate * avg_loss_pct)


def _group_stats(group_value, group_df: pd.DataFrame) -> dict:
    n = len(group_df)

    if n == 0:
        return {
            "group": group_value, "sample_size": 0, "win_rate_pct": 0.0,
            "avg_return_pct": 0.0, "avg_win_pct": 0.0, "avg_loss_pct": 0.0, "expectancy_pct": 0.0,
        }

    wins = group_df[group_df["return_pct"] > 0]
    losses = group_df[group_df["return_pct"] <= 0]  # includes exact breakeven -- see compute_expectancy's note

    win_rate = len(wins) / n
    loss_rate = 1 - win_rate
    avg_win = wins["return_pct"].mean() if not wins.empty else 0.0
    avg_loss = losses["return_pct"].mean() if not losses.empty else 0.0

    return {
        "group": group_value,
        "sample_size": n,
        "win_rate_pct": round(win_rate * 100, 1),
        "avg_return_pct": round(group_df["return_pct"].mean(), 2),
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "expectancy_pct": round(compute_expectancy(win_rate, avg_win, loss_rate, avg_loss), 2),
    }


def aggregate_by(trades: pd.DataFrame, group_column: str) -> pd.DataFrame:
    """
    Per-group breakdown (category / pattern_used / market_regime_verdict):
    win rate, avg return, avg win/loss (not blended -- win/loss asymmetry
    win rate alone hides), expectancy, and sample_size reported prominently
    next to every stat, not just left implicit in the row count -- a 71%
    win rate on 7 trades means nothing.
    """
    if trades.empty:
        return pd.DataFrame(columns=[
            "group", "sample_size", "win_rate_pct", "avg_return_pct",
            "avg_win_pct", "avg_loss_pct", "expectancy_pct",
        ])

    rows = [_group_stats(group_value, group_df) for group_value, group_df in trades.groupby(group_column)]
    return pd.DataFrame(rows)


def build_equity_curve(trades: pd.DataFrame, starting_equity: float = 100.0) -> pd.DataFrame:
    """
    Simple equal-weighted equity curve: trades sorted by entry_date, each
    one compounds the running equity by its own return_pct in sequence.
    A quick visual sanity check, not a real portfolio simulation -- it
    doesn't model overlapping concurrent positions or position sizing,
    both of which a genuine equity curve would need.
    """
    if trades.empty:
        return pd.DataFrame(columns=["entry_date", "equity"])

    ordered = trades.sort_values("entry_date").reset_index(drop=True)

    equity = starting_equity
    curve = []

    for _, trade in ordered.iterrows():
        equity *= (1 + trade["return_pct"] / 100)
        curve.append({"entry_date": trade["entry_date"], "equity": equity})

    return pd.DataFrame(curve)


def print_backtest_summary(trades: pd.DataFrame, low_sample_threshold: int = 20) -> None:
    """Console dashboard, same style as pattern_engine.py's metrics
    printout -- flags low sample sizes explicitly rather than letting a
    striking win rate on a handful of trades speak for itself."""
    print("\n" + "=" * 60)
    print("           FALCON BACKTEST RESULTS SUMMARY               ")
    print("=" * 60)

    if trades.empty:
        print(" No signals generated over this backtest period.")
        print("=" * 60)
        return

    print(f" TOTAL SIGNALS GENERATED : {len(trades)}")

    for label, column in [
        ("BY CATEGORY", "category"),
        ("BY PATTERN USED", "pattern_used"),
        ("BY MARKET REGIME", "market_regime_verdict"),
    ]:
        print(f"\n --- {label} ---")
        breakdown = aggregate_by(trades, column)
        for _, row in breakdown.iterrows():
            flag = "  [LOW SAMPLE SIZE -- interpret with caution]" if row["sample_size"] < low_sample_threshold else ""
            print(
                f"   {row['group']}: n={row['sample_size']}, win_rate={row['win_rate_pct']}%, "
                f"avg_return={row['avg_return_pct']}%, avg_win={row['avg_win_pct']}%, "
                f"avg_loss={row['avg_loss_pct']}%, expectancy={row['expectancy_pct']}%{flag}"
            )

    print("=" * 60 + "\n")
