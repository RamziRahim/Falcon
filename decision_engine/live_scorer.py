"""
===============================================================================
Falcon AI Swing Trading Platform — Live Scan Decision Wiring
===============================================================================
Script      : live_scorer.py
Package     : Decision Engine

Wires the live "New Scan" pipeline's per-ticker candidate rows into
decision_engine.leadership_decision_engine.categorize() -- the live-scan
counterpart to backtesting/replay_engine.py's replay_decision_as_of(),
using CURRENT data instead of a truncated historical replay.

Unlike replay_engine.py (fundamentals={}, disable_fundamental_signals=True
-- deliberately, since today's ROCE/D_E would be lookahead bias against a
past replay date), live scanning has no such restriction: fundamentals are
fetched for real and disable_fundamental_signals=False, per this task's
own spec. enable_microstructure_signals is left at categorize()'s own
default (False) -- turning it on for the live path is a separate,
deliberate decision, not a side effect of this wiring.

Fundamentals are merged from all four sources candidate_assembler.py's own
docstring documents:
  - fundamental_cache.get_fundamentals(ticker)                    -> roce, debt_to_equity
  - corporate_engine.get_comprehensive_fundamentals(ticker)       -> margin_trend_yoy, days_to_earnings
  - institutional_engine.get_shareholding_profile_with_trend(...) -> institutional_sponsorship, fii_trend, dii_trend, promoter_trend
  - deal_activity.get_recent_institutional_activity(ticker)       -> has_buy_activity

The institutional-shareholding-trend source needs an authenticated
Screener.in Playwright session (candidate_generation.auth.login() +
candidate_generation.session.create_session()) -- opened ONCE per scan
batch here (not per ticker), reused across every candidate
(shareholding_scraper.py's own 30-day cache means most tickers don't even
trigger a real page visit after the first scan of the month), and always
closed in a finally block even if the batch fails partway through. If
SCREENER_USERNAME/SCREENER_PASSWORD aren't configured, or login itself
fails, the whole batch degrades to the Yahoo-only shareholding snapshot
(institutional_engine.get_shareholding_profile(), no session needed) --
fii_trend/dii_trend/promoter_trend simply come back None, which
categorize()'s scoring already treats as "no signal" rather than a
disqualifier (see leadership_decision_engine.py's FUNDAMENTAL_DISQUALIFIERS,
which only gate on ROCE/D_E -- both covered by fundamental_cache alone).
Each of the four sources is independently exception-guarded so one
source's failure never blocks the other three.
===============================================================================
"""
from __future__ import annotations

import os

import pandas as pd

from common.logger import get_logger
from config import SCREENER_USERNAME, SCREENER_PASSWORD

from candidate_generation.auth import login, logout
from candidate_generation.session import create_session

from fundamental_analysis.fundamental_cache import get_fundamentals
from fundamental_analysis.corporate_engine import corporate_engine
from fundamental_analysis.institutional_engine import institutional_engine
from fundamental_analysis.deal_activity import get_recent_institutional_activity

from scoring.benchmark import get_benchmark_history
from scoring.market_regime import get_market_trend_state, count_distribution_days
from scoring.sector_rotation import rank_sectors

from decision_engine.candidate_assembler import assemble_candidate, assemble_sector_row, assemble_pattern_details
from decision_engine.leadership_decision_engine import categorize, get_market_regime_verdict

logger = get_logger(__name__)

PATTERN_DIR = "data/patterns"

# Same floor replay_engine.py uses -- a shorter history can't support real
# fractal/indicator-derived fields anyway (they'd already be NaN/absent on
# the persisted parquet row).
MIN_HISTORY_ROWS = 20

NO_DATA_RESULT = {
    "category": "NO_DATA",
    "confidence_score": 0.0,
    "caps_applied": "",
    "contributing_factors": "",
    "fakeout_risk_flags": "",
}

DECISION_COLUMNS = list(NO_DATA_RESULT.keys())


def _open_screener_session():
    """
    Opens one authenticated Screener.in Playwright session for the whole
    scan batch. Returns (playwright, browser, session) -- all None if
    credentials are missing or login fails, which callers must treat as
    "no live session available" (degrade to the Yahoo-only shareholding
    snapshot), never a crash of the whole scan.
    """
    if not SCREENER_USERNAME or not SCREENER_PASSWORD:
        logger.warning(
            "SCREENER_USERNAME/SCREENER_PASSWORD not configured -- institutional "
            "shareholding QoQ trend will be skipped for this scan (Yahoo-only "
            "snapshot used instead)."
        )
        return None, None, None

    try:
        playwright, browser, page = login(SCREENER_USERNAME, SCREENER_PASSWORD)
    except Exception as ex:
        logger.warning(
            "Screener.in login failed -- institutional shareholding QoQ trend "
            "will be skipped for this scan: %s", ex,
        )
        return None, None, None

    session = create_session(provider="Screener", browser=browser, page=page, username=SCREENER_USERNAME)
    session.set_authenticated(True)
    return playwright, browser, session


def _fetch_institutional_data(ticker: str, session) -> dict:
    """institutional_sponsorship + the Screener.in QoQ trend fields when a
    live session is available; Yahoo-only snapshot (institutional_sponsorship
    only, fii/dii/promoter_trend absent) otherwise -- both real data, never
    a fabricated placeholder."""
    if session is not None:
        try:
            return institutional_engine.get_shareholding_profile_with_trend(ticker, session)
        except Exception as ex:
            logger.warning("Shareholding trend fetch failed for %s: %s", ticker, ex)

    try:
        return institutional_engine.get_shareholding_profile(ticker)
    except Exception as ex:
        logger.warning("Shareholding snapshot fetch failed for %s: %s", ticker, ex)
        return {}


def _fetch_live_fundamentals(ticker: str, session) -> dict:
    """Merges all four fundamentals sources -- each independently
    exception-guarded so one source's failure never blocks the other
    three (every source below already fails closed to its own documented
    sentinel/default rather than raising in the first place, but this is
    a second line of defense against an unexpected exception)."""
    fundamentals: dict = {}

    try:
        fundamentals.update(get_fundamentals(ticker))
    except Exception as ex:
        logger.warning("fundamental_cache.get_fundamentals failed for %s: %s", ticker, ex)

    try:
        fundamentals.update(corporate_engine.get_comprehensive_fundamentals(ticker))
    except Exception as ex:
        logger.warning("corporate_engine.get_comprehensive_fundamentals failed for %s: %s", ticker, ex)

    fundamentals.update(_fetch_institutional_data(ticker, session))

    try:
        fundamentals.update(get_recent_institutional_activity(ticker))
    except Exception as ex:
        logger.warning("deal_activity.get_recent_institutional_activity failed for %s: %s", ticker, ex)

    return fundamentals


def _compute_live_market_verdict() -> str:
    """NIFTY's own current Trend_State + distribution days, same
    trend-based regime signal replay_engine.py uses for a historical
    date -- here simply evaluated at "now" (no truncation needed, there's
    no lookahead risk against live data). Fails closed to UNFAVORABLE
    (not a crash, not a silently-optimistic default) when regime data
    can't be resolved, same philosophy as replay_engine.py's own
    missing-regime-data handling."""
    try:
        benchmark_history = get_benchmark_history()
        trend_state = get_market_trend_state(benchmark_history)
        distribution_days = count_distribution_days(benchmark_history)

        # get_market_trend_state() returns "CHOPPY" both for a genuinely
        # choppy market AND as its own honest-unknown default when there's
        # too little history -- unlike replay_engine.py's truncated-history
        # helper, it has no separate "UNKNOWN" sentinel to check. Live
        # benchmark_history always has far more than the ~20-row minimum
        # (it's never truncated), so that ambiguity doesn't bite in
        # practice; distribution_days is the one piece that genuinely can
        # come back None (missing Volume data), so that's what's checked.
        if distribution_days is None:
            return "UNFAVORABLE"

        return get_market_regime_verdict(trend_state, distribution_days)

    except Exception as ex:
        logger.warning("Market regime computation failed, defaulting to UNFAVORABLE: %s", ex)
        return "UNFAVORABLE"


def _load_pattern_history(ticker: str) -> pd.DataFrame | None:
    path = os.path.join(PATTERN_DIR, f"{ticker}.parquet")

    if not os.path.exists(path):
        return None

    try:
        df = pd.read_parquet(path)
    except Exception as ex:
        logger.warning("Failed to read pattern data for %s: %s", ticker, ex)
        return None

    if df.empty or "Date" not in df.columns:
        return None

    return df.sort_values("Date").reset_index(drop=True)


def _decide_for_ticker(
    ticker: str, sector: str | None, rel_vol, rs_rating, sector_index_trend,
    sector_ranking: pd.DataFrame, market_verdict: str, session,
) -> dict:
    """Assembles and categorizes a single live candidate -- mirrors
    backtesting/replay_engine.py's replay_decision_as_of() step-by-step,
    minus the truncation (there's no as_of_date here, everything is
    already "now")."""
    history = _load_pattern_history(ticker)

    if history is None or len(history) < MIN_HISTORY_ROWS:
        return dict(NO_DATA_RESULT)

    pattern_row = history.iloc[-1].to_dict()

    fundamentals = _fetch_live_fundamentals(ticker, session)

    scoring_row = {"Rel_Vol": rel_vol, "RS_Rating": rs_rating, "Sector": sector}

    if sector is not None and sector in sector_ranking.index:
        sector_row = assemble_sector_row(sector_ranking, sector, sector_index_trend=sector_index_trend)
    else:
        sector_row = {
            "Avg_RS_Rating": 0.0, "Pct_Uptrend": 0.0, "Rank": None,
            "Total_Sectors": len(sector_ranking), "Sector_Index_Trend": sector_index_trend,
        }

    candidate = assemble_candidate(
        pattern_row, fundamentals=fundamentals, scoring_row=scoring_row, symbol=ticker,
        pattern_history_df=history,
    )
    pattern_details = assemble_pattern_details(pattern_row)

    result = categorize(
        candidate, sector_row, market_verdict,
        pattern_details=pattern_details,
        disable_fundamental_signals=False,
    )

    return {
        "category": result["category"],
        "confidence_score": result["confidence_score"],
        "caps_applied": ",".join(result["caps_applied"]),
        "contributing_factors": ",".join(result["contributing_factors"]),
        "fakeout_risk_flags": ",".join(result["fakeout_risk_flags"]),
    }


def score_live_candidates(records_df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds confidence_score / category / caps_applied / contributing_factors /
    fakeout_risk_flags columns to records_df (the live scan's already-
    scored candidate table -- Symbol/Sector/RS_Rating/Rel_Vol/Sector_Index_Trend
    already merged in by services.scan_pipeline_service.run_new_scan_pipeline()),
    calling categorize() for each row exactly like replay_decision_as_of()
    does for a backtest candidate, just against current data.

    Returns records_df unchanged (no new columns) if it's empty -- nothing
    to score yet.
    """
    if records_df.empty:
        return records_df

    playwright, browser, session = _open_screener_session()

    try:
        market_verdict = _compute_live_market_verdict()
        sector_ranking = rank_sectors(records_df) if "Sector" in records_df.columns else pd.DataFrame()

        decision_rows = []

        for _, row in records_df.iterrows():
            ticker = row["Symbol"]
            decision = _decide_for_ticker(
                ticker=ticker,
                sector=row.get("Sector"),
                rel_vol=row.get("Rel_Vol"),
                rs_rating=row.get("RS_Rating"),
                sector_index_trend=row.get("Sector_Index_Trend"),
                sector_ranking=sector_ranking,
                market_verdict=market_verdict,
                session=session,
            )
            decision["Symbol"] = ticker
            decision_rows.append(decision)

        decisions_df = pd.DataFrame(decision_rows)

        return records_df.merge(decisions_df, on="Symbol", how="left")

    finally:
        if playwright is not None and browser is not None:
            try:
                logout(playwright, browser)
            except Exception as ex:
                logger.warning("Screener.in logout failed (non-fatal): %s", ex)
