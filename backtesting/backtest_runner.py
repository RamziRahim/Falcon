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

import time
from collections import defaultdict

import pandas as pd

from common.logger import get_logger
from backtesting.replay_engine import build_scored_universe_as_of, replay_decision_as_of
from backtesting.outcome_measurement import measure_forward_outcome
from decision_engine.leadership_decision_engine import get_best_pattern_points
from scoring.sector_map import sector_map

logger = get_logger(__name__)

SIGNAL_CATEGORIES = ("EXECUTE", "ALERT_WATCHLIST")


def populate_sector_cache(universe: list[str]) -> None:
    """
    Force-fetches and caches the sector for every ticker in the backtest
    universe before the replay loop starts.

    Real gap this closes: sector_map.py's 30-day cache (data/sector_map.json)
    is populated lazily, one ticker at a time, whenever get_sector() first
    gets called for it -- for a backtest universe assembled from
    backtesting.universe_builder (Nifty 50 + Midcap 150) that's never been
    scanned live before, that cache starts empty. Without pre-populating
    it, every sector lookup during the replay loop would return "Unknown"
    on its first (uncached) call within that run, silently breaking sector
    health verdicts, sector RS ranking, and Pct_Uptrend grouping for most
    of the universe -- not a crash, just quietly wrong data.

    One-time step, not something that runs per replay date: sector_map's
    own cache already has a 30-day refresh interval, so calling this once
    before the loop starts is sufficient for the whole backtest run.
    """
    for ticker in universe:
        sector = sector_map.get_sector(ticker)
        if sector == "Unknown":
            logger.warning("No sector data for %s -- will be grouped as Unknown", ticker)


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
    sector_index_histories: dict | None = None,
    enable_microstructure_signals: bool = False,
) -> pd.DataFrame:
    """
    Returns one row per signal generated (Part C's schema) across every
    ticker in universe_histories, sampled every sample_every_n_days
    trading days between start_date and end_date.

    Universe-wide RS/sector scoring (build_scored_universe_as_of) is
    computed once per distinct sampled date and reused across every
    ticker sampled on that date -- not once per (ticker, date) pair --
    since it's the same answer for all of them at a fixed as_of_date.

    sector_index_histories : dict[Sector label -> full sector index
        OHLCV history], pre-fetched once by the caller (e.g. one
        scoring.sector_indices.get_sector_index_history() call per
        distinct sector actually present in universe_histories, after
        populate_sector_cache() has warmed the sector lookup cache) --
        threaded through to every replay_decision_as_of() call so RS
        Rating and sector health verdicts are sector-index-anchored, not
        the old small-universe peer-percentile/breadth-proxy versions.
        None degrades gracefully (see build_scored_universe_as_of() and
        scoring.sector_indices.get_sector_index_trend()), not a crash.
    enable_microstructure_signals : passed straight through to every
        replay_decision_as_of() call, which passes it straight through to
        categorize() -- see that function's own docstring for what it
        actually does. Defaults to False (identical behavior to every
        prior backtest run).
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
    sorted_dates = sorted(dates_to_tickers.keys())
    total_dates = len(sorted_dates)
    run_started_at = time.monotonic()

    for date_index, as_of_date in enumerate(sorted_dates):

        # Computed from this run's own observed pace, not a hardcoded guess --
        # replay speed depends on universe size/host machine, so a fixed
        # "~70 minutes" estimate is wrong as soon as either changes.
        if date_index > 0 and date_index % 10 == 0:
            elapsed = time.monotonic() - run_started_at
            per_date = elapsed / date_index
            remaining = per_date * (total_dates - date_index)
            logger.info(
                "Progress: %d/%d sampled dates (%.1fs elapsed, ~%.1fs remaining)",
                date_index, total_dates, elapsed, remaining,
            )

        universe_scoring = build_scored_universe_as_of(
            as_of_date, universe_histories, benchmark_history, sector_index_histories,
        )

        for ticker in dates_to_tickers[as_of_date]:

            full_history = universe_histories[ticker]

            decision = replay_decision_as_of(
                ticker=ticker,
                as_of_date=as_of_date,
                full_history=full_history,
                benchmark_history=benchmark_history,
                universe_histories=universe_histories,
                vix_history=vix_history,
                sector_index_histories=sector_index_histories,
                precomputed_universe_scoring=universe_scoring,
                enable_microstructure_signals=enable_microstructure_signals,
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


def _group_stats(group_value, group_df: pd.DataFrame, return_column: str = "return_pct") -> dict:
    """return_column defaults to the raw-signal-level schema's return_pct;
    episode-level callers (episode_builder.py's output) pass
    gross_return_pct/net_return_pct instead -- same win/loss/expectancy
    math either way, just reading a different column."""
    n = len(group_df)

    if n == 0:
        return {
            "group": group_value, "sample_size": 0, "win_rate_pct": 0.0,
            "avg_return_pct": 0.0, "avg_win_pct": 0.0, "avg_loss_pct": 0.0, "expectancy_pct": 0.0,
        }

    wins = group_df[group_df[return_column] > 0]
    losses = group_df[group_df[return_column] <= 0]  # includes exact breakeven -- see compute_expectancy's note

    win_rate = len(wins) / n
    loss_rate = 1 - win_rate
    avg_win = wins[return_column].mean() if not wins.empty else 0.0
    avg_loss = losses[return_column].mean() if not losses.empty else 0.0

    return {
        "group": group_value,
        "sample_size": n,
        "win_rate_pct": round(win_rate * 100, 1),
        "avg_return_pct": round(group_df[return_column].mean(), 2),
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "expectancy_pct": round(compute_expectancy(win_rate, avg_win, loss_rate, avg_loss), 2),
    }


def aggregate_by(trades: pd.DataFrame, group_column: str, return_column: str = "return_pct") -> pd.DataFrame:
    """
    Per-group breakdown (category / pattern_used / market_regime_verdict):
    win rate, avg return, avg win/loss (not blended -- win/loss asymmetry
    win rate alone hides), expectancy, and sample_size reported prominently
    next to every stat, not just left implicit in the row count -- a 71%
    win rate on 7 trades means nothing.
    """
    empty_result = pd.DataFrame(columns=[
        "group", "sample_size", "win_rate_pct", "avg_return_pct",
        "avg_win_pct", "avg_loss_pct", "expectancy_pct",
    ])

    if trades.empty:
        return empty_result

    rows = [
        _group_stats(group_value, group_df, return_column)
        # dropna=False -- a NaN group (e.g. pattern_used is NaN for every
        # episode where no pattern fired, 622 of 797 in run #1) is real
        # data, not something to silently discard from the breakdown.
        for group_value, group_df in trades.groupby(group_column, observed=True, dropna=False)
    ]
    # groupby(dropna=True, the pandas default) silently drops an all-NaN
    # group -- e.g. qcut() on a single-row/no-variance input can produce one
    # NaN-category row with zero real groups. rows=[] then would otherwise
    # produce a DataFrame with no columns at all (not just no rows), which
    # crashes any caller indexing into "expectancy_pct" etc.
    if not rows:
        return empty_result
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


def _ceiling_cause(row) -> str:
    """Why a score>=65 (EXECUTE-grade) signal ended up ALERT_WATCHLIST --
    mirrors get_ceiling()'s own branching in leadership_decision_engine.py.
    Backtest replay always calls categorize() with
    disable_fundamental_signals=True (replay_engine.py), which skips
    INDEPENDENT_CAPS/EARNINGS_PROXIMITY entirely -- so market/sector
    verdict is the only possible cause of a cap in this dataset, never
    caps_applied."""
    if row["market_regime_verdict"] == "UNFAVORABLE":
        return "UNFAVORABLE market"
    return f"CAUTION market + {row['sector_health_verdict']} sector"


def aggregate_ceiling_attribution(
    trades: pd.DataFrame, execute_score_threshold: float = 65.0, return_column: str = "return_pct"
) -> dict:
    """
    Splits every ALERT_WATCHLIST row into two populations:
      - "capped": confidence_score >= execute_score_threshold -- scored
        EXECUTE-grade but the market/sector ceiling (get_ceiling() in
        leadership_decision_engine.py) pulled the final category down to
        ALERT_WATCHLIST anyway.
      - "genuine": confidence_score < execute_score_threshold -- would
        have landed on ALERT_WATCHLIST regardless of any ceiling.

    This is the load-bearing distinction for the signal-scarcity question
    (EXECUTE producing far too few trades to validate or deploy): if the
    "capped" population's outcomes resemble EXECUTE's, the fix is trading
    the ceiling at reduced size (an exposure-scaling policy) rather than
    lowering compute_score()'s EXECUTE threshold -- loosening the score
    would let the genuinely weaker "genuine" population through too.

    return_column: "return_pct" for the raw signal-level schema (default,
    preserves the original signal-level table), or
    "gross_return_pct"/"net_return_pct" to run this same attribution on
    episode_builder.py's episode-level output instead (Phase 1.2 "ceiling
    attribution v2" -- the raw-signal-level version overstates every
    population's n by however much a resampling artifact re-fires the
    same open trade, so the episode-level numbers are the ones that
    actually inform Gate 1).
    """
    watchlist = trades[trades["category"] == "ALERT_WATCHLIST"]

    capped = watchlist[watchlist["confidence_score"] >= execute_score_threshold]
    genuine = watchlist[watchlist["confidence_score"] < execute_score_threshold]
    execute = trades[trades["category"] == "EXECUTE"]

    by_cause = pd.DataFrame()
    if not capped.empty:
        causes = capped.apply(_ceiling_cause, axis=1)
        by_cause = pd.DataFrame([
            _group_stats(cause, capped[causes == cause], return_column) for cause in causes.unique()
        ])

    return {
        "capped": _group_stats(f"capped (score >= {execute_score_threshold})", capped, return_column),
        "genuine": _group_stats(f"genuine (score < {execute_score_threshold})", genuine, return_column),
        "execute": _group_stats("EXECUTE (for comparison)", execute, return_column),
        "by_cause": by_cause,
    }


def print_ceiling_attribution(
    trades: pd.DataFrame,
    execute_score_threshold: float = 65.0,
    low_sample_threshold: int = 20,
    return_column: str = "return_pct",
) -> None:
    """Ceiling-attribution table: of every ALERT_WATCHLIST signal, how many
    scored EXECUTE-grade (>=65) but were capped by the regime/sector
    ceiling vs how many genuinely scored 40-64. Answers whether EXECUTE's
    scarcity (see BY CATEGORY above) is a scoring problem or a ceiling
    problem -- see aggregate_ceiling_attribution()'s docstring."""
    if trades.empty or "ALERT_WATCHLIST" not in trades["category"].values:
        return

    attribution = aggregate_ceiling_attribution(trades, execute_score_threshold, return_column)

    print("\n --- CEILING ATTRIBUTION (ALERT_WATCHLIST breakdown) ---")
    for key in ("capped", "genuine", "execute"):
        row = attribution[key]
        flag = "  [LOW SAMPLE SIZE -- interpret with caution]" if row["sample_size"] < low_sample_threshold else ""
        print(
            f"   {row['group']}: n={row['sample_size']}, win_rate={row['win_rate_pct']}%, "
            f"avg_return={row['avg_return_pct']}%, avg_win={row['avg_win_pct']}%, "
            f"avg_loss={row['avg_loss_pct']}%, expectancy={row['expectancy_pct']}%{flag}"
        )

    if not attribution["by_cause"].empty:
        print("\n   capped-by-cause:")
        for _, row in attribution["by_cause"].iterrows():
            flag = "  [LOW SAMPLE SIZE -- interpret with caution]" if row["sample_size"] < low_sample_threshold else ""
            print(
                f"     {row['group']}: n={row['sample_size']}, win_rate={row['win_rate_pct']}%, "
                f"avg_return={row['avg_return_pct']}%, expectancy={row['expectancy_pct']}%{flag}"
            )


def print_backtest_summary(trades: pd.DataFrame, low_sample_threshold: int = 20) -> None:
    """Console dashboard, same style as pattern_engine.py's metrics
    printout -- flags low sample sizes explicitly rather than letting a
    striking win rate on a handful of trades speak for itself."""
    print("\n" + "=" * 60)
    print("           FALCON BACKTEST RESULTS SUMMARY               ")
    print("=" * 60)
    print(
        " Universe construction: curated list from current screens, not a\n"
        " point-in-time historical constituent list -- tickers that were\n"
        " delisted/renamed/merged out of the index over the backtest window\n"
        " are absent. Every count and stat below is a survivorship-biased\n"
        " upper bound, not an unconditional estimate."
    )
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

    print_ceiling_attribution(trades, low_sample_threshold=low_sample_threshold)

    print("=" * 60 + "\n")
