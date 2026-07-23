"""
===============================================================================
Falcon AI Swing Trading Platform — Portfolio Simulator (Part I-5)
===============================================================================
Script      : portfolio_simulator.py
Package     : Backtesting

A real portfolio-level simulation on top of episode_builder.py's episode
log: fixed-fractional position sizing (1% of equity risked on a full-size
trade, scaled by whatever risk_fraction a policy assigns) and a fixed
number of concurrent slots, so a signal can be skipped not because its
own category/score was insufficient but because every slot was already
occupied by an earlier, still-open trade -- something
backtest_runner.py's build_equity_curve() explicitly disclaims not
modeling.

-------------------------------------------------------------------------
Sizing model
-------------------------------------------------------------------------
Every episode already carries r_multiple (net_return_pct / planned stop
distance, from episode_builder.py) -- the return a FULL-size (1.0 risk
fraction) position would produce is base_risk_pct * r_multiple. A policy
that assigns risk_fraction=0.5 to a capped signal halves that contribution,
matching the "trade the ceiling at reduced size" exposure-scaling idea
directly (roadmap SS2.1) rather than requiring a second, parallel notion
of position size.

-------------------------------------------------------------------------
Concurrency / slot contention
-------------------------------------------------------------------------
Episodes are considered in episode_start_date order. A slot frees up once
its occupant's episode_end_date is strictly before the candidate's
episode_start_date (same convention episode_builder.py's absorption rule
uses: entry == prior exit means already flat, not still occupied). If
every slot is occupied, the candidate is skipped entirely -- not sized
down, not queued -- and counted as "missed due to slot exhaustion", which
is exactly the opportunity-cost number a wider-net policy (trading more
capped signals) needs to be judged against: taking more trades competes
for the same fixed number of slots.

-------------------------------------------------------------------------
Equity curve
-------------------------------------------------------------------------
Taken episodes are then ordered by episode_end_date (when their outcome
actually resolves) and applied to a single compounding equity value one
at a time -- same convention as build_equity_curve(), extended with
per-trade sizing. This is a standard fixed-fractional approximation for
concurrent positions (each trade risks a fraction of CURRENT equity
regardless of how many other positions are open), not a literal
per-position capital allocation ledger.
===============================================================================
"""
from __future__ import annotations

from typing import Callable

import pandas as pd

RiskPolicy = Callable[[pd.Series], float]


def policy_hard_cap(episode: pd.Series) -> float:
    """Current production behavior: only EXECUTE episodes are ever taken,
    at full size. Every ceiling-capped ALERT_WATCHLIST episode, regardless
    of score, is never traded."""
    return 1.0 if episode["category"] == "EXECUTE" else 0.0


def policy_caution_half_unfavorable_blocked(episode: pd.Series) -> float:
    """EXECUTE at full size; a capped signal (score >= 65) trades at half
    size only when the ceiling cause was CAUTION -- an UNFAVORABLE-capped
    signal is still fully blocked, same as the current hard cap. Covers
    both the master execution spec's variant (b) 'CAUTION at 1/2 risk' and
    variant (d) 'CAUTION 1/2 + UNFAVORABLE blocked' -- they are the same
    rule once UNFAVORABLE's fate is made explicit for (b) too.

    The "capped" branch below only ever applied to a real ALERT_WATCHLIST
    signal when this was written (EXECUTE/ALERT_WATCHLIST were the only
    two categories in play) -- checking confidence_score/regime alone,
    without an explicit category=="ALERT_WATCHLIST" guard, quietly relied
    on that. B-8's MONITOR tier (2.6c) breaks that assumption: a
    no-pattern candidate that would have scored EXECUTE-grade (>=65) is
    downgraded to MONITOR, not ALERT_WATCHLIST, but can still carry
    confidence_score>=65 -- without the explicit guard, a MONITOR row in
    a CAUTION regime would get sized here as if it were a real capped
    signal, directly contradicting decision #4 (no-pattern signals are
    never traded, monitor-only)."""
    if episode["category"] == "EXECUTE":
        return 1.0
    if episode["category"] == "ALERT_WATCHLIST" and episode["confidence_score"] >= 65.0 \
            and episode["market_regime_verdict"] == "CAUTION":
        return 0.5
    return 0.0


def policy_caution_half_unfavorable_quarter(episode: pd.Series) -> float:
    """Variant (c): capped CAUTION signals at half size, capped UNFAVORABLE
    signals at quarter size (rather than fully blocked). See
    policy_caution_half_unfavorable_blocked's docstring for why the
    category=="ALERT_WATCHLIST" guard is required, not optional, now that
    MONITOR (2.6c) exists."""
    if episode["category"] == "EXECUTE":
        return 1.0
    if episode["category"] == "ALERT_WATCHLIST" and episode["confidence_score"] >= 65.0:
        if episode["market_regime_verdict"] == "CAUTION":
            return 0.5
        if episode["market_regime_verdict"] == "UNFAVORABLE":
            return 0.25
    return 0.0


def policy_sector_aware_caution(episode: pd.Series) -> float:
    """New variant (e), added per the human's request after the episode-
    level ceiling attribution showed CAUTION+WEAK-sector (n=14, 1.05%
    expectancy) meaningfully underperforming CAUTION+NEUTRAL (n=49, 2.87%):
    capped CAUTION+NEUTRAL trades at half size, capped CAUTION+WEAK trades
    at quarter size (not excluded outright -- still some edge, just
    smaller than NEUTRAL's), CAUTION+STRONG at half size (STRONG sector in
    a CAUTION market is at least as strong a case as NEUTRAL). UNFAVORABLE
    stays blocked, same as (b)/(d) -- this variant isolates the
    sector-quality question, not the market-regime one.

    See policy_caution_half_unfavorable_blocked's docstring for why the
    category=="ALERT_WATCHLIST" guard is required, not optional, now that
    MONITOR (2.6c) exists -- this is the policy actually wired into run #2
    (2.6a), so the guard matters most here."""
    if episode["category"] == "EXECUTE":
        return 1.0
    if episode["category"] == "ALERT_WATCHLIST" and episode["confidence_score"] >= 65.0 \
            and episode["market_regime_verdict"] == "CAUTION":
        if episode["sector_health_verdict"] == "WEAK":
            return 0.25
        return 0.5  # NEUTRAL or STRONG
    return 0.0


NAMED_POLICIES: dict[str, RiskPolicy] = {
    "a_hard_cap": policy_hard_cap,
    "b_d_caution_half_unfavorable_blocked": policy_caution_half_unfavorable_blocked,
    "c_caution_half_unfavorable_quarter": policy_caution_half_unfavorable_quarter,
    "e_sector_aware_caution": policy_sector_aware_caution,
}


def _select_episodes(episodes: pd.DataFrame, policy: RiskPolicy, n_slots: int) -> tuple[pd.DataFrame, int]:
    working = episodes.copy()
    working["risk_fraction"] = working.apply(policy, axis=1)
    working = working[working["risk_fraction"] > 0]
    # r_multiple is undefined (NaN) only when stop_pct was 0 -- can't size
    # a trade against a zero-width planned risk, so it's excluded from the
    # simulation entirely rather than treated as a free (zero-risk) trade.
    working = working[working["r_multiple"].notna()]

    candidates = working.sort_values("episode_start_date")

    active_exits: list = []
    taken_rows = []
    missed_due_to_slots = 0

    for _, row in candidates.iterrows():
        entry = row["episode_start_date"]
        active_exits = [exit_date for exit_date in active_exits if exit_date > entry]

        if len(active_exits) < n_slots:
            active_exits.append(row["episode_end_date"])
            taken_rows.append(row)
        else:
            missed_due_to_slots += 1

    taken = pd.DataFrame(taken_rows) if taken_rows else working.iloc[0:0]
    return taken, missed_due_to_slots


def _max_drawdown_pct(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max * 100
    return round(drawdown.min(), 2)


def _cagr_pct(equity_curve: pd.DataFrame, starting_equity: float) -> float:
    if equity_curve.empty:
        return 0.0
    days = (equity_curve["exit_date"].iloc[-1] - equity_curve["exit_date"].iloc[0]).days
    if days <= 0:
        return 0.0
    years = days / 365.25
    final_equity = equity_curve["equity"].iloc[-1]
    return round(((final_equity / starting_equity) ** (1 / years) - 1) * 100, 2)


def _monthly_return_dispersion_pct(equity_curve: pd.DataFrame) -> dict:
    if equity_curve.empty:
        return {"std_pct": 0.0, "n_months": 0}

    working = equity_curve.copy()
    working["month"] = working["exit_date"].dt.to_period("M")
    monthly_equity = working.groupby("month")["equity"].last()
    monthly_returns = monthly_equity.pct_change().dropna() * 100

    if monthly_returns.empty:
        return {"std_pct": 0.0, "n_months": len(monthly_equity)}

    return {"std_pct": round(monthly_returns.std(), 2), "n_months": len(monthly_equity)}


def simulate_portfolio(
    episodes: pd.DataFrame,
    policy: RiskPolicy,
    n_slots: int = 5,
    base_risk_pct: float = 1.0,
    starting_equity: float = 100.0,
) -> dict:
    """Runs one policy end-to-end: selection + slot contention ->
    chronological equity curve -> summary stats. episodes must be
    episode_builder.py's output (needs episode_start_date/episode_end_date/
    r_multiple/category/confidence_score/market_regime_verdict/
    sector_health_verdict)."""
    working = episodes.copy()
    working["episode_start_date"] = pd.to_datetime(working["episode_start_date"])
    working["episode_end_date"] = pd.to_datetime(working["episode_end_date"])

    taken, missed_due_to_slots = _select_episodes(working, policy, n_slots)

    total_candidates = len(taken) + missed_due_to_slots
    slot_utilization_pct = round(len(taken) / total_candidates * 100, 1) if total_candidates else 0.0

    if taken.empty:
        equity_curve = pd.DataFrame(columns=["exit_date", "equity"])
    else:
        ordered = taken.sort_values("episode_end_date")
        equity = starting_equity
        rows = []
        for _, row in ordered.iterrows():
            contribution = row["risk_fraction"] * (base_risk_pct / 100) * row["r_multiple"]
            equity *= (1 + contribution)
            rows.append({"exit_date": row["episode_end_date"], "equity": equity})
        equity_curve = pd.DataFrame(rows)

    dispersion = _monthly_return_dispersion_pct(equity_curve)

    return {
        "n_taken": len(taken),
        "n_missed_due_to_slots": missed_due_to_slots,
        "slot_utilization_pct": slot_utilization_pct,
        "final_equity": round(equity_curve["equity"].iloc[-1], 2) if not equity_curve.empty else starting_equity,
        "max_drawdown_pct": _max_drawdown_pct(equity_curve["equity"]) if not equity_curve.empty else 0.0,
        "cagr_pct": _cagr_pct(equity_curve, starting_equity),
        "monthly_return_std_pct": dispersion["std_pct"],
        "n_months": dispersion["n_months"],
        "equity_curve": equity_curve,
    }


def compare_policies(
    episodes: pd.DataFrame, policies: dict[str, RiskPolicy] = NAMED_POLICIES,
    n_slots: int = 5, base_risk_pct: float = 1.0, starting_equity: float = 100.0,
) -> pd.DataFrame:
    """Runs every named policy against the same episode log and returns a
    one-row-per-policy comparison table (drops the equity_curve column --
    callers wanting the curve itself should call simulate_portfolio()
    directly for a single policy)."""
    rows = []
    for name, policy in policies.items():
        result = simulate_portfolio(episodes, policy, n_slots, base_risk_pct, starting_equity)
        rows.append({"policy": name, **{k: v for k, v in result.items() if k != "equity_curve"}})
    return pd.DataFrame(rows)
