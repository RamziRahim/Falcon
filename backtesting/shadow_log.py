"""
===============================================================================
Falcon AI Swing Trading Platform — UNFAVORABLE Shadow Log (Gate 1 decision #2)
===============================================================================
Script      : shadow_log.py
Package     : Backtesting

Gate 1 decision #2: UNFAVORABLE-capped signals (score >= 65, blocked by
the market ceiling because market_regime_verdict == "UNFAVORABLE") stay
BLOCKED for real entries in run #2 -- data/gate1_report.md's own clustering
check (n=25 across 6 of 8 contiguous UNFAVORABLE periods) was encouraging
but still too thin to size real risk on. Rather than making that call on
a hunch, this population is shadow-logged: reported plainly, labeled as
shadow (never real capital, never competes for a real portfolio slot), so
run #2 grows the sample for free and Gate 2 gets a data-driven answer
instead of a guess.

Deliberately NOT a portfolio-level equity curve: that would imply this
population competing for capital/slots against real trades, which is
exactly the question still open (decision #2 is "not yet," not "yes at
1/4"). This is a plain per-episode stats report plus the underlying
episodes themselves, for Gate 2 to inspect directly -- portfolio_simulator's
policy_caution_half_unfavorable_quarter (variant (c)) already models what
a REAL 1/4-size UNFAVORABLE policy would look like, if and when that
decision is revisited.
===============================================================================
"""
from __future__ import annotations

import pandas as pd

from backtesting.backtest_runner import aggregate_by

SHADOW_RISK_FRACTION = 0.25  # matches variant (c)'s UNFAVORABLE sizing, for reference only -- not applied to real capital here


def shadow_log_unfavorable_capped(
    episodes: pd.DataFrame, execute_score_threshold: float = 65.0, return_column: str = "net_return_pct"
) -> dict:
    """
    Returns {"stats": dict, "episodes": pd.DataFrame} for the UNFAVORABLE-
    capped population: ALERT_WATCHLIST episodes scoring >= execute_score_threshold
    with market_regime_verdict == "UNFAVORABLE". "episodes" is the raw
    subset (for Gate 2 to inspect clustering, dates, tickers directly);
    "stats" is the same win_rate/expectancy breakdown the rest of this
    codebase already uses (backtest_runner.aggregate_by), labeled as shadow.
    """
    watchlist = episodes[episodes["category"] == "ALERT_WATCHLIST"]
    shadow_episodes = watchlist[
        (watchlist["confidence_score"] >= execute_score_threshold)
        & (watchlist["market_regime_verdict"] == "UNFAVORABLE")
    ].copy()

    label = f"SHADOW -- UNFAVORABLE-capped, score>={execute_score_threshold} (not real capital)"
    shadow_episodes["_shadow_group"] = label
    table = aggregate_by(shadow_episodes, "_shadow_group", return_column)

    if table.empty:
        stats = {
            "group": label, "sample_size": 0, "win_rate_pct": 0.0,
            "avg_return_pct": 0.0, "avg_win_pct": 0.0, "avg_loss_pct": 0.0, "expectancy_pct": 0.0,
        }
    else:
        stats = table.iloc[0].to_dict()

    stats["shadow_risk_fraction_for_reference"] = SHADOW_RISK_FRACTION

    return {"stats": stats, "episodes": shadow_episodes.drop(columns=["_shadow_group"])}


def print_unfavorable_shadow_log(episodes: pd.DataFrame, execute_score_threshold: float = 65.0) -> None:
    result = shadow_log_unfavorable_capped(episodes, execute_score_threshold)
    stats = result["stats"]

    print("\n" + "=" * 78)
    print("  UNFAVORABLE SHADOW LOG (Gate 1 decision #2 -- SHADOW ONLY, not real capital)")
    print("=" * 78)
    print(
        f"   {stats['group']}: n={stats['sample_size']}, win_rate={stats['win_rate_pct']}%, "
        f"avg_return={stats['avg_return_pct']}%, expectancy={stats['expectancy_pct']}%"
    )
    print(f"   (for reference only -- variant (c)'s real sizing would be "
          f"{stats['shadow_risk_fraction_for_reference']} risk fraction if ever adopted)")
    print("=" * 78 + "\n")
