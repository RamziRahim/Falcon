"""
===============================================================================
Falcon AI Swing Trading Platform — Component Diagnostics (Part I-7)
===============================================================================
Script      : component_diagnostics.py
Package     : Backtesting

Per-component episode-level bucketing: for each input that feeds either
compute_score() or the ceiling (confidence score, pattern, market regime,
sector verdict, absorption count), buckets episodes by that input and
reports win_rate/expectancy per bucket plus a monotonicity verdict --
does the input actually predict outcome in the direction its own design
assumes, or is it flat/inverted?

All bucketing operates on episode_builder.py's output (episode level), not
raw signals -- a raw-signal bucketing would let the same resampling
artifact episode_builder.py exists to remove double-count into whichever
bucket that ticker's repeated signal happened to fall in.

-------------------------------------------------------------------------
What run #1's schema does NOT support (reported explicitly, not silently
dropped)
-------------------------------------------------------------------------
RS Rating quintile, MACD signal state, Multiple_Patterns_Confirmed, and
delivery-conviction flag all exist inside categorize()'s candidate dict
during replay (decision_engine/leadership_decision_engine.py's
compute_score()), but backtesting/backtest_runner.py's run_backtest()
never persisted them into trade_records -- only the fields listed in
episode_builder.py's own schema comment made it into
data/backtest_results.csv. Bucketing by these four requires a
run_backtest() schema change, which is an engine change gated to run #2
onward (master execution spec standing rule 3: post-processors run
against run #1's existing CSV without re-running replay). This module
runs every bucketing run #1's actual data supports and lists the rest as
UNAVAILABLE rather than fabricating or silently omitting them.
===============================================================================
"""
from __future__ import annotations

import pandas as pd

from backtesting.backtest_runner import aggregate_by
from decision_engine.leadership_decision_engine import PATTERN_WEIGHTS

RETURN_COLUMN = "net_return_pct"

# Presumed direction of increasing expectancy, left to right, per each
# input's own design intent (see leadership_decision_engine.py's
# comments) -- monotonicity is checked against this order, not assumed.
CATEGORY_ORDER = ["ALERT_WATCHLIST", "EXECUTE"]  # AVOID not recorded in run #1, see A-1
REGIME_ORDER = ["UNFAVORABLE", "CAUTION", "FAVORABLE"]
SECTOR_VERDICT_ORDER = ["WEAK", "NEUTRAL", "STRONG"]
# Descending by PATTERN_WEIGHTS -- best-defined/most-rigorous pattern first,
# "no pattern fired" last. Expectancy is expected to decrease along this
# order if the weighting is justified.
PATTERN_ORDER = [name for name, _ in PATTERN_WEIGHTS] + [None]

UNAVAILABLE_IN_RUN_1 = [
    "RS Rating quintile",
    "MACD signal state",
    "Multiple_Patterns_Confirmed",
    "delivery-conviction flag",
]


def _monotonicity_verdict(ordered_expectancies: list[float]) -> str:
    """Only judges the labels actually present (missing labels, e.g. AVOID
    in run #1, are simply absent from the comparison, not treated as a
    break in monotonicity)."""
    if len(ordered_expectancies) < 2:
        return "N/A (fewer than 2 buckets present)"

    diffs = [b - a for a, b in zip(ordered_expectancies, ordered_expectancies[1:])]

    if all(d >= 0 for d in diffs) and any(d > 0 for d in diffs):
        return "monotonically increasing"
    if all(d <= 0 for d in diffs) and any(d < 0 for d in diffs):
        return "monotonically decreasing"
    if all(d == 0 for d in diffs):
        return "flat (no variation)"
    return "NOT monotonic (inversion present)"


def bucket_by_ordered_column(episodes: pd.DataFrame, column: str, order: list) -> dict:
    """Generic ordered-categorical bucketing (regime, sector verdict,
    category, pattern) -- groups by `column`, reports stats via the same
    aggregate_by() the rest of the codebase uses, then checks monotonicity
    against `order` using only the labels actually present."""
    table = aggregate_by(episodes, column, return_column=RETURN_COLUMN)

    if table.empty:
        return {"table": table, "monotonicity": "N/A (no episodes)"}

    stats_by_label = dict(zip(table["group"], table["expectancy_pct"]))
    present_in_order = [label for label in order if label in stats_by_label]
    ordered_expectancies = [stats_by_label[label] for label in present_in_order]

    return {
        "table": table,
        "order_checked": present_in_order,
        "monotonicity": _monotonicity_verdict(ordered_expectancies),
    }


def bucket_by_confidence_decile(episodes: pd.DataFrame, n_bins: int = 10) -> dict:
    """Deciles of confidence_score (episode level). Duplicate bin edges are
    dropped (pd.qcut(duplicates='drop')) rather than raised as an error --
    run #1 has a real cluster of scores clamped at exactly 100.0 (compute_score()'s
    own clamp), which collapses the top bin(s)."""
    if episodes.empty:
        return {"table": pd.DataFrame(), "monotonicity": "N/A (no episodes)"}

    working = episodes.copy()
    working["confidence_decile"] = pd.qcut(
        working["confidence_score"], q=n_bins, duplicates="drop"
    )

    table = aggregate_by(working, "confidence_decile", return_column=RETURN_COLUMN)
    # aggregate_by groups via pandas groupby, which already sorts Interval
    # categories in ascending order -- low score first, high score last.
    ordered_expectancies = list(table["expectancy_pct"])

    return {
        "table": table,
        "monotonicity": _monotonicity_verdict(ordered_expectancies),
    }


def bucket_by_absorption_count(episodes: pd.DataFrame) -> dict:
    """n_signals_absorbed, capped at 3+ (run #1's max was 4) -- exploratory,
    no presumed direction (episode_builder.py's own docstring makes no
    claim that more absorption implies a better or worse trade), so no
    monotonicity check against a fixed order is applied; the table alone
    is reported for inspection."""
    if episodes.empty:
        return {"table": pd.DataFrame()}

    working = episodes.copy()
    working["absorption_bucket"] = working["n_signals_absorbed"].apply(
        lambda n: "3+" if n >= 3 else str(n)
    )
    table = aggregate_by(working, "absorption_bucket", return_column=RETURN_COLUMN)
    return {"table": table}


def run_component_diagnostics(episodes: pd.DataFrame) -> dict:
    return {
        "category": bucket_by_ordered_column(episodes, "category", CATEGORY_ORDER),
        "confidence_decile": bucket_by_confidence_decile(episodes),
        "pattern_used": bucket_by_ordered_column(episodes, "pattern_used", PATTERN_ORDER),
        "market_regime_verdict": bucket_by_ordered_column(episodes, "market_regime_verdict", REGIME_ORDER),
        "sector_health_verdict": bucket_by_ordered_column(episodes, "sector_health_verdict", SECTOR_VERDICT_ORDER),
        "n_signals_absorbed": bucket_by_absorption_count(episodes),
        "unavailable_in_run_1": UNAVAILABLE_IN_RUN_1,
    }


def print_component_diagnostics(episodes: pd.DataFrame) -> None:
    results = run_component_diagnostics(episodes)

    print("\n" + "=" * 78)
    print("  COMPONENT DIAGNOSTICS (episode level, net_return_pct)")
    print("=" * 78)

    for key in ("category", "confidence_decile", "pattern_used", "market_regime_verdict", "sector_health_verdict"):
        result = results[key]
        print(f"\n --- {key} ---")
        for _, row in result["table"].iterrows():
            print(
                f"   {row['group']}: n={row['sample_size']}, win_rate={row['win_rate_pct']}%, "
                f"avg_return={row['avg_return_pct']}%, expectancy={row['expectancy_pct']}%"
            )
        print(f"   monotonicity: {result['monotonicity']}")

    print("\n --- n_signals_absorbed (exploratory, no presumed direction) ---")
    for _, row in results["n_signals_absorbed"]["table"].iterrows():
        print(
            f"   {row['group']}: n={row['sample_size']}, win_rate={row['win_rate_pct']}%, "
            f"avg_return={row['avg_return_pct']}%, expectancy={row['expectancy_pct']}%"
        )

    print("\n --- NOT AVAILABLE in run #1's schema (requires run #2) ---")
    for item in results["unavailable_in_run_1"]:
        print(f"   - {item}")

    print("=" * 78 + "\n")
