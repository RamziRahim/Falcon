"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : fundamental_cache.py
Package     : Fundamental Analysis

Purpose
-------
Returns roce/debt_to_equity for a ticker, sourced from the Screener
fundamentals store (fundamental_analysis/screener_fundamentals_store.py)
as of docs/known_data_issues.md item #4 -- previously two separate live
Yahoo calls (metrics_engine.get_roce(), metrics_engine.get_risk_vitals()
via the now-dead fundamental_engine.get_complete_data_packet() chain),
each with its own 7-day JSON cache that could silently serve a pre-fix
value for up to a week (docs/known_data_issues.md item #3's root cause).

No cache machinery of its own anymore -- the Screener store IS the cache
now, refreshed once per scan by candidate_generation.candidate_generator.
generate_candidates(), not lazily per-candidate on a fixed TTL. Kept as a
module-level function (not removed) purely for call-site compatibility --
decision_engine/live_scorer.py and ui/dashboard_data.py both import
get_fundamentals from here.
===============================================================================
"""
from __future__ import annotations

from fundamental_analysis.screener_fundamentals_store import (
    get_debt_to_equity_display,
    get_roce_display,
)

# revenue_yoy_quarterly_growth kept as a stable dict key for shape-
# compatibility with any future caller -- confirmed via a full-codebase
# usage audit (docs/known_data_issues.md item #4) that nothing currently
# reads this specific field from THIS function's return value.
# ui/dashboard_data.py's "Revenue Growth (YoY)" display reads the
# SAME-NAMED field from corporate_engine.get_comprehensive_fundamentals()
# instead, a different source entirely. Static "DATA_GAP" rather than a
# live fetch, since computing a real value here would only feed a key
# nothing reads.
_REVENUE_YOY_UNUSED_PLACEHOLDER = "DATA_GAP"


def get_fundamentals(ticker: str, force_refresh: bool = False) -> dict:
    """
    Returns a flattened fundamentals dict for a ticker: roce,
    revenue_yoy_quarterly_growth, debt_to_equity -- same shape every
    existing caller (decision_engine/candidate_assembler.py,
    ui/dashboard_data.py) already expects.

    force_refresh is a no-op, kept for call-site compatibility -- there's
    no live fetch left here to force; the Screener store is populated
    once per scan, not fetched lazily per-candidate.

    Both roce and debt_to_equity come back in the exact same "XX.XX%"
    string convention (or "N/A") the old Yahoo-sourced functions used --
    see screener_fundamentals_store.get_roce_display()/
    get_debt_to_equity_display()'s own docstrings for the scale-conversion
    details (Screener's own D/E column is a plain ratio, not a
    percentage, unlike ROCE) -- so candidate_assembler.py's
    _parse_formatted_percentage() parsing needs no change.
    """
    return {
        "roce": get_roce_display(ticker),
        "revenue_yoy_quarterly_growth": _REVENUE_YOY_UNUSED_PLACEHOLDER,
        "debt_to_equity": get_debt_to_equity_display(ticker),
    }
