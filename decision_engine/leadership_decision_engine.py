"""
===============================================================================
Falcon AI Swing Trading Platform — Leadership Decision Engine (v1)
===============================================================================
Script      : leadership_decision_engine.py
Package     : Decision Engine

Deterministic Tier 1/2/3 categorization for Leadership-strategy candidates
only: EXECUTE / ALERT_WATCHLIST / AVOID, plus entry/target/stop-loss and an
explicit fakeout-risk breakdown, all as a structured packet for the
downstream AI synthesis layer to narrate (not decide).

Emergent and Reversal strategies need their own decision logic later --
Reversal in particular can't reuse this cascade as-is, since VCP (and by
extension most of the continuation-pattern scoring below) structurally
requires an established UPTREND, which a reversal setup by definition
doesn't have yet. This module is scoped to Leadership only; see
"Extensibility" at the bottom for how the sibling engines are meant to
slot in without changing this one.

-------------------------------------------------------------------------
Input contract -- read before wiring real data in
-------------------------------------------------------------------------
This module operates on an already-assembled, already-normalized flat
`candidate` dict. Assembling that dict from the real pipeline (pattern
engine parquet output + fundamental_analysis + scoring modules) is a
separate integration task, NOT built here -- consistent with every other
module in this codebase being built data-first and wired into a decision
layer later. Two concrete gaps worth naming rather than leaving implicit:

1. Naming mismatch, pattern breakout flags: pattern_engine.py persists
   PascalCase columns (Is_VCP_Breakout, Is_Flat_Base_Breakout, ...,
   Has_Active_FVG, Is_Liquidity_Sweep, Multiple_Patterns_Confirmed). This
   module's PATTERN_WEIGHTS below expects lowercase keys (is_vcp_breakout,
   is_flat_base_breakout, ...) directly on `candidate`, matching how this
   feature was specified. Whoever assembles `candidate` needs to map one
   naming convention to the other -- flagged as a fast-follow, not solved
   here, same treatment as the Price_Crossed_Pivot/Breakout_Volume_Confirmed
   gap noted in pattern_engine.py's own history.

2. Naming/type mismatch, fundamentals: fundamental_analysis/corporate_engine.py
   and institutional_engine.py return human-formatted strings ("14.20%",
   "DEBT_FREE") for ROCE/D_E/institutional sponsorship. This module expects
   plain numeric floats (ROCE=14.2, D_E=0.35, institutional_sponsorship_pct=24.5)
   on `candidate` -- its own decision-facing contract, not a re-export of
   those upstream string formats. Converting one to the other is not part
   of this task.

Expected `candidate` keys:
    Trend_State: str                          ("UPTREND"/"DOWNTREND"/"CHOPPY")
    Close: float
    Rel_Vol: float
    D_E: float                                 (debt-to-equity ratio, e.g. 0.35)
    ROCE: float                                (percentage as a plain number, e.g. 14.2)
    RS_Rating: float                           (0-100, real field -- scoring_engine.py)
    RSI_14: float                              (real field -- technical_analysis/indicators/momentum.py)
    ATR_14: float                              (real field -- technical_analysis/indicators/volatility.py)
    Delivery_Pct: float                        (real field -- market_data/providers/nse_provider.py)
    Delivery_Pct_20d_avg: float                (caller-computed rolling average; not yet a
                                                 persisted column anywhere in the pipeline)
    margin_trend_yoy: str | None               ("EXPANDING"/"CONTRACTING"/"FLAT" -- real field,
                                                 fundamental_analysis/corporate_engine.py)
    days_to_earnings: int                      (real field -- corporate_engine.py, default 999)
    institutional_sponsorship_pct: float
    has_buy_activity: bool                     (real field -- fundamental_analysis/deal_activity.py)
    has_active_fvg: bool
    has_liquidity_sweep: bool
    fii_trend / dii_trend / promoter_trend:    "INCREASING"/"DECREASING"/"FLAT"/None
                                                 (real fields -- shareholding_scraper.py; None
                                                 means not yet scraped for this ticker, skip-if-absent)
    is_vcp_breakout / is_flat_base_breakout / is_cup_handle_breakout /
    is_ascending_triangle_breakout / is_bull_flag_breakout: bool
    Multiple_Patterns_Confirmed: bool           (passed straight through from pattern_engine.py,
                                                 kept in its real PascalCase since it's a
                                                 pure passthrough, not a scoring input this
                                                 module owns)

Expected `sector_row` keys (from scoring.sector_rotation.rank_sectors(),
one row for the candidate's own sector, plus one caller-added field):
    Avg_RS_Rating: float, Pct_Uptrend: float, Rank: int,
    Total_Sectors: int   -- NOT a column rank_sectors() returns (each row
    only knows its own Rank, not how many sectors exist in total); the
    caller must add this from len(rank_sectors(...)) before calling in,
    since "top half of ranking" is meaningless without it.

`pattern_details`: dict[str, dict] mapping each PATTERN_WEIGHTS field name
to that pattern's own raw detector result (the dict with "pivot_level"),
so get_entry_target_stop can price off whichever pattern actually won the
selection below.
===============================================================================
"""
from __future__ import annotations

CATEGORY_RANK = {"AVOID": 0, "ALERT_WATCHLIST": 1, "EXECUTE": 2}


def get_market_regime_verdict(vix_regime: str, distribution_day_count: int) -> str:
    """Returns FAVORABLE / CAUTION / UNFAVORABLE.

    Thresholds are reasonable starting points, not yet backtested -- same
    caveat as everywhere else in this project.
    """
    if vix_regime == "ELEVATED" or distribution_day_count >= 6:
        return "UNFAVORABLE"
    if distribution_day_count >= 3:
        return "CAUTION"
    return "FAVORABLE"


def get_sector_health_verdict(sector_row: dict) -> str:
    """Returns STRONG / NEUTRAL / WEAK for the candidate's sector."""
    if sector_row["Pct_Uptrend"] >= 60 and sector_row["Avg_RS_Rating"] >= 60:
        return "STRONG"
    if sector_row["Pct_Uptrend"] < 30 or sector_row["Avg_RS_Rating"] < 40:
        return "WEAK"
    return "NEUTRAL"


def _is_top_half_sector(sector_row: dict) -> bool:
    """"Top half of ranking" needs the total sector count, which a single
    rank_sectors() row doesn't carry on its own -- see Total_Sectors in
    the module docstring's sector_row contract."""
    total = sector_row.get("Total_Sectors")
    rank = sector_row.get("Rank")
    if not total or rank is None:
        return False
    return rank <= total / 2


# `is None or` on each numeric check: candidate_assembler.py's
# _parse_formatted_percentage() legitimately returns None for a
# non-numeric upstream sentinel (e.g. corporate_engine.py's D_E can come
# back as "DEBT_FREE" instead of a number) -- direct `s["ROCE"] < 10.0`
# would raise TypeError comparing None to a float the first time real
# data hit this path. Missing/unparseable fundamental data fails closed
# (disqualifies) rather than silently passing a quality gate whose whole
# point is to filter on that same data.
DISQUALIFIERS = [
    lambda s: s["Trend_State"] != "UPTREND",
    lambda s: s["Rel_Vol"] is None or s["Rel_Vol"] < 0.5,
    lambda s: s["D_E"] is None or s["D_E"] > 0.5,
    lambda s: s["ROCE"] is None or s["ROCE"] < 10.0,
]

INDEPENDENT_CAPS = [
    (lambda s: s["days_to_earnings"] <= 7, "EARNINGS_PROXIMITY"),
]

# Weight ordering reflects how rigorously each pattern's own definition
# constrains what qualifies, not an arbitrary preference -- VCP and
# Cup-Handle require multi-week structural conditions (and, for VCP, a
# genuinely continuous, tested score); Bull Flag's brief window makes it
# the easiest to satisfy coincidentally, hence the lowest weight.
PATTERN_WEIGHTS = [
    ("is_vcp_breakout", 30),
    ("is_cup_handle_breakout", 25),
    ("is_ascending_triangle_breakout", 20),
    ("is_flat_base_breakout", 18),
    ("is_bull_flag_breakout", 15),
]


def get_ceiling(market_verdict: str, sector_verdict: str) -> str:
    if market_verdict == "UNFAVORABLE":
        return "ALERT_WATCHLIST"  # never EXECUTE in a genuinely bad market,
                                    # no matter how good the stock looks
    if market_verdict == "CAUTION":
        # Even in a shaky market, the strongest names in the strongest
        # groups can still work -- but only those. Everything else caps.
        return "EXECUTE" if sector_verdict == "STRONG" else "ALERT_WATCHLIST"
    return "EXECUTE"  # FAVORABLE market -- no market-imposed ceiling


def get_best_pattern_points(candidate: dict) -> tuple[int, str | None]:
    """Takes the single highest-weighted *confirmed breakout* among
    whichever patterns fired -- summing every pattern that fired would
    double-count the same underlying observation as if it were
    independent confirming evidence, which it isn't (a VCP's final,
    tightest contraction wave can easily also technically qualify as a
    flat base)."""
    for field_name, points in PATTERN_WEIGHTS:
        if candidate.get(field_name):
            return points, field_name
    return 0, None


def compute_score(candidate: dict, sector_row: dict) -> float:
    """0-100 base score (clamped), computed once the cascade ceiling from
    Steps 1-2 is already known -- the final category is always the lower
    of this score and that ceiling, never the score in isolation."""
    score = 0.0

    best_points, _ = get_best_pattern_points(candidate)
    score += best_points

    if candidate.get("has_active_fvg"):
        score += 15
    if candidate.get("has_liquidity_sweep"):
        score += 15

    score += (candidate.get("RS_Rating", 0) / 100) * 20

    if candidate.get("institutional_sponsorship_pct", 0) >= 20:
        score += 10
    if _is_top_half_sector(sector_row):
        score += 10
    if candidate.get("has_buy_activity"):
        score += 10

    # Skip-if-absent: None means "not yet scraped," not "flat" -- applying
    # neither bonus nor penalty keeps the score honest about what it
    # actually knows.
    if candidate.get("fii_trend") == "INCREASING":
        score += 15
    if candidate.get("dii_trend") == "INCREASING":
        score += 8
    if candidate.get("promoter_trend") == "INCREASING":
        score += 5
    if candidate.get("promoter_trend") == "DECREASING":
        score -= 15

    if candidate.get("RSI_14", 0) > 70:
        score -= 10
    if candidate.get("margin_trend_yoy") == "CONTRACTING":
        score -= 10
    if sector_row.get("Pct_Uptrend", 100) < 30:
        score -= 15
    if _is_low_delivery_conviction(candidate):
        score -= 15

    return round(max(0.0, min(100.0, score)), 1)


def _is_low_delivery_conviction(candidate: dict) -> bool:
    """True when Delivery_Pct is genuinely below its own 20-day average.
    Both values can legitimately be None (Delivery_Pct_20d_avg isn't
    persisted anywhere in the pipeline yet -- see candidate_assembler.py's
    docstring) -- `.get(key, default)` only falls back to `default` when
    the key is *absent*, not when it's present but None, so a naive
    `candidate.get("Delivery_Pct_20d_avg", 100)` still returns None here
    and crashes the comparison the first time real assembled data hits
    this path (confirmed by tracing a real candidate through categorize()
    end-to-end)."""
    delivery_pct = candidate.get("Delivery_Pct")
    delivery_avg = candidate.get("Delivery_Pct_20d_avg")
    return delivery_pct is not None and delivery_avg is not None and delivery_pct < delivery_avg


def get_fakeout_risk_flags(candidate: dict, sector_row: dict) -> list[str]:
    """Surfaces *why* something might be a fakeout as named flags, not
    just a quieter score.

    WEAK_VOLUME_CONFIRMATION is still absent here even though
    pattern_engine.py now persists the granular Price_Crossed_Pivot/
    Breakout_Volume_Confirmed columns per pattern (the fast-follow this
    docstring used to flag as missing) -- computing it needs to know
    *which* pattern was selected (get_best_pattern_points) and read that
    specific pattern's sub-fields, which candidate_assembler.py doesn't
    yet flatten onto `candidate`. Wiring that through is the remaining
    fast-follow, not solved here.
    """
    flags = []

    if _is_low_delivery_conviction(candidate):
        flags.append("LOW_DELIVERY_CONVICTION")
    if sector_row.get("Pct_Uptrend", 100) < 30.0:
        flags.append("ISOLATED_MOVE_NO_SECTOR_TAILWIND")
    if candidate.get("RSI_14", 0) > 70:
        flags.append("TECHNICALLY_OVEREXTENDED")
    if candidate.get("margin_trend_yoy") == "CONTRACTING":
        flags.append("MARGIN_QUALITY_CONCERN")
    if candidate.get("promoter_trend") == "DECREASING":
        flags.append("PROMOTER_STAKE_DECLINING")

    return flags


def get_entry_target_stop(candidate: dict, best_pattern_field: str | None, best_pattern_result: dict | None) -> dict:
    """Entry prices off whichever pattern was selected via the
    weight-priority logic above, not VCP specifically -- all 5 detectors
    return their own pivot_level.

    Stop-loss and target currently fall back to ATR for ALL 5 patterns:
    none of the 5 detectors return an absolute price-based structural low
    or height, only percentage depths and pivot_level (the high) -- a
    proper measured-move target/stop needs pivot_level minus the
    structural low in real price terms, which isn't available from any
    current detector output. Each detector already computes the relevant
    low as a local variable right next to its depth-percentage
    calculation, so adding it to the returned dict is a small fast-follow,
    not new logic -- worth doing before relying on non-ATR stops/targets
    for real trades.
    """
    if best_pattern_field is None or not best_pattern_result:
        entry = candidate["Close"]
    else:
        entry = best_pattern_result.get("pivot_level", candidate["Close"])

    atr = candidate.get("ATR_14", 0)
    return {
        "entry": entry,
        "stop_loss": entry - 2 * atr,
        "target": entry + 2.5 * atr,
    }


def categorize(candidate: dict, sector_row: dict, market_verdict: str, pattern_details: dict | None = None) -> dict:
    """Full Leadership-strategy decision: disqualifiers first (AVOID
    immediately, regardless of market/sector/score), then the cascade
    ceiling from market + sector verdicts, then the 0-100 score -- the
    final category is always the lower of the score-based result and
    that ceiling, never the score alone.
    """
    pattern_details = pattern_details or {}

    for check in DISQUALIFIERS:
        if check(candidate):
            return {
                "symbol": candidate.get("symbol"),
                "category": "AVOID",
                "market_regime_verdict": market_verdict,
                "sector_health_verdict": None,
                "confidence_score": 0.0,
                "caps_applied": [],
                "fakeout_risk_flags": [],
                "entry": None,
                "stop_loss": None,
                "target": None,
                "supporting_data": candidate,
            }

    sector_verdict = get_sector_health_verdict(sector_row)
    ceiling = get_ceiling(market_verdict, sector_verdict)

    caps_applied = [name for check, name in INDEPENDENT_CAPS if check(candidate)]
    if caps_applied:
        ceiling = min(ceiling, "ALERT_WATCHLIST", key=lambda c: CATEGORY_RANK[c])

    score = compute_score(candidate, sector_row)

    if score < 40:
        score_based_category = "AVOID"
    elif score >= 65:
        score_based_category = "EXECUTE"
    else:
        score_based_category = "ALERT_WATCHLIST"

    final_category = min(score_based_category, ceiling, key=lambda c: CATEGORY_RANK[c])

    if final_category == "AVOID":
        entry = stop_loss = target = None
    else:
        best_points, best_field = get_best_pattern_points(candidate)
        best_result = pattern_details.get(best_field) if best_field else None
        ets = get_entry_target_stop(candidate, best_field, best_result)
        entry, stop_loss, target = ets["entry"], ets["stop_loss"], ets["target"]

    return {
        "symbol": candidate.get("symbol"),
        "category": final_category,
        "market_regime_verdict": market_verdict,
        "sector_health_verdict": sector_verdict,
        "confidence_score": score,
        "caps_applied": caps_applied,
        "fakeout_risk_flags": get_fakeout_risk_flags(candidate, sector_row),
        "multiple_patterns_confirmed": candidate.get("Multiple_Patterns_Confirmed", False),
        "entry": entry,
        "stop_loss": stop_loss,
        "target": target,
        "supporting_data": candidate,
    }


# -------------------------------------------------------------------------
# Extensibility
# -------------------------------------------------------------------------
# emergent_decision_engine.py / reversal_decision_engine.py can live
# alongside this file later, each implementing the same output contract
# (category/market_regime_verdict/sector_health_verdict/confidence_score/
# caps_applied/fakeout_risk_flags/entry/stop_loss/target/supporting_data)
# with different Tier 1/2/3 logic suited to those strategies -- Reversal
# in particular needs its own pattern-selection table entirely, since it
# can't rely on VCP/continuation-pattern breakouts the way this module
# does. This module shouldn't need to change when those get built.
