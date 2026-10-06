"""
Falcon — Trailing-Exit Backtest Experiment (Qullamaggie-style partial + trail)
Run from project root: python tests/run_trailing_exit_experiment.py

Pure post-processing research comparison against run #4's already-validated
episode log -- does NOT touch categorize(), get_entry_target_stop(), or any
live production code. Same entries, same original stop, same universe;
only what happens AFTER entry is recomputed under an alternative exit rule
(backtesting/trailing_exit_simulator.py).

Part 1 (data): data/backtest_results_run4_calibrated_model.csv is run #4's
raw per-signal log (confirmed the canonical file -- it's the exact RAW_PATH
tests/run4_contribution_attribution.py already used to produce
data/run4_taken_episodes_with_contribution.csv, the 59-episode "+82.74%"
headline this project already reports elsewhere). episode_builder.build_episodes()
(existing, unmodified) collapses it into one row per real trade episode --
reused exactly, not reimplemented, so episode identity/boundaries (which
signals count as one continuous position) are held fixed from the
original run. Only each episode's OWN exit outcome is recomputed under
the trailing rule; re-deriving absorption dynamically under a different
exit rule is a materially bigger, separate question this experiment does
not attempt.

Part 3 (replay): for every episode, the original result is carried
forward unchanged (never recomputed); the trailing-exit result is
computed against the real historical daily bars already cached in
data/technical/{ticker}.parquet.

Part 4 (portfolio comparison): both episode sets through the SAME
portfolio_simulator.simulate_portfolio() (policy_hard_cap -- EXECUTE only,
full size, run #4's own canonical policy; 5 slots; 1% base risk; the
existing 0.3% ROUND_TRIP_COST_PCT applied once per episode, same
convention as episode_builder.py -- this experiment does not model a
second selling leg's cost separately for the partial exit).

Part 5 (parameter sensitivity, tuning-split discipline): partial-trigger
and trailing-MA-period variations are evaluated ONLY on entries dated <=
TUNING_SPLIT_END (2025-09-21 -- the exact split boundary already
established for the v2 calibrated model's own tuning/validation split,
see tests/run_v2_calibration_full.py). Slot contention is computed
SEPARATELY within each split (not on the full population then sliced),
since a live trader would never have had validation-split trades
competing for slots during the tuning period. One configuration is
chosen from the tuning-split results alone, then run ONCE against the
validation split as the final, un-iterated read.
"""
import os
import sys

sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from backtesting.episode_builder import build_episodes
from backtesting.portfolio_simulator import _select_episodes, policy_hard_cap, simulate_portfolio
from backtesting.trailing_exit_simulator import simulate_trailing_exit, NO_DATA_RESULT
from config import ROUND_TRIP_COST_PCT, MAX_HOLDING_TRADING_DAYS

RAW_PATH = "data/backtest_results_run4_calibrated_model.csv"
TECHNICAL_DIR = "data/technical"
N_SLOTS = 5
BASE_RISK_PCT = 1.0
STARTING_EQUITY = 100.0
TUNING_SPLIT_END = "2025-09-21"

DEFAULT_PARTIAL_EXIT_GAIN_PCT = 8.0
DEFAULT_PARTIAL_EXIT_FRACTION = 0.5
DEFAULT_TRAILING_MA_PERIOD = 20


# ---------------------------------------------------------------------------
# Part 1: load run #4's existing episode log, no new collection
# ---------------------------------------------------------------------------

def load_raw_trades() -> pd.DataFrame:
    trades = pd.read_csv(RAW_PATH, low_memory=False)
    trades["entry_date"] = pd.to_datetime(trades["entry_date"], format="mixed")
    trades["exit_date"] = pd.to_datetime(trades["exit_date"], format="mixed")
    return trades


def build_original_episodes(trades: pd.DataFrame) -> pd.DataFrame:
    """Reuses episode_builder.build_episodes() exactly as-is (the same
    call tests/run4_contribution_attribution.py already made against this
    same file) -- not a reimplementation of the absorption rule."""
    episodes = build_episodes(trades)
    episodes["episode_start_date"] = pd.to_datetime(episodes["episode_start_date"])
    episodes["episode_end_date"] = pd.to_datetime(episodes["episode_end_date"])
    return episodes


def attach_entry_fields(episodes: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    """episode_builder.py's own output drops entry_price/stop_pct (it only
    needs them internally to derive r_multiple) -- joined back here from
    the raw log by (ticker, entry_date), which is exactly
    (ticker, episode_start_date) for the FOUNDING signal of each episode.
    Confirmed no duplicate (ticker, entry_date) rows exist in the raw log,
    so this join is exact, not approximate."""
    keyed = trades.set_index(["ticker", "entry_date"])[["entry_price", "stop_pct"]]
    idx = pd.MultiIndex.from_arrays([episodes["ticker"], episodes["episode_start_date"]])
    out = episodes.copy()
    out["entry_price"] = keyed["entry_price"].reindex(idx).to_numpy()
    out["stop_pct"] = keyed["stop_pct"].reindex(idx).to_numpy()
    return out


# ---------------------------------------------------------------------------
# Part 3: replay every episode under the trailing-exit rule
# ---------------------------------------------------------------------------

_HISTORY_CACHE: dict[str, pd.DataFrame | None] = {}


def _load_price_history(ticker: str) -> pd.DataFrame | None:
    if ticker not in _HISTORY_CACHE:
        path = os.path.join(TECHNICAL_DIR, f"{ticker}.parquet")
        if not os.path.exists(path):
            _HISTORY_CACHE[ticker] = None
        else:
            df = pd.read_parquet(path)
            df["Date"] = pd.to_datetime(df["Date"])
            _HISTORY_CACHE[ticker] = df.sort_values("Date").reset_index(drop=True)
    return _HISTORY_CACHE[ticker]


# Confirmed live during this experiment (2026-09/10, exact date TBD by
# git log): 10 of 213 episodes have a raw-log entry_price that disagrees
# with data/technical/{ticker}.parquet's own cached Close on the SAME
# date by more than this ratio -- e.g. NAUKRI.NS 2024-09-19: entry_price
# 1494.58 vs cached Close 7902.10 (5.29x). This is the known, still-open
# ~34-ticker price-corruption/stock-split issue (docs/known_data_issues.md
# item #1) showing up concretely here: run #4's raw log captured
# entry_price from whatever data/technical/ state existed when run #4 was
# originally executed, and the cache has since been re-adjusted for a
# real stock split for at least these tickers -- the two numbers are on
# different price bases, not evidence of a real price move. Left
# undetected, this single-handedly fabricates >400% "returns" that are a
# unit-mismatch artifact, not a trailing-exit finding. A real split ratio
# is usually a small integer or its reciprocal (2x, 3x, 5x, 1/2, 1/3...);
# 1.5x/0.67x is a conservative floor below the smallest common split
# (a 3:2 bonus) while still comfortably clearing legitimate large
# single-day/multi-day moves this project's own patterns can produce.
PRICE_BASIS_MISMATCH_RATIO_BOUNDS = (0.67, 1.5)


def _price_basis_mismatch(entry_price: float, entry_date, history: pd.DataFrame) -> bool:
    matches = history.index[history["Date"] == entry_date]
    if len(matches) == 0:
        return False  # NO_DATA path handles this; not this check's job
    cached_close = history.loc[matches[0], "Close"]
    if entry_price in (0, None) or pd.isna(entry_price) or pd.isna(cached_close):
        return False
    ratio = cached_close / entry_price
    low, high = PRICE_BASIS_MISMATCH_RATIO_BOUNDS
    return ratio < low or ratio > high


def filter_price_basis_mismatches(episodes_with_entry_fields: pd.DataFrame) -> pd.DataFrame:
    """Drops any episode whose raw-log entry_price disagrees with
    data/technical/{ticker}.parquet's own cached Close on that same date
    (see PRICE_BASIS_MISMATCH_RATIO_BOUNDS/_price_basis_mismatch above).
    Applied to BOTH sides of the comparison up front (not just inside
    compute_trailing_episodes()) -- the ORIGINAL result is actually
    unaffected by this bug (it's entirely self-contained in run #4's own
    raw log, no dependency on today's price cache), but leaving a
    mismatched episode in the original population while dropping it from
    the trailing-exit population would silently compare two different
    episode sets, not a fair like-for-like read."""
    keep_mask = []
    dropped = []
    for _, row in episodes_with_entry_fields.iterrows():
        history = _load_price_history(row["ticker"])
        if history is not None and _price_basis_mismatch(row["entry_price"], row["episode_start_date"], history):
            keep_mask.append(False)
            dropped.append((row["ticker"], row["episode_start_date"].date(), row["entry_price"]))
        else:
            keep_mask.append(True)

    if dropped:
        print(f"  [price-basis check] excluding {len(dropped)} episode(s) from BOTH sides of the "
              f"comparison -- known stock-split/price-corruption issue "
              f"(docs/known_data_issues.md item #1): {dropped}")

    return episodes_with_entry_fields[keep_mask].reset_index(drop=True)


def _trading_day_offset(history: pd.DataFrame, start_date, end_date) -> float:
    """Trading-day count between two dates already known to be real rows
    in `history` -- matches outcome_measurement.measure_forward_outcome()'s
    own 1-indexed offset convention for days_held."""
    start_matches = history.index[history["Date"] == start_date]
    end_matches = history.index[history["Date"] == end_date]
    if len(start_matches) == 0 or len(end_matches) == 0:
        return np.nan
    return int(end_matches[0] - start_matches[0])


def compute_trailing_episodes(
    episodes_with_entry_fields: pd.DataFrame,
    partial_exit_gain_pct: float = DEFAULT_PARTIAL_EXIT_GAIN_PCT,
    partial_exit_fraction: float = DEFAULT_PARTIAL_EXIT_FRACTION,
    trailing_ma_period: int = DEFAULT_TRAILING_MA_PERIOD,
    max_holding_days: int = MAX_HOLDING_TRADING_DAYS,
) -> pd.DataFrame:
    """Returns a copy of the input with episode_end_date/exit_reason/
    days_held/gross_return_pct/net_return_pct/r_multiple all replaced by
    the trailing-exit rule's own outcome -- every other column (entry-time
    decision context: category, market_regime_verdict, sector_health_verdict,
    confidence_score, pattern_used, caps_applied) is copied through
    unchanged, since this experiment only changes what happens after entry.
    Rows where the real cached price history can't answer the question
    (NO_DATA -- missing ticker file or entry_date not found in it), or
    where entry_price disagrees with the cache's own Close on that date
    by more than a plausible-split ratio (see
    PRICE_BASIS_MISMATCH_RATIO_BOUNDS -- the known, still-open stock-split/
    price-corruption issue, docs/known_data_issues.md item #1), are
    dropped and counted, not silently kept with a fabricated return.
    """
    rows = []
    dropped_no_data = 0
    dropped_price_basis_mismatch = 0

    for _, row in episodes_with_entry_fields.iterrows():
        history = _load_price_history(row["ticker"])
        if history is None:
            dropped_no_data += 1
            continue

        entry_price = row["entry_price"]
        stop_pct = row["stop_pct"]

        if _price_basis_mismatch(entry_price, row["episode_start_date"], history):
            dropped_price_basis_mismatch += 1
            continue

        hard_stop_price = (
            entry_price * (1 - stop_pct / 100)
            if pd.notna(stop_pct) and stop_pct not in (0, None)
            else None
        )

        result = simulate_trailing_exit(
            entry_price=entry_price,
            entry_date=row["episode_start_date"],
            price_history=history,
            partial_exit_gain_pct=partial_exit_gain_pct,
            partial_exit_fraction=partial_exit_fraction,
            trailing_ma_period=trailing_ma_period,
            max_holding_days=max_holding_days,
            hard_stop_price=hard_stop_price,
        )

        if result["remainder_exit_reason"] == "NO_DATA":
            dropped_no_data += 1
            continue

        gross = result["blended_return_pct"]
        net = gross - ROUND_TRIP_COST_PCT * 100
        r_multiple = (net / stop_pct) if pd.notna(stop_pct) and stop_pct not in (0, None) else float("nan")

        new_row = row.copy()
        new_row["episode_end_date"] = result["remainder_exit_date"]
        new_row["exit_reason"] = result["remainder_exit_reason"]
        new_row["days_held"] = _trading_day_offset(
            history, row["episode_start_date"], result["remainder_exit_date"]
        )
        new_row["gross_return_pct"] = gross
        new_row["net_return_pct"] = net
        new_row["r_multiple"] = r_multiple
        new_row["partial_exit_date"] = result["partial_exit_date"]
        new_row["partial_exit_price"] = result["partial_exit_price"]
        new_row["never_hit_partial_trigger"] = result["never_hit_partial_trigger"]
        rows.append(new_row)

    if dropped_no_data:
        print(f"  [trailing-exit replay] dropped {dropped_no_data} episode(s) -- "
              f"no usable cached price history for the entry date.")
    if dropped_price_basis_mismatch:
        print(f"  [trailing-exit replay] dropped {dropped_price_basis_mismatch} episode(s) -- "
              f"entry_price disagrees with the cached technical data's own Close on that "
              f"date by more than {PRICE_BASIS_MISMATCH_RATIO_BOUNDS} (known stock-split/"
              f"price-corruption issue, docs/known_data_issues.md item #1) -- see "
              f"run_trailing_exit_experiment.py's own comment for the exact tickers/dates found.")

    return pd.DataFrame(rows).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Part 4: portfolio-level comparison, same metrics as every other report
# ---------------------------------------------------------------------------

def _avg_winner_pct(episodes: pd.DataFrame, return_col: str = "net_return_pct") -> float:
    winners = episodes[episodes[return_col] > 0]
    return round(winners[return_col].mean(), 2) if len(winners) else 0.0


def _win_rate_pct(episodes: pd.DataFrame, return_col: str = "net_return_pct") -> float:
    if episodes.empty:
        return 0.0
    return round((episodes[return_col] > 0).mean() * 100, 1)


def _concentration(taken: pd.DataFrame) -> dict:
    """What share of the portfolio's total (multiplicative) growth comes
    from its single largest trade, and its top 3 -- same log-growth-sum
    technique as tests/run4_contribution_attribution.py (log-growths sum
    exactly to total log-growth regardless of order, so "share of total
    log-growth" is an exact, not approximate, attribution). A high
    concentration on a small n is itself an honest finding: it means a
    parameter/config comparison built on this population can be decided
    by 2-3 trades, not a stable difference -- exactly what the tuning-split
    ranking flip (baseline 20DMA vs. a 10-day variant) turned out to show."""
    if taken.empty:
        return {"top1_log_growth_share_pct": None, "top3_log_growth_share_pct": None}

    working = taken.copy()
    working["factor"] = 1 + working["risk_fraction"] * (BASE_RISK_PCT / 100) * working["r_multiple"]
    working["log_growth"] = np.log(working["factor"])
    total_log_growth = working["log_growth"].sum()

    if total_log_growth == 0:
        return {"top1_log_growth_share_pct": None, "top3_log_growth_share_pct": None}

    ranked = working.reindex(working["log_growth"].abs().sort_values(ascending=False).index)
    top1_share = ranked["log_growth"].iloc[:1].sum() / total_log_growth * 100
    top3_share = ranked["log_growth"].iloc[:3].sum() / total_log_growth * 100

    return {
        "top1_log_growth_share_pct": round(top1_share, 1),
        "top3_log_growth_share_pct": round(top3_share, 1),
    }


def portfolio_report(label: str, episodes: pd.DataFrame, return_col: str = "net_return_pct") -> dict:
    """Uses _select_episodes() directly (same private helper
    tests/run4_contribution_attribution.py already calls from outside the
    module) to get back the exact taken-episode rows with their own
    exit_reason/net_return_pct -- simulate_portfolio()'s own public return
    value only carries the equity curve (exit_date + equity), which can't
    be joined back to episodes safely when two different episodes share
    the same episode_end_date. Both calls apply the identical
    policy/n_slots, so the taken set is guaranteed identical between the
    two calls -- this isn't a second, possibly-inconsistent selection."""
    working = episodes.copy()
    working["episode_start_date"] = pd.to_datetime(working["episode_start_date"])
    working["episode_end_date"] = pd.to_datetime(working["episode_end_date"])

    taken, missed_due_to_slots = _select_episodes(working, policy_hard_cap, N_SLOTS)

    result = simulate_portfolio(
        episodes, policy_hard_cap, n_slots=N_SLOTS,
        base_risk_pct=BASE_RISK_PCT, starting_equity=STARTING_EQUITY,
    )
    total_return_pct = round(result["final_equity"] - STARTING_EQUITY, 2)
    calmar = round(result["cagr_pct"] / abs(result["max_drawdown_pct"]), 2) \
        if result["max_drawdown_pct"] not in (0.0, None) else None

    return {
        "label": label,
        "n_taken": result["n_taken"],
        "n_missed_due_to_slots": result["n_missed_due_to_slots"],
        "total_return_pct": total_return_pct,
        "max_drawdown_pct": result["max_drawdown_pct"],
        "cagr_pct": result["cagr_pct"],
        "calmar": calmar,
        "avg_winner_pct": _avg_winner_pct(taken, return_col),
        "win_rate_pct": _win_rate_pct(taken, return_col),
        "exit_reason_distribution": taken["exit_reason"].value_counts().to_dict(),
        **_concentration(taken),
    }


def print_comparison(original_report: dict, trailing_report: dict) -> None:
    print("\n" + "=" * 100)
    print("  PORTFOLIO-LEVEL COMPARISON -- ORIGINAL (fixed target/stop) vs TRAILING-EXIT")
    print("=" * 100)
    fields = [
        ("n_taken", "Episodes taken"),
        ("n_missed_due_to_slots", "Missed (slot exhaustion)"),
        ("total_return_pct", "Total return %"),
        ("max_drawdown_pct", "Max drawdown %"),
        ("cagr_pct", "CAGR %"),
        ("calmar", "Calmar"),
        ("avg_winner_pct", "Avg winner (net %)"),
        ("win_rate_pct", "Win rate %"),
    ]
    header = f"{'Metric':<28}{'Original':>18}{'Trailing-Exit':>18}"
    print(header)
    print("-" * len(header))
    for key, name in fields:
        print(f"{name:<28}{str(original_report[key]):>18}{str(trailing_report[key]):>18}")

    print("\nExit-reason distribution (taken episodes only):")
    print(f"  Original:      {original_report['exit_reason_distribution']}")
    print(f"  Trailing-Exit: {trailing_report['exit_reason_distribution']}")

    print("\nConcentration (share of total log-growth from the single largest / top-3 taken trades --"
          " a high share on a small n means the result rests on a handful of trades, not a stable edge):")
    print(f"  Original:      top-1 {original_report['top1_log_growth_share_pct']}%, "
          f"top-3 {original_report['top3_log_growth_share_pct']}%")
    print(f"  Trailing-Exit: top-1 {trailing_report['top1_log_growth_share_pct']}%, "
          f"top-3 {trailing_report['top3_log_growth_share_pct']}%")


# ---------------------------------------------------------------------------
# Part 5: parameter sensitivity, tuning-split discipline
# ---------------------------------------------------------------------------

def _split(episodes: pd.DataFrame, split_end: str = TUNING_SPLIT_END) -> tuple[pd.DataFrame, pd.DataFrame]:
    tuning = episodes[episodes["episode_start_date"] <= split_end].reset_index(drop=True)
    validation = episodes[episodes["episode_start_date"] > split_end].reset_index(drop=True)
    return tuning, validation


def run_sensitivity(episodes_with_entry_fields: pd.DataFrame) -> tuple[dict, dict]:
    tuning_pool, validation_pool = _split(episodes_with_entry_fields)

    variations = [
        {"name": "baseline (8%, 50%, 20DMA)", "partial_exit_gain_pct": 8.0, "trailing_ma_period": 20},
        {"name": "6% partial trigger", "partial_exit_gain_pct": 6.0, "trailing_ma_period": 20},
        {"name": "12% partial trigger", "partial_exit_gain_pct": 12.0, "trailing_ma_period": 20},
        {"name": "10-day trailing MA", "partial_exit_gain_pct": 8.0, "trailing_ma_period": 10},
    ]

    print("\n" + "=" * 100)
    print(f"  PART 5: PARAMETER SENSITIVITY -- TUNING SPLIT ONLY (entered <= {TUNING_SPLIT_END}, n={len(tuning_pool)})")
    print("=" * 100)

    tuning_results = []
    for variant in variations:
        trailing_tuning = compute_trailing_episodes(
            tuning_pool, partial_exit_gain_pct=variant["partial_exit_gain_pct"],
            trailing_ma_period=variant["trailing_ma_period"],
        )
        report = portfolio_report(variant["name"], trailing_tuning)
        tuning_results.append({**variant, **report})

    cols = ["name", "n_taken", "total_return_pct", "max_drawdown_pct", "calmar",
            "avg_winner_pct", "win_rate_pct", "top1_log_growth_share_pct", "top3_log_growth_share_pct"]
    print(pd.DataFrame(tuning_results)[cols].to_string(index=False))

    # Deliberately NOT selecting a "best" config here. A leave-top-3-out
    # robustness check (done once, outside this script, not repeated here
    # as a further peek at the tuning split) showed the baseline-vs-10-day
    # Calmar ranking above FLIPS once the top 3 taken trades are dropped
    # from each (baseline 23.77 -> 13.84; 10-day 25.76 -> 9.30) -- at
    # n=29-31 taken trades, a 2-3-trade robustness check reversing the
    # ranking means this dataset cannot distinguish these configurations.
    # Switching to a "more robust" selection rule now, specifically
    # because the naive one just got embarrassed, would be tuning the
    # TUNING METHOD after seeing it fail -- the same overfitting risk
    # this project guards against everywhere else, one level removed. The
    # top1/top3 concentration columns above make the same point directly:
    # each variant's result rests on a small handful of trades, not a
    # stable difference.
    print(f"\nVERDICT: parameter search is INCONCLUSIVE at this sample size -- NOT '10-day is "
          f"better', NOT '20-day is better'. The ranking is decided by 2-3 outsized trades "
          f"either way (see top1/top3 concentration columns, and the leave-top-3-out check in "
          f"this script's own docstring/comments). No further parameter variations will be run "
          f"against this same tuning split -- that would be additional peeking at data already "
          f"looked at too many times.")

    print("\n" + "=" * 100)
    print(f"  FINAL VALIDATION-SPLIT READ (entered > {TUNING_SPLIT_END}, n={len(validation_pool)}) -- "
          f"BASELINE (8%, 50%, 20DMA) config only, the spec's own pre-registered default, "
          f"NOT a tuned variant -- run ONCE, not iterated on")
    print("=" * 100)
    trailing_validation = compute_trailing_episodes(
        validation_pool, partial_exit_gain_pct=DEFAULT_PARTIAL_EXIT_GAIN_PCT,
        trailing_ma_period=DEFAULT_TRAILING_MA_PERIOD,
    )
    original_validation_report = portfolio_report("Original (validation split)", validation_pool)
    trailing_validation_report = portfolio_report("Trailing-Exit (validation split, baseline config)", trailing_validation)
    print_comparison(original_validation_report, trailing_validation_report)

    return trailing_validation_report


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Loading run #4's raw signal log:", RAW_PATH)
    trades = load_raw_trades()

    print("Building episodes (episode_builder.build_episodes(), unmodified)...")
    original_episodes = build_original_episodes(trades)
    all_episodes_with_entry_fields = attach_entry_fields(original_episodes, trades)
    print(f"  {len(all_episodes_with_entry_fields)} total episodes across all categories "
          f"(AVOID/MONITOR included -- run #4's raw log carries hypothetical outcomes for "
          f"those too, for its own ceiling/gate diagnostics).")

    # Scoped to EXECUTE/ALERT_WATCHLIST -- episode_builder.py's own module
    # docstring confirms only these two ever represent a genuine tradeable
    # signal (run #1's raw schema "only records these two"); policy_hard_cap
    # (Part 4's portfolio policy) can never select an AVOID/MONITOR episode
    # regardless, so simulating a full trailing-exit replay for the other
    # ~15,800 non-tradeable episodes would be pure wasted computation, not
    # a scope narrowing that changes any reported result. Filtered AFTER
    # build_episodes(), not before -- episode identity/absorption is still
    # derived from the FULL raw population, matching
    # tests/run4_contribution_attribution.py's own methodology exactly, so
    # this experiment's episode set is provably the same one run #4 itself
    # produced.
    episodes_with_entry_fields = all_episodes_with_entry_fields[
        all_episodes_with_entry_fields["category"].isin(["EXECUTE", "ALERT_WATCHLIST"])
    ].reset_index(drop=True)
    print(f"  {len(episodes_with_entry_fields)} EXECUTE/ALERT_WATCHLIST episodes -- "
          f"the only ones any portfolio policy in this project can ever select.")

    print("\nChecking entry_price against the cached technical data's own Close "
          "(known stock-split/price-corruption issue, docs/known_data_issues.md item #1)...")
    episodes_with_entry_fields = filter_price_basis_mismatches(episodes_with_entry_fields)
    print(f"  {len(episodes_with_entry_fields)} episodes remain after the price-basis check -- "
          f"used for BOTH the original and trailing-exit comparisons below.")

    print("\nReplaying every episode under the trailing-exit rule "
          f"(default: {DEFAULT_PARTIAL_EXIT_GAIN_PCT}% partial trigger, "
          f"{DEFAULT_PARTIAL_EXIT_FRACTION:.0%} fraction, "
          f"{DEFAULT_TRAILING_MA_PERIOD}-day trailing MA)...")
    trailing_episodes = compute_trailing_episodes(episodes_with_entry_fields)

    merged = episodes_with_entry_fields.merge(
        trailing_episodes[["ticker", "episode_start_date", "episode_end_date", "exit_reason",
                            "days_held", "gross_return_pct", "net_return_pct", "r_multiple",
                            "partial_exit_date", "partial_exit_price", "never_hit_partial_trigger"]],
        on=["ticker", "episode_start_date"], how="inner", suffixes=("_original", "_trailing"),
    )
    merged["delta_net_return_pct"] = merged["net_return_pct_trailing"] - merged["net_return_pct_original"]
    merged.to_csv("data/trailing_exit_episode_comparison.csv", index=False)
    print(f"  Saved full episode-level comparison -> data/trailing_exit_episode_comparison.csv "
          f"({len(merged)} rows)")

    original_report = portfolio_report("Original", episodes_with_entry_fields)
    trailing_report = portfolio_report("Trailing-Exit (default params)", trailing_episodes)
    print_comparison(original_report, trailing_report)

    validation_report = run_sensitivity(episodes_with_entry_fields)

    print("\n" + "=" * 100)
    print("  SUMMARY")
    print("=" * 100)
    print(f"Default-params (8%, 50%, 20DMA) trailing-exit vs original (full population, n_taken="
          f"{trailing_report['n_taken']}/{original_report['n_taken']}): "
          f"total return {trailing_report['total_return_pct']}% vs {original_report['total_return_pct']}%, "
          f"Calmar {trailing_report['calmar']} vs {original_report['calmar']}, "
          f"avg winner {trailing_report['avg_winner_pct']}% vs {original_report['avg_winner_pct']}%.")
    print("Tuning-split parameter search: INCONCLUSIVE at this sample size (see verdict above) -- "
          "no parameter was chosen or carried forward.")
    print(f"Validation-split (out-of-sample, run once, BASELINE config only, n_taken="
          f"{validation_report['n_taken']}): "
          f"total return {validation_report['total_return_pct']}%, Calmar {validation_report['calmar']}, "
          f"avg winner {validation_report['avg_winner_pct']}%.")


if __name__ == "__main__":
    main()
