"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================
Module      : flag_descriptions.py
Package     : ui

Purpose
-------
Hover-tooltip text for the Factors/Risk Flags chips (candidate cards and
the "All Filtered Candidates" table) -- one accurate 2-3 line description
per flag decision_engine.leadership_decision_engine.py can actually
produce (get_contributing_factors()/get_fakeout_risk_flags(), plus the
categorize()-appended PATTERN_ON_PROBATION:{pattern} flag), enumerated
from that module directly rather than from whatever happens to appear in
today's scan.

Depth: real per-candidate numbers plugged in where the underlying value
is genuinely available on the row (LOW_DELIVERY_CONVICTION,
ISOLATED_MOVE_NO_SECTOR_TAILWIND, TECHNICALLY_OVEREXTENDED,
BULLISH_FVG_UNFILLED) -- decision_engine/live_scorer.py's
_decide_for_ticker() propagates the specific fields each of these needs
(Delivery_Pct/Delivery_Pct_20d_avg/RSI_14/Pct_Uptrend) straight from the
same candidate/sector_row categorize() itself was given, so a tooltip can
never disagree with the flag it's describing. Falls back to an accurate
but generic description when the value is missing (None/NaN) rather than
showing a broken/blank tooltip. The remaining flags (MACD alignment/
divergence, margin trend, promoter trend, pattern probation) are
inherently categorical -- no single number to plug in -- so their
descriptions stay accurate but static.
===============================================================================
"""
from __future__ import annotations

import pandas as pd

# is_x_breakout field name -> human label, for PATTERN_ON_PROBATION:{field}.
# Mirrors decision_engine.leadership_decision_engine.PATTERN_WEIGHTS' own
# field names -- kept here rather than imported, since importing would
# pull the whole decision engine module into the UI layer for five string
# labels.
PATTERN_FIELD_LABELS = {
    "is_vcp_breakout": "VCP",
    "is_ascending_triangle_breakout": "Ascending Triangle",
    "is_flat_base_breakout": "Flat Base",
    "is_bull_flag_breakout": "Bull Flag",
    "is_cup_handle_breakout": "Cup & Handle",
}

PATTERN_ON_PROBATION_PREFIX = "PATTERN_ON_PROBATION:"


def _num(value):
    """None for a missing/NaN value, the value itself otherwise -- lets
    every description below plug in a real number only when one's
    genuinely there, falling back to generic text otherwise."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


# ---------------------------------------------------------------------------
# Contributing factors (get_contributing_factors())
# ---------------------------------------------------------------------------

def _macd_momentum_aligned(row) -> str:
    return (
        "MACD histogram is positive and rising versus the prior bar -- "
        "upward momentum is accelerating alongside the breakout, not just "
        "present."
    )


def _liquidity_sweep_ssl_confirmed(row) -> str:
    return (
        "Price wicked below a prior swing low (a sell-side liquidity sweep) "
        "and closed back inside the range -- read as a stop-hunt reversal, "
        "not a genuine breakdown."
    )


def _bullish_fvg_unfilled(row) -> str:
    filled = _num(row.get("fvg_filled_pct"))
    if filled is not None:
        return (
            f"An unfilled bullish Fair Value Gap from the breakout move sits "
            f"below current price as potential support -- currently "
            f"{filled:.0f}% filled (0% means completely open)."
        )
    return (
        "An unfilled bullish Fair Value Gap from the breakout move sits "
        "below current price as potential support."
    )


FACTOR_DESCRIPTIONS = {
    "MACD_MOMENTUM_ALIGNED": _macd_momentum_aligned,
    "LIQUIDITY_SWEEP_SSL_CONFIRMED": _liquidity_sweep_ssl_confirmed,
    "BULLISH_FVG_UNFILLED": _bullish_fvg_unfilled,
}


# ---------------------------------------------------------------------------
# Fakeout risk flags (get_fakeout_risk_flags() + categorize()'s own
# PATTERN_ON_PROBATION append)
# ---------------------------------------------------------------------------

def _low_delivery_conviction(row) -> str:
    pct = _num(row.get("Delivery_Pct"))
    avg = _num(row.get("Delivery_Pct_20d_avg"))
    if pct is not None and avg is not None:
        return (
            f"Delivery is {pct:.2f}%, below its own 20-day average of "
            f"{avg:.2f}% -- the move is happening on more speculative/"
            f"intraday volume than this stock's own recent norm."
        )
    return (
        "Delivery percentage is below its own 20-day average -- the move is "
        "happening on more speculative/intraday volume than this stock's "
        "own recent norm."
    )


def _isolated_move_no_sector_tailwind(row) -> str:
    pct = _num(row.get("Pct_Uptrend"))
    sector = row.get("Sector")
    if pct is not None and sector:
        return (
            f"Only {pct:.0f}% of tracked {sector} stocks are currently in an "
            f"uptrend (below the 30% breadth floor) -- this move isn't "
            f"confirmed by sector-wide participation."
        )
    if pct is not None:
        return (
            f"Only {pct:.0f}% of this stock's sector peers are currently in "
            f"an uptrend (below the 30% breadth floor) -- this move isn't "
            f"confirmed by sector-wide participation."
        )
    return (
        "Fewer than 30% of this stock's sector peers are currently in an "
        "uptrend -- this move isn't confirmed by sector-wide participation."
    )


def _technically_overextended(row) -> str:
    rsi = _num(row.get("RSI_14"))
    if rsi is not None:
        return (
            f"RSI(14) is {rsi:.1f}, above the 70 overbought threshold -- the "
            f"stock may be due for a pause or pullback before continuing "
            f"higher."
        )
    return (
        "RSI(14) is above the 70 overbought threshold -- the stock may be "
        "due for a pause or pullback before continuing higher."
    )


def _macd_bearish_divergence(row) -> str:
    return (
        "Price is near its recent high, but the MACD histogram has faded "
        "well off its own recent peak and is still falling -- momentum "
        "isn't confirming the price strength, a classic fakeout warning."
    )


def _margin_quality_concern(row) -> str:
    return (
        "Operating margin (YoY) is trending CONTRACTING per the latest "
        "Screener data -- the business's core profitability is softening "
        "even if the price action hasn't caught up to it yet."
    )


def _promoter_stake_declining(row) -> str:
    return (
        "Promoter shareholding is trending DECREASING per the latest "
        "Screener data -- insiders reducing their stake is a soft caution "
        "signal, not disqualifying on its own."
    )


RISK_FLAG_DESCRIPTIONS = {
    "LOW_DELIVERY_CONVICTION": _low_delivery_conviction,
    "ISOLATED_MOVE_NO_SECTOR_TAILWIND": _isolated_move_no_sector_tailwind,
    "TECHNICALLY_OVEREXTENDED": _technically_overextended,
    "MACD_BEARISH_DIVERGENCE": _macd_bearish_divergence,
    "MARGIN_QUALITY_CONCERN": _margin_quality_concern,
    "PROMOTER_STAKE_DECLINING": _promoter_stake_declining,
}


def _pattern_on_probation(pattern_field: str) -> str:
    label = PATTERN_FIELD_LABELS.get(pattern_field, pattern_field.replace("_", " ").title())
    return (
        f"The {label} pattern is on probation -- backtesting showed it as "
        f"the worst-performing pattern at the episode level (near-zero to "
        f"negative expectancy). It still prices this trade's entry/stop/"
        f"target, but treat it as a lower-confidence signal than the other "
        f"confirmed patterns."
    )


def get_factor_tooltip(factor: str, row) -> str:
    """2-3 line tooltip for one contributing-factor chip. `row` is
    anything dict-like (pd.Series or dict) exposing the fields
    decision_engine/live_scorer.py propagates. Falls back to a readable
    title-cased version of the flag name for anything not enumerated
    above -- should never trigger given the full enumeration, but avoids
    a blank/crashing tooltip if a new factor is ever added upstream
    without a matching entry here."""
    builder = FACTOR_DESCRIPTIONS.get(factor)
    if builder is None:
        return factor.replace("_", " ").title()
    return builder(row)


def get_risk_flag_tooltip(flag: str, row) -> str:
    """Same contract as get_factor_tooltip(), plus the parametrized
    PATTERN_ON_PROBATION:{pattern_field} case categorize() appends
    directly (not part of get_fakeout_risk_flags()'s own fixed list)."""
    if flag.startswith(PATTERN_ON_PROBATION_PREFIX):
        pattern_field = flag[len(PATTERN_ON_PROBATION_PREFIX):]
        return _pattern_on_probation(pattern_field)
    builder = RISK_FLAG_DESCRIPTIONS.get(flag)
    if builder is None:
        return flag.replace("_", " ").title()
    return builder(row)
