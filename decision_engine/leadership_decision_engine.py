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
    Delivery_Pct_20d_avg: float                (real field -- pattern_engine.py, rolling
                                                 20-day mean of Delivery_Pct)
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
    macd_signal: "BULLISH_ALIGNMENT"/"BEARISH_DIVERGENCE"/"NEUTRAL"
                                                 (technical_analysis/pattern_system/macd_signal.py's
                                                 get_macd_signal() output)
    liquidity_sweep_direction: "SSL"/"BSL"/None (technical_analysis/liquidity_sweep.py's
                                                 detect_liquidity_sweep() output; only read
                                                 when enable_microstructure_signals=True)
    fvg_direction: "bullish"/"bearish"/None,
    fvg_filled_pct: float | None                (technical_analysis/fair_value_gap.py's
                                                 detect_fvg() output; only read when
                                                 enable_microstructure_signals=True)

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

from config import (
    ATR_STOP_CEILING_MULTIPLE,
    ATR_STOP_FLOOR_MULTIPLE,
    MAX_HOLDING_TRADING_DAYS,
    MIN_REWARD_RISK,
    STOP_BUFFER_ATR_MULTIPLE,
    TARGET_MIN_ATR_MULTIPLE,
)
from scoring.consolidation_quality_model import load_model_artifact, predict_consolidation_quality

# MONITOR (B-8, Gate 1 decision #4): a candidate that scored ALERT_WATCHLIST-
# or-better (>=40) but had NO confirmed pattern at all -- ranked below
# ALERT_WATCHLIST so "pattern presence required for ALERT_WATCHLIST and
# above" holds regardless of how favorable the market/sector ceiling is
# (see categorize()'s own MONITOR downgrade, applied before the ceiling
# min() so a great regime can never lift a pattern-less candidate past
# it). Recorded in the backtest for analysis (data/backtest_results.csv
# via backtest_runner.py's SIGNAL_CATEGORIES); never surfaced as an
# actionable live signal the same way EXECUTE/ALERT_WATCHLIST are.
CATEGORY_RANK = {"AVOID": 0, "MONITOR": 1, "ALERT_WATCHLIST": 2, "EXECUTE": 3}


def get_market_regime_verdict(nifty_trend_state: str, distribution_day_count: int) -> str:
    """Returns FAVORABLE / CAUTION / UNFAVORABLE.

    Trend-based, not VIX-based: backtesting/regime_threshold_calibration.py's
    analyze_vix_vs_forward_returns() found (9.5 years, COVID-excluded) that
    high VIX does NOT precede worse NIFTY forward returns at a 20-day
    horizon -- if anything, mildly the opposite. VIX measures fear/
    volatility, a related but different concept from what O'Neil/Minervini
    "market health" actually means: trend direction. Conflating the two
    was the likely root cause, not a threshold calibration error.

    Replaced with NIFTY's own Trend_State (scoring.market_regime.get_market_trend_state(),
    the same market_structure_engine already used per-stock, applied to the
    benchmark). Validated first via analyze_trend_state_vs_forward_returns()
    before wiring in: UPTREND averaged +1.19% forward return, CHOPPY +0.95%,
    DOWNTREND +0.53% -- the correct monotonic ordering, unlike VIX.

    Distribution days kept as a secondary modifier -- its flat result
    checked alone doesn't necessarily mean it adds nothing combined with
    trend state, just that it doesn't work alone; worth re-testing this
    specific combination before the next full backtest, not assumed here.

    VIX itself isn't discarded -- flagged as a candidate input elsewhere
    (e.g. stop-loss width) in a future task, not part of this one.
    """
    if nifty_trend_state == "DOWNTREND":
        return "UNFAVORABLE"
    if nifty_trend_state == "CHOPPY" or distribution_day_count >= 3:
        return "CAUTION"
    return "FAVORABLE"


def _metrics_based_sector_verdict(sector_row: dict) -> str:
    if sector_row["Pct_Uptrend"] >= 60 and sector_row["Avg_RS_Rating"] >= 60:
        return "STRONG"
    if sector_row["Pct_Uptrend"] < 30 or sector_row["Avg_RS_Rating"] < 40:
        return "WEAK"
    return "NEUTRAL"


def get_sector_health_verdict(sector_row: dict) -> str:
    """Returns STRONG / NEUTRAL / WEAK for the candidate's sector.

    Combines the real sector index's own trend state
    (scoring.sector_indices.get_sector_index_trend() -- UPTREND/DOWNTREND/CHOPPY
    against the sector's actual NSE index, e.g. NIFTY IT) with the existing
    Pct_Uptrend/Avg_RS_Rating breadth metrics (computed from Falcon's own
    tracked-candidate universe, not the sector's real constituents) --
    kept both rather than replacing one with the other. Pct_Uptrend still
    carries information (breadth among the specific candidates being
    screened) even though it isn't true sector-wide breadth, so the two
    are combined rather than letting one unconditionally win:
      - real index DOWNTREND caps at WEAK regardless of the metrics --
        a small-sample proxy showing strength would be misleading if the
        sector itself is actually falling.
      - real index UPTREND + metrics STRONG confirms STRONG.
      - real index UPTREND + metrics WEAK is a genuine disagreement
        between the real index and tracked-candidate breadth -- softened
        to NEUTRAL rather than confidently picking a side.
      - CHOPPY, or any other combination, defers to the metrics-only
        verdict unchanged.

    sector_row["Sector_Index_Trend"] is optional -- absent (None) when
    the caller hasn't wired scoring.sector_indices in yet, or the sector
    has no real index mapping (see SECTOR_INDEX_MAP). Falls back to the
    metrics-only verdict in that case, same as before this combination
    existed.
    """
    metrics_verdict = _metrics_based_sector_verdict(sector_row)
    sector_index_trend = sector_row.get("Sector_Index_Trend")

    if sector_index_trend is None:
        return metrics_verdict

    if sector_index_trend == "DOWNTREND":
        return "WEAK"

    if sector_index_trend == "UPTREND" and metrics_verdict == "STRONG":
        return "STRONG"

    if sector_index_trend == "UPTREND" and metrics_verdict == "WEAK":
        return "NEUTRAL"

    return metrics_verdict


def _is_top_half_sector(sector_row: dict) -> bool:
    """"Top half of ranking" needs the total sector count, which a single
    rank_sectors() row doesn't carry on its own -- see Total_Sectors in
    the module docstring's sector_row contract."""
    total = sector_row.get("Total_Sectors")
    rank = sector_row.get("Rank")
    if not total or rank is None:
        return False
    return rank <= total / 2


# Split so backtesting/replay_engine.py can genuinely disable the
# fundamental half rather than fail closed on it (see
# disable_fundamental_signals below) -- current fundamental data is a
# live snapshot, not point-in-time, so applying today's ROCE/D_E to
# judge a trade from 2 years ago would be lookahead bias. That's a
# different situation from the live path, where missing/unparseable data
# should fail closed (see the `is None or` note below) rather than
# silently pass a quality gate whose whole point is to filter on that
# data -- backtesting mode needs the check skipped entirely, not made to
# fail one particular way.
TECHNICAL_DISQUALIFIERS = [
    lambda s: s["Trend_State"] != "UPTREND",
    lambda s: s["Rel_Vol"] is None or s["Rel_Vol"] < 0.5,
]

# `is None or` on each numeric check: candidate_assembler.py's
# _parse_formatted_percentage() legitimately returns None for a
# non-numeric upstream sentinel (e.g. corporate_engine.py's D_E can come
# back as "DEBT_FREE" instead of a number) -- direct `s["ROCE"] < 10.0`
# would raise TypeError comparing None to a float the first time real
# data hit this path. Missing/unparseable fundamental data fails closed
# (disqualifies) rather than silently passing a quality gate whose whole
# point is to filter on that same data.
FUNDAMENTAL_DISQUALIFIERS = [
    lambda s: s["D_E"] is None or s["D_E"] > 0.5,
    lambda s: s["ROCE"] is None or s["ROCE"] < 10.0,
]

DISQUALIFIERS = TECHNICAL_DISQUALIFIERS + FUNDAMENTAL_DISQUALIFIERS

# days_to_earnings has the same live-snapshot problem as ROCE/D_E above --
# corporate_engine.py's earnings calendar is a live-only fetch, no
# point-in-time historical reconstruction exists yet -- so this cap is
# fundamental too and gets skipped under disable_fundamental_signals.
INDEPENDENT_CAPS = [
    (lambda s: s["days_to_earnings"] <= 7, "EARNINGS_PROXIMITY"),
]

# Weight ordering reflects how rigorously each pattern's own definition
# constrains what qualifies, not an arbitrary preference -- VCP and
# Cup-Handle require multi-week structural conditions (and, for VCP, a
# genuinely continuous, tested score); Bull Flag's brief window makes it
# the easiest to satisfy coincidentally, hence the lowest weight.
#
# Cup & Handle on PROBATION (weight 0, decided at Gate 1 / master execution
# spec item 2.6b, data/gate1_report.md's G1-e): backtest run #1 showed it
# as the single worst-performing pattern at episode level (n=21,
# expectancy 0.36%, full window) -- confirmed on the TUNING SPLIT ALONE
# before enacting this (n=6, expectancy -3.21%, worse than the full-window
# number, not better -- not a validation-period artifact). Weight 0 means
# a Cup & Handle-only signal contributes nothing to compute_score()'s
# pattern-points term, but detection stays on (candidate_assembler /
# pattern_engine still run it, entry/stop/target still price off it if
# it's the only pattern that fired) -- PATTERNS_ON_PROBATION below tags
# categorize()'s output so a Cup & Handle-priced signal is visibly
# flagged, not silently demoted. Triangle/VCP's own weight ordering is
# deliberately left untouched here -- see the same report's note that
# ordering integers now would be the one-window reaction Phase 4's
# calibrated scorer exists to replace wholesale.

# List order IS the selection priority (get_best_pattern_points() below
# returns the first match, it does not re-sort by weight) -- must stay
# sorted descending by weight, or a lower-weighted pattern earlier in the
# list would keep winning selection over a higher-weighted one that fired
# alongside it. Cup & Handle's weight-0 probation (see above) moves it
# here, to the end, rather than leaving it in its original by-rigor
# position -- leaving it at position 2 with a 0 weight would have let it
# keep "winning" priority over Ascending Triangle (weight 20) whenever
# both fired together, silently reintroducing the same problem probation
# exists to fix.
PATTERN_WEIGHTS = [
    ("is_vcp_breakout", 30),
    ("is_ascending_triangle_breakout", 20),
    ("is_flat_base_breakout", 18),
    ("is_bull_flag_breakout", 15),
    ("is_cup_handle_breakout", 0),
]

PATTERNS_ON_PROBATION = {"is_cup_handle_breakout"}

# Deliberately smaller than MACD's +10/-12: MACD is an established
# continuous indicator (histogram slope) already validated in an earlier
# pass; liquidity sweeps and FVGs (technical_analysis/liquidity_sweep.py,
# technical_analysis/fair_value_gap.py) are newer, more binary ICT/SMC-
# style microstructure checks still being EVALUATED, not yet proven, per
# their own spec's framing -- a conservative mid-range bonus (the "+5 to
# +8" suggested range's midpoint) avoids overweighting an unvalidated
# signal while still being large enough to show up in a flag-on/flag-off
# backtest comparison. Confidence boosts only, never a cap or
# disqualifier -- see enable_microstructure_signals below.
LIQUIDITY_SWEEP_SCORE_BONUS = 6
FVG_SCORE_BONUS = 6


# Phase 4.6: the hand-set market/sector hard ceiling this function used
# to implement (UNFAVORABLE always caps, CAUTION caps unless sector
# STRONG, FAVORABLE never caps) is REMOVED, not reparameterized --
# replaced by the calibrated v2 consolidation-quality model's own
# probability output, in which market_regime_verdict/sector_health_verdict
# are soft, continuously-weighted, LEARNED inputs (see
# models/consolidation_quality_v1.json's own coefficients) rather than a
# hard rule. Gate 3 (two independent, non-overlapping validation windows)
# showed the calibrated probability outperforms this hard ceiling +
# score>=65 combination; see _predict_candidate_consolidation_quality()
# below for what replaced it. Confirmed unused elsewhere in the codebase
# before deletion -- backtesting/backtest_runner.py's ceiling-attribution
# diagnostics and tests/choke_point_decomposition.py's own comments
# describe this function's OLD behavior for analyzing historical (run #2/
# #3) backtest data generated under it, not live calls into it.


_MODEL_ARTIFACT_CACHE: dict[str, dict] = {}


def _get_default_model_artifact() -> dict:
    """Lazily loads and caches config.ACTIVE_MODEL_VERSION's artifact --
    loaded once per process, not once per candidate (categorize() can be
    called thousands of times in a single backtest run). Lazy (not
    module-level at import time) so a test can construct a categorize()
    call with an explicit model_artifact= override without ever touching
    the real file on disk."""
    from config import ACTIVE_MODEL_VERSION

    if ACTIVE_MODEL_VERSION not in _MODEL_ARTIFACT_CACHE:
        _MODEL_ARTIFACT_CACHE[ACTIVE_MODEL_VERSION] = load_model_artifact(ACTIVE_MODEL_VERSION)

    return _MODEL_ARTIFACT_CACHE[ACTIVE_MODEL_VERSION]


def _predict_candidate_consolidation_quality(
    candidate: dict, market_verdict: str, sector_verdict: str, pattern_used: str, artifact: dict,
) -> float | None:
    """Assembles the calibrated model's feature vector from `candidate`
    (already carrying the 9 v2 consolidation-quality features + RS_Rating +
    macd_signal via decision_engine.candidate_assembler.assemble_candidate(),
    Phase 4.6) plus the regime/sector/pattern context categorize() already
    has in scope, and returns the predicted win probability.

    Returns None (not a crash, not a fabricated probability) when a
    required numeric feature or rs_line_new_high is missing -- e.g.
    consolidation_valid=False (INSUFFICIENT_PIVOTS: not enough confirmed
    macro pivots yet to locate a base) or rs_line_invalidated_reason set
    (INSUFFICIENT_HISTORY/NO_BENCHMARK_HISTORY). The caller treats None as
    "the model genuinely can't score this candidate" and fails closed to
    ALERT_WATCHLIST, the same conservative default this codebase already
    uses everywhere else a required input can't be resolved (missing
    regime data -> UNFAVORABLE, missing fundamentals -> "no signal") --
    never a silent EXECUTE.
    """
    feature_values = {}

    for feature in artifact["numeric_features"]:
        value = candidate.get(feature)
        if value is None:
            return None
        feature_values[feature] = value

    for feature in artifact["boolean_features"]:
        value = candidate.get(feature)
        if value is None:
            return None
        feature_values[feature] = value

    feature_values["market_regime_verdict"] = market_verdict
    feature_values["sector_health_verdict"] = sector_verdict
    feature_values["pattern_used"] = pattern_used
    feature_values["macd_signal"] = candidate.get("macd_signal") or "NEUTRAL"

    return predict_consolidation_quality(feature_values, artifact)


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


def compute_score(
    candidate: dict,
    sector_row: dict,
    disable_fundamental_signals: bool = False,
    enable_microstructure_signals: bool = False,
) -> float:
    """0-100 base score (clamped), computed once the cascade ceiling from
    Steps 1-2 is already known -- the final category is always the lower
    of this score and that ceiling, never the score in isolation.

    disable_fundamental_signals=True skips every institutional/fundamental
    modifier below (institutional sponsorship, buy-side deal activity,
    FII/DII/promoter trend, margin trend) -- for backtesting/replay_engine.py,
    where today's fundamentals can't legitimately judge a trade from years
    ago. Technical/regime signals (pattern points, FVG, liquidity sweep,
    RS_Rating, sector breadth, RSI, delivery conviction, MACD signal) are
    unaffected.

    enable_microstructure_signals=False (the default) skips the two new
    ICT/SMC microstructure bonuses (liquidity sweep, Fair Value Gap)
    entirely -- with it off, this function's output is byte-for-byte
    identical to before these signals existed. Additive only when on:
    never a cap, never a disqualifier, confidence boosts only (see
    LIQUIDITY_SWEEP_SCORE_BONUS/FVG_SCORE_BONUS's own comment for why
    these are smaller than MACD's weight).
    """
    score = 0.0

    best_points, _ = get_best_pattern_points(candidate)
    score += best_points

    if candidate.get("has_active_fvg"):
        score += 15
    if candidate.get("has_liquidity_sweep"):
        score += 15

    score += (candidate.get("RS_Rating", 0) / 100) * 20

    if _is_top_half_sector(sector_row):
        score += 10

    if not disable_fundamental_signals:
        if candidate.get("institutional_sponsorship_pct", 0) >= 20:
            score += 10
        if candidate.get("has_buy_activity"):
            score += 10

        # Skip-if-absent: None means "not yet scraped," not "flat" --
        # applying neither bonus nor penalty keeps the score honest about
        # what it actually knows.
        if candidate.get("fii_trend") == "INCREASING":
            score += 15
        if candidate.get("dii_trend") == "INCREASING":
            score += 8
        if candidate.get("promoter_trend") == "INCREASING":
            score += 5
        if candidate.get("promoter_trend") == "DECREASING":
            score -= 15
        if candidate.get("margin_trend_yoy") == "CONTRACTING":
            score -= 10

    if candidate.get("RSI_14", 0) > 70:
        score -= 10
    if sector_row.get("Pct_Uptrend", 100) < 30:
        score -= 15
    if _is_low_delivery_conviction(candidate):
        score -= 15

    # Bidirectional, not negative-only: momentum actually confirming the
    # breakout direction is real signal, not just the absence of a
    # warning -- see technical_analysis/pattern_system/macd_signal.py's
    # own docstring for why crediting alignment (not just penalizing
    # divergence) is a deliberate, principled choice. -12 for divergence
    # is slightly stronger than the +10 bonus: a breakout with active
    # momentum divergence has a historically higher failure rate than a
    # setup without MACD confirmation still working out.
    macd_signal = candidate.get("macd_signal", "NEUTRAL")
    if macd_signal == "BULLISH_ALIGNMENT":
        score += 10
    elif macd_signal == "BEARISH_DIVERGENCE":
        score -= 12

    if enable_microstructure_signals:
        # SSL (swept lows) is the bullish-bias direction for this
        # Leadership-only, UPTREND-gated engine -- BSL (swept highs) is a
        # bearish signal and deliberately not credited here. See
        # technical_analysis/liquidity_sweep.py's own docstring for the
        # SSL/BSL definitions.
        if candidate.get("liquidity_sweep_direction") == "SSL":
            score += LIQUIDITY_SWEEP_SCORE_BONUS

        # A bullish FVG still open (not yet fully filled) confirms the
        # setup has room the breakout can still draw price toward -- a
        # FULLY filled gap (100%) has already done its job and no longer
        # represents open, unmitigated demand.
        if candidate.get("fvg_direction") == "bullish" and (candidate.get("fvg_filled_pct") or 0) < 100:
            score += FVG_SCORE_BONUS

    return round(max(0.0, min(100.0, score)), 1)


def _is_low_delivery_conviction(candidate: dict) -> bool:
    """True when Delivery_Pct is genuinely below its own 20-day average.
    Delivery_Pct can be None whenever NSE wasn't the active data source
    for that fetch -- `.get(key, default)` only falls back to `default`
    when the key is *absent*, not when it's present but None, so a naive
    `candidate.get("Delivery_Pct_20d_avg", 100)` still returns None here
    and crashes the comparison (confirmed by tracing a real candidate
    through categorize() end-to-end). Separately, Delivery_Pct_20d_avg
    can be NaN (not None) during a ticker's first 19 bars of history,
    where pandas' rolling(20) hasn't filled yet -- that case doesn't need
    an explicit guard, since any comparison against NaN returns False
    rather than raising, so it safely just never fires the flag."""
    delivery_pct = candidate.get("Delivery_Pct")
    delivery_avg = candidate.get("Delivery_Pct_20d_avg")
    return delivery_pct is not None and delivery_avg is not None and delivery_pct < delivery_avg


def get_fakeout_risk_flags(candidate: dict, sector_row: dict, disable_fundamental_signals: bool = False) -> list[str]:
    """Surfaces *why* something might be a fakeout as named flags, not
    just a quieter score.

    disable_fundamental_signals=True skips the two fundamental-sourced
    flags (MARGIN_QUALITY_CONCERN, PROMOTER_STAKE_DECLINING) -- same
    lookahead-bias reason as compute_score's flag. The technical flags
    (delivery conviction, sector breadth, RSI) are unaffected.

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

    if candidate.get("macd_signal") == "BEARISH_DIVERGENCE":
        flags.append("MACD_BEARISH_DIVERGENCE")

    if not disable_fundamental_signals:
        if candidate.get("margin_trend_yoy") == "CONTRACTING":
            flags.append("MARGIN_QUALITY_CONCERN")
        if candidate.get("promoter_trend") == "DECREASING":
            flags.append("PROMOTER_STAKE_DECLINING")

    return flags


def get_contributing_factors(candidate: dict, enable_microstructure_signals: bool = False) -> list[str]:
    """Positive-side counterpart to get_fakeout_risk_flags() -- named
    factors that positively confirmed the setup, not just a quieter
    absence of warnings.

    enable_microstructure_signals=False (the default) omits the two new
    liquidity-sweep/FVG factors entirely, matching compute_score()'s own
    flag -- with it off, this function's output is unchanged from before
    these signals existed.
    """
    factors = []

    if candidate.get("macd_signal") == "BULLISH_ALIGNMENT":
        factors.append("MACD_MOMENTUM_ALIGNED")

    if enable_microstructure_signals:
        if candidate.get("liquidity_sweep_direction") == "SSL":
            factors.append("LIQUIDITY_SWEEP_SSL_CONFIRMED")
        if candidate.get("fvg_direction") == "bullish" and (candidate.get("fvg_filled_pct") or 0) < 100:
            factors.append("BULLISH_FVG_UNFILLED")

    return factors


def get_entry_target_stop(candidate: dict, best_pattern_field: str | None, best_pattern_result: dict | None) -> dict:
    """Entry prices off whichever pattern was selected via the
    weight-priority logic above, not VCP specifically -- all 5 detectors
    return their own pivot_level.

    Stop-loss/target (2.2, I-6, two-low model): stop and target are priced
    off two DIFFERENT lows on the same pattern, not the same one --
    pricing both off one low forced reward:risk toward exactly 1.0
    whenever the stop was unclamped, which is what run #2 caught.
      - stop_loss = entry - stop_distance, where stop_distance is the
        entry-to-proximal-low distance (best_pattern_result["proximal_low"]
        -- the pattern's near support: VCP's final contraction low, the
        flag's pullback low, etc., see
        decision_engine.candidate_assembler.PATTERN_PROXIMAL_LOW_COLUMN_MAP)
        plus a small buffer (STOP_BUFFER_ATR_MULTIPLE x ATR_14, so the
        stop sits below support rather than exactly on it), CLAMPED to
        [ATR_STOP_FLOOR_MULTIPLE, ATR_STOP_CEILING_MULTIPLE] x ATR_14 same
        as before.
      - target = entry + the entry-to-structural-low distance
        (best_pattern_result["structural_low"] -- the pattern's deeper,
        overall base: VCP's first contraction low, the flagpole's base,
        etc.) -- a genuine measured move, floored at
        TARGET_MIN_ATR_MULTIPLE x ATR_14 so a shallow pattern can't
        produce a target too close to entry to ever clear the RR floor.
    Falls back to the prior flat ATR guess (entry -+ 2/2.5x ATR) for BOTH
    legs when there's no pattern at all, or proximal_low is missing/
    nonsensical (>= entry) -- there's no usable near support to price a
    stop off at all. Falls back for the TARGET leg only (stop still prices
    off proximal_low normally) when structural_low is missing or not
    actually deeper than proximal_low (malformed/mis-detected pattern) --
    tagged target_provenance="ATR_FALLBACK_STRUCTURAL_INVALID" so this
    case is distinguishable from a genuine measured move.
    stop_provenance/target_provenance name which path was taken, for
    diagnostics -- never silently one or the other.

    max_holding_days (2.1, I-3): the time-stop half of the trade plan,
    alongside entry/stop_loss/target -- a single config value
    (MAX_HOLDING_TRADING_DAYS) rather than something a caller has to know
    to apply separately. backtesting/outcome_measurement.py's
    measure_forward_outcome() defaults to the same constant, so a replay
    that doesn't explicitly pass max_holding_days already agrees with what
    the trade plan itself states.
    """
    atr = candidate.get("ATR_14", 0) or 0

    if best_pattern_field is None or not best_pattern_result:
        entry = candidate["Close"]
        return {
            "entry": entry,
            "stop_loss": entry - 2 * atr,
            "target": entry + 2.5 * atr,
            "max_holding_days": MAX_HOLDING_TRADING_DAYS,
            "stop_provenance": "ATR_FALLBACK_NO_PATTERN",
            "target_provenance": "ATR_FALLBACK_NO_PATTERN",
            "proximal_low": None,
        }

    entry = best_pattern_result.get("pivot_level", candidate["Close"])
    proximal_low = best_pattern_result.get("proximal_low")
    structural_low = best_pattern_result.get("structural_low")

    if proximal_low is None or proximal_low >= entry:
        # No usable proximal low -- missing, or nonsensical (a
        # mis-detected pivot placing the "low" at or above entry) -- same
        # flat-ATR fallback as the no-pattern case, for both legs, since
        # there's no near support to price a stop off at all.
        return {
            "entry": entry,
            "stop_loss": entry - 2 * atr,
            "target": entry + 2.5 * atr,
            "max_holding_days": MAX_HOLDING_TRADING_DAYS,
            "stop_provenance": "ATR_FALLBACK_NO_PROXIMAL_LOW",
            "target_provenance": "ATR_FALLBACK_NO_PROXIMAL_LOW",
            "proximal_low": proximal_low,
        }

    raw_proximal_distance = (entry - proximal_low) + STOP_BUFFER_ATR_MULTIPLE * atr

    if atr > 0:
        atr_floor = ATR_STOP_FLOOR_MULTIPLE * atr
        atr_ceiling = ATR_STOP_CEILING_MULTIPLE * atr
        stop_distance = max(atr_floor, min(raw_proximal_distance, atr_ceiling))
        if stop_distance == raw_proximal_distance:
            stop_provenance = "STRUCTURAL"
        elif stop_distance == atr_floor:
            stop_provenance = "STRUCTURAL_CLAMPED_TO_ATR_FLOOR"
        else:
            stop_provenance = "STRUCTURAL_CLAMPED_TO_ATR_CEILING"
    else:
        # No real ATR to clamp against (or buffer with) -- use the
        # proximal distance as-is rather than degrading to a zero-width
        # (unclampable) stop.
        stop_distance = raw_proximal_distance
        stop_provenance = "STRUCTURAL"

    if structural_low is None or structural_low >= proximal_low:
        # Malformed geometry -- the deeper anchor isn't actually deeper
        # than the near one -- fall back to the flat ATR target rather
        # than project a nonsensical (or negative) measured move. The
        # stop above is unaffected: it never depended on structural_low.
        target = entry + 2.5 * atr
        target_provenance = "ATR_FALLBACK_STRUCTURAL_INVALID"
    else:
        raw_structural_distance = entry - structural_low
        target_min = TARGET_MIN_ATR_MULTIPLE * atr
        if atr > 0 and raw_structural_distance < target_min:
            target = entry + target_min
            target_provenance = "MEASURED_MOVE_FLOORED_TO_ATR_MIN"
        else:
            target = entry + raw_structural_distance
            target_provenance = "MEASURED_MOVE"

    return {
        "entry": entry,
        "stop_loss": entry - stop_distance,
        "target": target,
        "max_holding_days": MAX_HOLDING_TRADING_DAYS,
        "stop_provenance": stop_provenance,
        "target_provenance": target_provenance,
        "proximal_low": proximal_low,
    }


def categorize(
    candidate: dict,
    sector_row: dict,
    market_verdict: str,
    pattern_details: dict | None = None,
    disable_fundamental_signals: bool = False,
    enable_microstructure_signals: bool = False,
    min_reward_risk: float = MIN_REWARD_RISK,
    model_artifact: dict | None = None,
) -> dict:
    """Full Leadership-strategy decision: disqualifiers first (AVOID
    immediately, regardless of market/sector/score), then the 0-100 score
    floors AVOID (score<40) and MONITOR (no confirmed pattern, B-8) same
    as before -- but for a pattern-confirmed candidate that clears the
    score floor, EXECUTE-vs-ALERT_WATCHLIST is now decided by the
    calibrated v2 consolidation-quality model's predicted win probability
    (Phase 4.6), not a hand-set score>=65 cutoff clamped by a market/
    sector hard ceiling. market_regime_verdict/sector_health_verdict are
    now soft, continuously-weighted, LEARNED inputs to that probability
    (see the model's own fitted coefficients) instead of a rule that
    either fully blocks or fully permits EXECUTE. Gate 3 (two independent,
    non-overlapping validation windows) showed this outperforms the old
    score+ceiling combination; see _predict_candidate_consolidation_quality()'s
    own docstring for exactly what replaced get_ceiling().

    model_artifact : optional override, defaults to
        config.ACTIVE_MODEL_VERSION's artifact (loaded once per process
        and cached, not once per candidate). Tests pass a small stub/
        fixture artifact directly rather than depending on the real file
        on disk -- same pattern as min_reward_risk/enable_microstructure_signals
        below, a single overridable parameter for experiments/tests
        without touching call sites.

    disable_fundamental_signals=True is for backtesting/replay_engine.py:
    it genuinely skips the ROCE/D_E disqualifiers, the EARNINGS_PROXIMITY
    cap, and every fundamental-sourced score modifier/flag, rather than
    letting them fail closed on data that was never fetched for a
    historical replay date. This is different from the live path's
    "missing data fails closed" behavior (see FUNDAMENTAL_DISQUALIFIERS'
    own comment) -- here the checks are deliberately not run at all, not
    run and made to fail one particular way. Default False preserves the
    exact live-path behavior.

    enable_microstructure_signals=False (the default) means this
    function's output is byte-for-byte identical to before liquidity-
    sweep/FVG detection existed -- neither signal is a cap or a
    disqualifier, confidence boosts only, and both are opt-in per the
    spec's explicit requirement that existing behavior stay provably
    unchanged unless this flag is turned on.

    min_reward_risk (2.2, I-6): an EXECUTE-grade signal whose actual
    reward:risk (measured-move target distance / actual stop distance,
    from get_entry_target_stop()) falls below this floor is downgraded to
    ALERT_WATCHLIST with an RR_BELOW_FLOOR cap recorded in caps_applied --
    a technically well-scored setup with a poor risk:reward isn't worth
    EXECUTE-grade conviction. Only ever downgrades EXECUTE; ALERT_WATCHLIST/
    MONITOR/AVOID are unaffected (already at or below that tier). Threaded
    like enable_microstructure_signals -- a single config default
    (MIN_REWARD_RISK), overridable per call for tuning-split experiments
    without touching call sites.
    """
    pattern_details = pattern_details or {}

    disqualifiers = TECHNICAL_DISQUALIFIERS if disable_fundamental_signals else DISQUALIFIERS

    for check in disqualifiers:
        if check(candidate):
            return {
                "symbol": candidate.get("symbol"),
                "category": "AVOID",
                "market_regime_verdict": market_verdict,
                "sector_health_verdict": None,
                "confidence_score": 0.0,
                "caps_applied": [],
                "fakeout_risk_flags": [],
                "contributing_factors": [],
                "entry": None,
                "stop_loss": None,
                "target": None,
                "max_holding_days": None,
                "stop_provenance": None,
                "target_provenance": None,
                "reward_risk": None,
                "proximal_low": None,
                "bars_since_breakout": None,
                "breakout_within_last_k_bars": False,
                "supporting_data": candidate,
            }

    sector_verdict = get_sector_health_verdict(sector_row)

    independent_caps = [] if disable_fundamental_signals else INDEPENDENT_CAPS
    caps_applied = [name for check, name in independent_caps if check(candidate)]

    score = compute_score(
        candidate, sector_row,
        disable_fundamental_signals=disable_fundamental_signals,
        enable_microstructure_signals=enable_microstructure_signals,
    )

    best_points, best_field = get_best_pattern_points(candidate)

    if score < 40:
        # Unchanged: the calibrated model was only ever fit on real
        # EXECUTE/ALERT_WATCHLIST episodes (score>=40, pattern-confirmed)
        # -- it has no trained behavior for genuinely weak setups, so this
        # floor stays a hard, pre-model rule, same as before.
        final_category = "AVOID"
    elif best_field is None:
        # B-8 (2.6c, Gate 1 decision #4) unchanged: pattern presence
        # required for ALERT_WATCHLIST and above -- the model's own
        # pattern_used feature is only ever populated for a pattern-
        # confirmed candidate too (never fit on a no-pattern row), so this
        # gate stays a hard pre-filter, not something the calibrated
        # probability could ever rescue.
        final_category = "MONITOR"
    else:
        artifact = model_artifact if model_artifact is not None else _get_default_model_artifact()
        predicted_p = _predict_candidate_consolidation_quality(
            candidate, market_verdict, sector_verdict, best_field, artifact,
        )
        if predicted_p is None:
            # The model genuinely can't score this candidate (missing v2
            # feature inputs -- insufficient own-ticker or benchmark
            # history) -- fails closed to ALERT_WATCHLIST, never a silent
            # EXECUTE. See _predict_candidate_consolidation_quality()'s
            # own docstring.
            final_category = "ALERT_WATCHLIST"
        else:
            final_category = "EXECUTE" if predicted_p >= artifact["execute_cutoff"] else "ALERT_WATCHLIST"

    # independent_caps (e.g. EARNINGS_PROXIMITY) unchanged: still hard-caps
    # at ALERT_WATCHLIST regardless of how the tier above was reached --
    # only ever downgrades EXECUTE, since AVOID/MONITOR/ALERT_WATCHLIST
    # already rank at or below ALERT_WATCHLIST (CATEGORY_RANK).
    if caps_applied:
        final_category = min(final_category, "ALERT_WATCHLIST", key=lambda c: CATEGORY_RANK[c])

    best_result = pattern_details.get(best_field) if best_field else None

    if final_category == "AVOID":
        entry = stop_loss = target = max_holding_days = None
        stop_provenance = target_provenance = reward_risk = proximal_low = None
    else:
        ets = get_entry_target_stop(candidate, best_field, best_result)
        entry, stop_loss, target = ets["entry"], ets["stop_loss"], ets["target"]
        max_holding_days = ets["max_holding_days"]
        stop_provenance, target_provenance = ets["stop_provenance"], ets["target_provenance"]
        proximal_low = ets["proximal_low"]

        # entry - stop_loss <= 0 would mean a broken stop (at or above
        # entry) -- can't compute a meaningful RR from that.
        reward_risk = (target - entry) / (entry - stop_loss) if (entry - stop_loss) > 0 else None

        # 2.2 (I-6) RR floor: only ever downgrades EXECUTE -- ALERT_WATCHLIST/
        # MONITOR are already at or below that tier.
        if final_category == "EXECUTE" and reward_risk is not None and reward_risk < min_reward_risk:
            final_category = "ALERT_WATCHLIST"
            caps_applied = caps_applied + ["RR_BELOW_FLOOR"]

    fakeout_risk_flags = get_fakeout_risk_flags(candidate, sector_row, disable_fundamental_signals=disable_fundamental_signals)
    if best_field in PATTERNS_ON_PROBATION:
        fakeout_risk_flags.append(f"PATTERN_ON_PROBATION:{best_field}")

    return {
        "symbol": candidate.get("symbol"),
        "category": final_category,
        "market_regime_verdict": market_verdict,
        "sector_health_verdict": sector_verdict,
        "confidence_score": score,
        "caps_applied": caps_applied,
        "fakeout_risk_flags": fakeout_risk_flags,
        "contributing_factors": get_contributing_factors(candidate, enable_microstructure_signals=enable_microstructure_signals),
        "multiple_patterns_confirmed": candidate.get("Multiple_Patterns_Confirmed", False),
        "entry": entry,
        "stop_loss": stop_loss,
        "target": target,
        "max_holding_days": max_holding_days,
        # 2.2 (I-6): provenance names which pricing path was actually
        # taken (STRUCTURAL/STRUCTURAL_CLAMPED_TO_ATR_FLOOR-or-CEILING/
        # MEASURED_MOVE/ATR_FALLBACK_*, see get_entry_target_stop()'s own
        # docstring) -- None for AVOID (no trade plan at all).
        "stop_provenance": stop_provenance,
        "target_provenance": target_provenance,
        "reward_risk": reward_risk,
        # Two-low model (2.2 fix, I-6): the near-support anchor the stop
        # was actually priced off, alongside the provenance fields above --
        # None for AVOID/no-pattern/no-usable-proximal-low.
        "proximal_low": proximal_low,
        # A-5 breakout-recency contract, surfaced for the SELECTED pattern
        # (the one that actually drove the score/entry) rather than
        # requiring a consumer to dig into supporting_data/pattern_details
        # themselves -- None/False when no pattern fired at all.
        "bars_since_breakout": best_result.get("bars_since_breakout") if best_result else None,
        "breakout_within_last_k_bars": best_result.get("breakout_within_last_k_bars", False) if best_result else False,
        "supporting_data": candidate,
    }


# -------------------------------------------------------------------------
# Extensibility
# -------------------------------------------------------------------------
# emergent_decision_engine.py / reversal_decision_engine.py can live
# alongside this file later, each implementing the same output contract
# (category/market_regime_verdict/sector_health_verdict/confidence_score/
# caps_applied/fakeout_risk_flags/contributing_factors/entry/stop_loss/
# target/supporting_data) with different Tier 1/2/3 logic suited to those
# strategies -- Reversal
# in particular needs its own pattern-selection table entirely, since it
# can't rely on VCP/continuation-pattern breakouts the way this module
# does. This module shouldn't need to change when those get built.
