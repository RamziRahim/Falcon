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

import json
import random
import time
from collections import defaultdict

import pandas as pd

from common.logger import get_logger
from backtesting.detector_funnel import tally_funnel
from backtesting.portfolio_simulator import policy_sector_aware_caution
from backtesting.replay_engine import build_scored_universe_as_of, replay_decision_as_of
from backtesting.outcome_measurement import measure_forward_outcome
from config import MAX_HOLDING_TRADING_DAYS, MIN_REWARD_RISK
from decision_engine.leadership_decision_engine import get_best_pattern_points, get_entry_target_stop
from scoring.sector_map import sector_map

logger = get_logger(__name__)

# MONITOR (B-8, 2.6c) included here so it gets a REAL forward outcome
# recorded (it has real entry/stop/target pricing, unlike AVOID) --
# "recorded in the backtest, not surfaced as signals" (decision #4) is
# enforced by recommended_risk_fraction always being None for it below and
# by the live dashboard never treating MONITOR as actionable, not by
# excluding it from this backtest log.
SIGNAL_CATEGORIES = ("EXECUTE", "ALERT_WATCHLIST", "MONITOR")


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


def _hypothetical_trade_plan(candidate: dict, pattern_details: dict) -> dict:
    """A-1: categorize() never prices an AVOID decision (entry/stop_loss/
    target are all None) -- there's no real trade to plan. This reuses the
    exact same selection + pricing logic (get_best_pattern_points ->
    get_entry_target_stop) a REAL decision would have used, purely to
    answer "what would have happened if we'd taken this anyway," which is
    what the monotonicity check (EXECUTE > ALERT_WATCHLIST > AVOID,
    docs/backtest_success_criteria.md criterion 2) needs. Never called
    from the live/categorize() path -- backtest-only, analysis-only."""
    _, best_field = get_best_pattern_points(candidate)
    best_result = pattern_details.get(best_field) if best_field else None
    return get_entry_target_stop(candidate, best_field, best_result)


def run_backtest(
    universe_histories: dict,
    benchmark_history: pd.DataFrame,
    vix_history: pd.DataFrame | None,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    sample_every_n_days: int = 5,
    max_holding_days: int = MAX_HOLDING_TRADING_DAYS,
    sector_index_histories: dict | None = None,
    enable_microstructure_signals: bool = False,
    min_reward_risk: float = MIN_REWARD_RISK,
    funnel_counts: dict | None = None,
    avoid_sample_rate: float = 1.0,
    avoid_sample_seed: int = 42,
    checkpoint_path: str | None = None,
    checkpoint_every_n_dates: int = 20,
    resume_trade_records: list | None = None,
    resume_from_date_index: int = 0,
) -> pd.DataFrame:
    """
    Returns one row per signal generated (Part C's schema) across every
    ticker in universe_histories, sampled every sample_every_n_days
    trading days between start_date and end_date.

    avoid_sample_rate (A-1, Phase 2.5): fraction of AVOID decisions to
    record with a HYPOTHETICAL forward outcome (see
    _hypothetical_trade_plan()'s own docstring) -- 1.0 (default) records
    every AVOID candidate, since docs/backtest_success_criteria.md's
    monotonicity criterion (EXECUTE > ALERT_WATCHLIST > AVOID) needs real
    AVOID outcomes to even be testable. If AVOID volume turns out to
    swamp run #2's runtime (AVOID is typically the largest category --
    most candidates get disqualified or score too low), drop this to 0.3;
    every recorded AVOID row then carries sampled_avoid=True so downstream
    analysis knows it's reading a subsample, not the full AVOID
    population, and shouldn't treat its raw count as comparable to
    EXECUTE/ALERT_WATCHLIST's un-sampled ones. Uses a seeded
    random.Random (avoid_sample_seed) for a reproducible run, not the
    global random module.

    funnel_counts (A-4, Phase 2.4): optional dict[str, collections.Counter],
    mutated in place via detector_funnel.tally_funnel() for EVERY (ticker,
    date) evaluation -- including AVOID and NO_DATA outcomes, not just the
    EXECUTE/ALERT_WATCHLIST rows that make it into the returned DataFrame.
    A per-detector precondition-survival count needs every attempt, not
    just the ones that became a trade, or it couldn't answer "how many
    setups cleared the structural bar but never confirmed a breakout."
    None (the default) skips funnel tracking entirely -- existing callers
    that don't pass this see identical behavior to before A-4 existed.

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

    checkpoint_path / checkpoint_every_n_dates (added after a multi-hour
    wide-universe run was killed outright by an environment restart with
    zero recovery -- this function previously held everything in memory
    and only ever wrote a result on a clean return): every
    checkpoint_every_n_dates sampled dates (same cadence as the existing
    progress log above), and once more after the final date, trade_records
    accumulated SO FAR is written to checkpoint_path as a plain CSV
    (full overwrite each time, not an append -- avoids any risk of a
    duplicate-row checkpoint from a partial/interrupted write), plus a
    small `<checkpoint_path>.meta.json` sidecar recording
    last_completed_date_index/last_completed_date/start_date/end_date/
    total_dates. checkpoint_path=None (default) reproduces every prior
    caller's exact behavior -- no new file, no new I/O.

    resume_trade_records / resume_from_date_index: the other half of the
    same recovery -- a caller that has a prior checkpoint passes its
    already-completed rows (prepended to this run's own trade_records) and
    the date_index to resume from (every date before it is skipped
    entirely, not re-computed) rather than starting over from date 0.
    start_date/end_date must be the SAME values the checkpointed run used
    (the checkpoint's own meta.json records them for exactly this reason)
    -- passing today's freshly-recomputed "start_date = today - N days"
    on a later calendar day would silently shift the whole sampling grid
    and misalign the resume point.
    """
    ticker_sample_dates = {
        ticker: _sampled_dates_for_ticker(history, start_date, end_date, sample_every_n_days)
        for ticker, history in universe_histories.items()
    }

    dates_to_tickers = defaultdict(list)
    for ticker, dates in ticker_sample_dates.items():
        for as_of_date in dates:
            dates_to_tickers[as_of_date].append(ticker)

    trade_records = list(resume_trade_records) if resume_trade_records else []
    sorted_dates = sorted(dates_to_tickers.keys())
    total_dates = len(sorted_dates)
    run_started_at = time.monotonic()
    avoid_rng = random.Random(avoid_sample_seed)

    def _write_checkpoint(completed_index: int, completed_date: pd.Timestamp) -> None:
        if checkpoint_path is None:
            return
        pd.DataFrame(trade_records).to_csv(checkpoint_path, index=False)
        with open(f"{checkpoint_path}.meta.json", "w", encoding="utf-8") as fh:
            json.dump({
                "last_completed_date_index": completed_index,
                "last_completed_date": str(completed_date.date()),
                "start_date": str(start_date.date()),
                "end_date": str(end_date.date()),
                "total_dates": total_dates,
            }, fh, indent=2)

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

        if date_index < resume_from_date_index:
            # Already covered by a prior checkpoint (resume_trade_records
            # already carries this date's rows) -- skip the real work, not
            # just the logging, so a resume is actually fast.
            continue

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
                min_reward_risk=min_reward_risk,
            )

            if funnel_counts is not None:
                tally_funnel(funnel_counts, decision.get("detector_funnel"))

            if decision["category"] == "AVOID":
                is_sampled = avoid_sample_rate < 1.0
                if is_sampled and avoid_rng.random() >= avoid_sample_rate:
                    continue

                candidate = decision["supporting_data"]
                pattern_details = decision.get("pattern_details") or {}
                ets = _hypothetical_trade_plan(candidate, pattern_details)
                hypothetical_entry = ets["entry"]

                avoid_outcome = measure_forward_outcome(
                    entry_date=as_of_date,
                    entry_price=hypothetical_entry,
                    stop_loss=ets["stop_loss"],
                    target=ets["target"],
                    full_history=full_history,
                    max_holding_days=ets["max_holding_days"],
                )

                if avoid_outcome["exit_reason"] == "NO_DATA":
                    continue

                trade_records.append({
                    "ticker": ticker,
                    "entry_date": as_of_date,
                    "entry_price": hypothetical_entry,
                    "category": "AVOID",
                    "pattern_used": _pattern_used(candidate),
                    "market_regime_verdict": decision["market_regime_verdict"],
                    "sector_health_verdict": decision["sector_health_verdict"],
                    "exit_date": avoid_outcome["exit_date"],
                    "exit_price": avoid_outcome["exit_price"],
                    "exit_reason": avoid_outcome["exit_reason"],
                    "return_pct": avoid_outcome["return_pct"],
                    "days_held": avoid_outcome["days_held"],
                    "target_pct": ((ets["target"] - hypothetical_entry) / hypothetical_entry) * 100,
                    "stop_pct": ((hypothetical_entry - ets["stop_loss"]) / hypothetical_entry) * 100,
                    # 2.2 (I-6): the hypothetical trade plan's own
                    # provenance -- same fields a real trade carries, so
                    # AVOID rows are analyzable with the same tooling.
                    "stop_provenance": ets["stop_provenance"],
                    "target_provenance": ets["target_provenance"],
                    "proximal_low": ets["proximal_low"],
                    "reward_risk": (
                        (ets["target"] - hypothetical_entry) / (hypothetical_entry - ets["stop_loss"])
                        if (hypothetical_entry - ets["stop_loss"]) > 0 else None
                    ),
                    # A-5: same recency fields a real trade carries.
                    "bars_since_breakout": decision.get("bars_since_breakout"),
                    "breakout_within_last_k_bars": decision.get("breakout_within_last_k_bars", False),
                    "confidence_score": decision["confidence_score"],
                    "caps_applied": ",".join(decision["caps_applied"]),
                    # A-1: True whenever sampling was active for this run at
                    # all -- every AVOID row recorded under a rate < 1.0 is,
                    # by construction, part of a subsample, not the full
                    # AVOID population, regardless of whether this
                    # particular row happened to be the one kept.
                    "sampled_avoid": is_sampled,
                    # 2.6a: not applicable to a signal that was never
                    # priced for real -- exposure scaling only concerns
                    # the ceiling-capped ALERT_WATCHLIST/EXECUTE population.
                    "recommended_risk_fraction": None,
                })
                continue

            if decision["category"] not in SIGNAL_CATEGORIES or decision["entry"] is None:
                continue

            outcome = measure_forward_outcome(
                entry_date=as_of_date,
                entry_price=decision["entry"],
                stop_loss=decision["stop_loss"],
                target=decision["target"],
                full_history=full_history,
                # The trade plan's own max_holding_days (categorize() ->
                # get_entry_target_stop(), 2.1) is the authoritative time
                # stop for this specific decision -- falls back to the
                # function parameter only if a decision dict doesn't carry
                # one (e.g. a test double stubbing categorize()).
                max_holding_days=decision.get("max_holding_days") or max_holding_days,
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
                # 2.2 (I-6): which pricing path categorize() actually took
                # (STRUCTURAL/STRUCTURAL_CLAMPED_TO_ATR_FLOOR-or-CEILING/
                # ATR_FALLBACK_*) and the resulting reward:risk -- already
                # computed by categorize() itself, not re-derived here.
                "stop_provenance": decision.get("stop_provenance"),
                "target_provenance": decision.get("target_provenance"),
                "proximal_low": decision.get("proximal_low"),
                "reward_risk": decision.get("reward_risk"),
                # A-5: for the SELECTED pattern -- None/False when no
                # pattern fired (MONITOR, or an ATR-fallback ALERT_WATCHLIST).
                "bars_since_breakout": decision.get("bars_since_breakout"),
                "breakout_within_last_k_bars": decision.get("breakout_within_last_k_bars", False),
                # categorize() already computes both of these for every
                # decision -- without them, an ALERT_WATCHLIST row is
                # indistinguishable from "genuinely scored low" vs "strong
                # score, capped by the regime/sector ceiling."
                "confidence_score": decision["confidence_score"],
                "caps_applied": ",".join(decision["caps_applied"]),
                "sampled_avoid": False,  # only ever True for AVOID rows, see above
                # 2.6a: the adopted exposure-scaling policy (e), Gate 1
                # decision #1 -- what fraction of full (1% base) risk this
                # signal should size at. 1.0 for EXECUTE; 0.5/0.25/0.0 for
                # a capped ALERT_WATCHLIST depending on regime+sector (see
                # portfolio_simulator.policy_sector_aware_caution's own
                # docstring); 0.0 for a genuinely-scored (<65) or
                # UNFAVORABLE-capped ALERT_WATCHLIST -- UNFAVORABLE stays
                # blocked for real sizing per decision #2, shadow-logged
                # separately (2.6d), not sized here. Always None for
                # MONITOR (2.6c) -- never traded regardless of score/regime,
                # policy_sector_aware_caution's own category=="ALERT_WATCHLIST"
                # guard would already return 0.0 for it, but None is more
                # honest here: 0.0 could be misread as "considered and
                # sized at zero," where MONITOR was never eligible at all.
                "recommended_risk_fraction": (
                    None if decision["category"] == "MONITOR" else policy_sector_aware_caution(decision)
                ),
            })

        if checkpoint_path is not None and (
            (date_index + 1) % checkpoint_every_n_dates == 0 or date_index == total_dates - 1
        ):
            _write_checkpoint(date_index, as_of_date)

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
