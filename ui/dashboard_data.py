"""
===============================================================================
Falcon AI Swing Trading Platform
Module  : dashboard_data.py
Package : ui

Purpose
-------
Pure data-adapter for the mockup-derived dashboard (ui/dashboard.py +
ui/dashboard_template.html) -- shapes REAL Falcon data (records_df from
decision_engine.live_scorer.score_live_candidates(), sector rankings,
market regime, index quotes, price history) into the exact template-
variable dict the mockup's own script block defined (see
reference_mockup_annotated.html's SECTION 3 for the reference shape).

No Streamlit calls here (matches services/scan_pipeline_service.py's own
"kept Streamlit-free so it's directly testable" convention) -- ui/dashboard.py
is the thin Streamlit-facing wrapper.

Explicit "no fabricated data" policy (per the build instructions): every
field below either comes from a real Falcon computation or is an honest
empty/unavailable state. Two mockup fields have NO real Falcon data
source anywhere in this codebase and are deliberately left unavailable
rather than invented:
  - FII/DII net flow (₹ Cr) -- no market-wide flow data source exists
    (fundamental_analysis/institutional_engine.py's fii_trend/dii_trend
    are PER-STOCK shareholding trend signals, not a market-wide daily
    flow figure).
  - Market Insights narrative text -- the mockup's own array is
    hand-written prose ("Nifty opened above yesterday's high with broad
    participation..."); Falcon has no narrative-generation capability
    (that's the same "AI narration" layer explicitly disabled below, not
    a separate real capability). Shown as a "Coming Soon" panel, same
    treatment as the AI note panel, rather than either fabricated prose
    or silently dropped.
===============================================================================
"""
from __future__ import annotations

import math
from datetime import timedelta
from typing import Optional

import pandas as pd

from ui.flag_descriptions import get_factor_tooltip, get_risk_flag_tooltip

GREEN = "oklch(0.72 0.19 150)"
AMBER = "oklch(0.78 0.16 80)"
RED = "oklch(0.68 0.2 25)"
GREY = "oklch(0.69 0.01 250)"
BLUE = "oklch(0.7 0.15 230)"

REGIME_STYLE = {
    "FAVORABLE": {"emoji": "🟢", "color": GREEN, "subColor": "oklch(0.65 0.14 150)",
                  "bg": "oklch(0.25 0.08 150 / 0.28)", "border": "oklch(0.4 0.1 150 / 0.5)"},
    "CAUTION": {"emoji": "🟡", "color": AMBER, "subColor": "oklch(0.68 0.13 80)",
                "bg": "oklch(0.28 0.08 80 / 0.28)", "border": "oklch(0.45 0.1 80 / 0.5)"},
    "UNFAVORABLE": {"emoji": "🔴", "color": RED, "subColor": "oklch(0.62 0.16 25)",
                     "bg": "oklch(0.28 0.08 25 / 0.28)", "border": "oklch(0.45 0.1 25 / 0.5)"},
}

TREND_STYLE = {
    "UPTREND": {"color": GREEN, "bg": "oklch(0.25 0.08 150 / 0.3)", "border": "oklch(0.4 0.1 150 / 0.5)"},
    "DOWNTREND": {"color": RED, "bg": "oklch(0.28 0.08 25 / 0.3)", "border": "oklch(0.45 0.1 25 / 0.5)"},
    "CHOPPY": {"color": GREY, "bg": "oklch(0.28 0.012 250)", "border": "oklch(0.4 0.012 250)"},
    "UNKNOWN": {"color": GREY, "bg": "oklch(0.28 0.012 250)", "border": "oklch(0.4 0.012 250)"},
}

CATEGORY_STYLE = {
    "EXECUTE": {"label": "EXECUTE", "color": GREEN, "bg": "oklch(0.3 0.09 150 / 0.35)"},
    "ALERT_WATCHLIST": {"label": "WATCHLIST", "color": AMBER, "bg": "oklch(0.32 0.09 80 / 0.35)"},
    "MONITOR": {"label": "MONITOR", "color": BLUE, "bg": "oklch(0.28 0.09 230 / 0.35)"},
}

NA = "—"

# Screener-column-name -> readable pattern label, for MONITOR's "what's
# forming" line. Deliberately NOT the same map as decision_engine's
# PATTERN_WEIGHTS/PATTERN_COLUMN_MAP (those are about CONFIRMED breakouts
# feeding the score) -- these are the *_Setup booleans, which exist on
# every data/patterns/*.parquet row but were never copied into `candidate`
# by candidate_assembler.py (categorize() never needed "is something
# forming", only "is something confirmed"), so this reads pattern_row
# directly rather than going through the candidate dict.
MONITOR_SETUP_COLUMNS = [
    ("Is_VCP_Setup", "VCP"),
    ("Is_Flat_Base_Setup", "Flat Base"),
    ("Is_Cup_Handle_Setup", "Cup & Handle"),
    ("Is_Ascending_Triangle_Setup", "Ascending Triangle"),
    ("Is_Bull_Flag_Setup", "Bull Flag"),
]


def get_monitor_setup_state(latest_pattern_row: dict) -> Optional[str]:
    """Which pattern(s), if any, are currently forming but not yet
    confirmed -- for a MONITOR-tier candidate's card. Reads the real
    Is_X_Setup booleans straight off data/patterns/*.parquet's latest row
    (the same row build_chart_view() already has via `history`), NOT
    Pattern_Type (which pattern_engine.py only ever populates for
    CONFIRMED breakouts -- always empty/None for a MONITOR candidate by
    definition, so it can't answer this question at all).

    None when no setup detector fired -- an honest "nothing forming yet"
    rather than always claiming some structure exists just because the
    candidate reached MONITOR."""
    forming = [label for column, label in MONITOR_SETUP_COLUMNS if latest_pattern_row.get(column)]
    if not forming:
        return None
    return f"{', '.join(forming)} forming, not yet confirmed"


def _is_missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _factor_chips(names: list[str], row: pd.Series) -> list[dict]:
    """Chip label + hover tooltip for the Factors column/chips -- shared
    by build_candidate_view() (EXECUTE/WATCHLIST) and
    build_monitor_candidate_view() (MONITOR) so both render identically."""
    return [{"label": name, "tooltip": get_factor_tooltip(name, row)} for name in names]


def _risk_flag_chips(names: list[str], row: pd.Series) -> list[dict]:
    """Risk-flag counterpart to _factor_chips()."""
    return [{"label": name, "tooltip": get_risk_flag_tooltip(name, row)} for name in names]


def get_vwap_reclaim_display(row: pd.Series) -> Optional[dict]:
    """VWAP Reclaim (technical_analysis/vwap_reclaim.py, via
    services/scan_pipeline_service.py's live wiring) -- purely
    informational, same-day-only confluence flag for EXECUTE/WATCHLIST
    cards. Three real states, deliberately NOT collapsed into a single
    binary chip (per the spec): "reclaimed" (dipped below VWAP today and
    has since recovered -- the interesting case), "above_all_day" (never
    dipped -- a different, simpler state, not the same as a recovery),
    and "below" (no positive signal here).

    Returns None (render no chip at all) when the signal wasn't computed
    this scan -- market closed, candidate wasn't EXECUTE/WATCHLIST, the
    intraday fetch failed, or vwap_reclaim.py's own fail-closed checks
    tripped (too few bars / too gappy) -- same "honest absence, not a
    fabricated state" policy as every other field in this module. Also
    None for a records_df predating this feature (vwap_reclaimed column
    absent entirely), not misread as "below VWAP"."""
    invalidated_reason = row.get("vwap_invalidated_reason")
    reclaimed = row.get("vwap_reclaimed")

    if not _is_missing(invalidated_reason):
        return None
    if _is_missing(reclaimed):
        return None

    if bool(reclaimed):
        return {"label": "VWAP Reclaimed", "state": "reclaimed"}
    if bool(row.get("currently_above_vwap")):
        return {"label": "Above VWAP All Day", "state": "above_all_day"}
    return {"label": "Below VWAP", "state": "below"}


def _fmt_price(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return NA
    return f"₹{value:,.2f}"


def _fmt_pct(value, sign: bool = True) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return NA
    prefix = "+" if sign and value >= 0 else ""
    return f"{prefix}{value:.2f}%"


def _change_color(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return GREY
    return GREEN if value >= 0 else RED


def compute_day_change_pct(history: pd.DataFrame) -> Optional[float]:
    """Real day-over-day % change from the same price history the chart
    uses -- not a field build_candidate_table() currently exposes, but
    directly derivable from the last two Close values rather than
    fabricated."""
    if history is None or len(history) < 2:
        return None
    prev_close = history["Close"].iloc[-2]
    last_close = history["Close"].iloc[-1]
    if prev_close in (0, None) or pd.isna(prev_close) or pd.isna(last_close):
        return None
    return round((last_close - prev_close) / prev_close * 100, 2)


def build_market_pulse(regime_snapshot: dict | None, index_quotes: dict) -> dict:
    """Top strip: regime banner, real indices, the repurposed NIFTY Trend
    badge (was VIX in the mockup -- Falcon doesn't use VIX for anything,
    per the build instructions), distribution days, and an honest
    unavailable state for FII/DII flow (no real data source)."""
    verdict = regime_snapshot["verdict"] if regime_snapshot else None
    style = REGIME_STYLE.get(verdict, {"emoji": "⚪", "color": GREY, "subColor": GREY,
                                        "bg": "oklch(0.22 0.012 250)", "border": "oklch(0.3 0.012 250)"})
    regime = {"label": verdict or "UNKNOWN", **style}

    indices = []
    for label, q in index_quotes.items():
        if q:
            indices.append({
                "name": label, "price": f"{q['last_price']:,.2f}",
                "change": _fmt_pct(q["change_pct"]), "color": _change_color(q["change_pct"]),
            })
        else:
            indices.append({"name": label, "price": NA, "change": "unavailable", "color": GREY})

    trend_state = regime_snapshot["trend_state"] if regime_snapshot else "UNKNOWN"
    trend_style = TREND_STYLE.get(trend_state, TREND_STYLE["UNKNOWN"])
    nifty_trend = {
        "value": trend_state,
        "badge": verdict or "UNKNOWN",
        "bg": trend_style["bg"], "color": trend_style["color"], "border": trend_style["border"],
    }

    dist_count = regime_snapshot["distribution_days"] if regime_snapshot else None
    dist_meter = []
    for i in range(8):
        lit = dist_count is not None and i < min(dist_count, 8)
        dist_meter.append({"color": AMBER if lit else "oklch(0.28 0.012 250)"})
    dist_label = NA if dist_count is None else ("Elevated" if dist_count >= 5 else "Healthy")
    dist_label_color = GREY if dist_count is None else (RED if dist_count >= 5 else GREEN)

    return {
        "regime": regime,
        "indices": indices,
        "nifty_trend": nifty_trend,
        "distribution": {
            "count": NA if dist_count is None else str(dist_count),
            "meter": dist_meter, "label": dist_label, "labelColor": dist_label_color,
        },
        # No real market-wide FII/DII flow data source anywhere in this
        # codebase -- honest unavailable state, not a fabricated number.
        "flows": {"available": False},
    }


def build_sector_view(records_df: pd.DataFrame) -> list[dict]:
    """Sector Rotation panel -- scoring.sector_rotation.rank_sectors(),
    which averages RS_Rating per sector. RS_Rating itself is
    sector-index-anchored (scoring.sector_index_rs.compute_sector_index_rs(),
    threaded through scoring.scoring_engine.ScoringEngine.score_universe()
    as the primary path) -- not the old small-universe peer-percentile
    average, per the build instructions."""
    from scoring.sector_rotation import rank_sectors

    ranking = rank_sectors(records_df)
    if ranking.empty:
        return []

    max_rs = ranking["Avg_RS_Rating"].max() or 1.0
    sectors = []
    for sector_name, row in ranking.iterrows():
        rs = row["Avg_RS_Rating"]
        color = GREEN if rs >= 70 else (AMBER if rs >= 50 else GREY)
        sectors.append({
            "name": sector_name, "rs": f"{rs:.0f}",
            "countLabel": f"({int(row['Ticker_Count'])})",
            "barWidth": f"{round(rs / max_rs * 100)}%",
            "barColor": color,
        })
    return sectors


def _most_recent_trading_day(as_of_date):
    """Walks backward from as_of_date (inclusive) to the most recent real
    NSE trading day -- same weekday+holiday-calendar convention
    ui/header.py's get_market_status() already uses for the OPEN/CLOSED
    badge, not a new trading-calendar concept. get_nse_holidays() is
    disk-cached (REFRESH_INTERVAL_DAYS), so calling this once per
    candidate on every dashboard render is cheap, not a live NSE fetch
    each time."""
    from market_data.holiday_calendar import get_nse_holidays

    holidays = get_nse_holidays()
    d = as_of_date
    while d.weekday() >= 5 or d in holidays:
        d -= timedelta(days=1)
    return d


def format_stale_data_notice(symbol: str, data_last_date, scan_date) -> str | None:
    """Warns when a candidate's own OHLCV history predates the most
    recent real NSE trading day as of the scan -- catches a silent
    per-ticker Phase 3/4 fetch failure within an otherwise-successful
    scan: the ticker still lands in records_df with a real category
    (categorize() ran fine against whatever stale data was already on
    disk), so nothing else would otherwise signal that its chart/card is
    showing day(s)-old data. None when the data is current (the common
    case).

    Compared against the most recent TRADING day, not the scan's
    calendar date directly (2026-08-22 fix) -- a scan run on a weekend or
    NSE holiday has no newer trading data to compare against by
    definition, so the raw calendar-date comparison this used to do
    fired a false "not refreshed" warning on every single non-trading-day
    scan, even though the cached data was already exactly as current as
    it could possibly be. Confirmed live: a Saturday scan flagged
    Friday's (correct, complete) data as stale.

    Compared as DATES, not datetimes -- a same-day scan naturally uses
    whatever the day's own last-published trading data is, regardless of
    what time within the day the scan itself ran.

    Does NOT cover a ticker that fell out of today's screened universe
    entirely (e.g. a prior-day mover no longer matching Leadership's
    screen.query) -- such a ticker has no card/chart anywhere in
    records_df to attach this notice to; it's simply absent from today's
    dashboard, not present-but-stale. That's a different, currently
    unbuilt surface (a "recently dropped from screen" view), not this
    function's job."""
    if data_last_date is None or scan_date is None:
        return None

    data_date = data_last_date.date() if hasattr(data_last_date, "date") else data_last_date
    scan_only_date = scan_date.date() if hasattr(scan_date, "date") else scan_date

    effective_trading_date = _most_recent_trading_day(scan_only_date)

    if data_date >= effective_trading_date:
        return None

    return f"Last scanned {data_date:%Y-%m-%d} — {symbol} data not refreshed in the latest scan"


def build_chart_view(
    history: pd.DataFrame, symbol: str, price: float, change_pct: Optional[float], sector: str,
    scan_date=None,
) -> dict:
    """Chart panel -- real OHLCV + EMA_20/EMA_50 (already-computed columns
    in data/patterns/*.parquet, not recomputed here). Pre-renders all
    three ranges (1M/3M/6M) server-side rather than a client-side
    charting engine -- range switching is a JS show/hide of pre-rendered
    blocks, same visual result as the mockup, simpler and independently
    testable in Python. Called once per EXECUTE/WATCHLIST candidate (see
    build_dashboard_context()'s all_charts) so every candidate has its own
    real, independently rendered chart ready ahead of time -- clicking a
    candidate card re-points the chart panel to it client-side
    (falconOpenCandidate() in dashboard_template.html toggles which
    pre-rendered [data-chart-panel] is shown, keyed by symbol) alongside
    opening its detail modal, matching the mockup's own coupled behavior."""
    ranges = {"1M": 22, "3M": 66, "6M": 120}
    range_blocks = {}

    for label, n in ranges.items():
        window = history.tail(n).reset_index(drop=True)
        if window.empty:
            range_blocks[label] = {"candles": [], "volumeBars": [], "ema20Points": "", "ema50Points": ""}
            continue

        vals = pd.concat([window["High"], window["Low"], window["EMA_20"], window["EMA_50"]]).dropna()
        v_max, v_min = vals.max(), vals.min()
        v_range = max(v_max - v_min, 0.01)

        def to_y_pct(v):
            if pd.isna(v):
                return 50.0
            return (v_max - v) / v_range * 100

        candles = []
        for _, c in window.iterrows():
            up = c["Close"] >= c["Open"]
            color = GREEN if up else RED
            body_top = to_y_pct(max(c["Open"], c["Close"]))
            body_bottom = to_y_pct(min(c["Open"], c["Close"]))
            body_height = max(body_bottom - body_top, 0.5)
            wick_top = to_y_pct(c["High"])
            wick_bottom = to_y_pct(c["Low"])
            wick_height = max(wick_bottom - wick_top, 0.3)
            candles.append({
                "wickStyle": f"position:absolute;top:{wick_top:.2f}%;left:50%;width:1px;"
                             f"height:{wick_height:.2f}%;background:{color};transform:translateX(-50%);",
                "bodyStyle": f"position:absolute;top:{body_top:.2f}%;left:15%;width:70%;"
                             f"height:{body_height:.2f}%;background:{color};border-radius:1px;",
            })

        max_vol = window["Volume"].max() or 1
        volume_bars = []
        for _, c in window.iterrows():
            pct = max((c["Volume"] / max_vol) * 100, 4) if pd.notna(c["Volume"]) else 4
            vol_color = "oklch(0.72 0.19 150 / 0.45)" if c["Close"] >= c["Open"] else "oklch(0.68 0.2 25 / 0.45)"
            volume_bars.append({"heightPct": f"{pct:.1f}%", "color": vol_color})

        def points_str(series):
            n_pts = len(series)
            if n_pts == 0:
                return ""
            return " ".join(
                f"{(i + 0.5) / n_pts * 100:.3f},{to_y_pct(v):.2f}"
                for i, v in enumerate(series.tolist())
            )

        range_blocks[label] = {
            "candles": candles, "volumeBars": volume_bars,
            "ema20Points": points_str(window["EMA_20"]), "ema50Points": points_str(window["EMA_50"]),
        }

    stale_notice = (
        format_stale_data_notice(symbol, history["Date"].max(), scan_date)
        if not history.empty else None
    )

    return {
        "symbol": symbol,
        "priceFmt": _fmt_price(price),
        "changeFmt": _fmt_pct(change_pct),
        "changeColor": _change_color(change_pct),
        "sector": sector or NA,
        "ranges": range_blocks,
        "staleNotice": stale_notice,
    }


def fetch_fundamentals_view(symbol: str) -> list[dict]:
    """Fundamentals panel -- merges the three real fundamental sources
    already used elsewhere in this codebase (fundamental_cache,
    corporate_engine, institutional_engine's Yahoo-only snapshot -- no
    Screener.in session here, matching app.py's own existing detail-panel
    pattern, not live_scorer.py's batch-session one). Cached at the
    source (fundamental_cache.py's own TTL), so calling this per shown
    candidate is cheap even though score_live_candidates() already
    fetched the same data once during scoring -- records_df doesn't
    persist raw fundamental values today, only categorize()'s decision
    output, so this is a deliberate second (cached) read, not a
    duplicated network cost.

    No real P/E-vs-sector data source exists anywhere in this codebase
    -- honestly omitted (NA), not fabricated.
    """
    from fundamental_analysis.fundamental_cache import get_fundamentals
    from fundamental_analysis.corporate_engine import corporate_engine
    from fundamental_analysis.institutional_engine import institutional_engine
    from fundamental_analysis.screener_fundamentals_store import (
        get_pe_ratio_display, get_industry_pe_display,
    )
    from common.utils import sentinel_to_display

    try:
        base = get_fundamentals(symbol)
    except Exception:
        base = {}
    try:
        comprehensive = corporate_engine.get_comprehensive_fundamentals(symbol)
    except Exception:
        comprehensive = {}
    try:
        shareholding = institutional_engine.get_shareholding_profile(symbol)
    except Exception:
        shareholding = {}

    def d(value) -> str:
        display = sentinel_to_display(value) if value is not None else NA
        return display if display not in (None, "", "N/A", "DATA_GAP", "UNKNOWN") else NA

    days_to_earnings = comprehensive.get("days_to_earnings")
    earnings_str = NA if days_to_earnings is None or days_to_earnings == 999 else f"{days_to_earnings} days"

    # P/E vs Sector (2026-08-20): both values come from the Screener
    # fundamentals store now (docs/known_data_issues.md) -- "P/E vs
    # Sector" only when BOTH the company's own P/E and Screener's
    # peer/sector-average "Ind PE" are real; if either is missing, an
    # honest NA rather than a half-comparison that implies more than the
    # data supports.
    pe = get_pe_ratio_display(symbol)
    industry_pe = get_industry_pe_display(symbol)
    pe_vs_sector = NA if pe == "N/A" or industry_pe == "N/A" else f"{pe} vs {industry_pe}"

    return [
        {"k": "ROCE", "v": d(base.get("roce"))},
        {"k": "Revenue Growth (YoY)", "v": d(comprehensive.get("revenue_yoy_quarterly_growth"))},
        {"k": "Net Income Growth (YoY)", "v": d(comprehensive.get("net_income_yoy_quarterly_growth"))},
        {"k": "Margin Trend", "v": d(comprehensive.get("margin_trend_yoy"))},
        {"k": "Debt / Equity", "v": d(base.get("debt_to_equity"))},
        {"k": "P/E vs Sector", "v": pe_vs_sector},
        {"k": "Institutional Sponsorship", "v": d(shareholding.get("institutional_sponsorship"))},
        {"k": "Promoter Holding", "v": d(shareholding.get("promoter_holding"))},
        {"k": "Days to Earnings", "v": earnings_str},
    ]


def build_score_waterfall(confidence_score: float, contributing_factors: list[str]) -> list[dict]:
    """Composite-score breakdown -- confidence_score/contributing_factors
    are categorize()'s OLD additive 0-100 point system, still computed
    (compute_score()) and returned, but NO LONGER what decides EXECUTE
    vs. ALERT_WATCHLIST as of Phase 4.6 (the calibrated model's
    predicted_p does that now, via coefficients on standardized features
    -- not a simple additive breakdown, since a logistic sigmoid isn't
    linear). Deliberately captioned in the template as the composite
    score's own breakdown, not relabeled as "why predicted_p is what it
    is" -- conflating the two would misrepresent which number actually
    drove the category. Real per-factor point deltas aren't tracked
    individually (compute_score() returns only the final sum), so each
    factor is shown as a labeled contributor without an individual point
    value, rather than fabricating a per-factor split that was never
    actually computed."""
    rows = [{"label": "Base Score", "value": "", "isBase": True}]
    for factor in contributing_factors:
        rows.append({"label": factor.replace("_", " ").title(), "value": "", "isBase": False})
    return rows


def build_candidate_view(row: pd.Series, history: pd.DataFrame | None, scan_date=None) -> dict:
    """One EXECUTE/WATCHLIST card + its full modal detail. predicted_p
    (not confidence_score) drives the confidence gauge, per the build
    instructions -- the calibrated model's real probability, which is
    what actually decided this candidate's category."""
    category = row.get("category")
    style = CATEGORY_STYLE.get(category, {"label": category, "color": GREY, "bg": "oklch(0.28 0.012 250)"})

    change_pct = compute_day_change_pct(history) if history is not None else None
    predicted_p = row.get("predicted_p")
    conf_display = NA if predicted_p is None or pd.isna(predicted_p) else f"{predicted_p * 100:.0f}"
    conf_frac = 0.0 if predicted_p is None or pd.isna(predicted_p) else float(predicted_p)

    factors = [f for f in str(row.get("contributing_factors") or "").split(",") if f]
    risk_flags = [f for f in str(row.get("fakeout_risk_flags") or "").split(",") if f]
    caps = [c for c in str(row.get("caps_applied") or "").split(",") if c]

    rs_rating = row.get("RS_Rating")
    rs_display = NA if rs_rating is None or pd.isna(rs_rating) else f"{rs_rating:.0f}"

    entry, stop_loss, target = row.get("entry"), row.get("stop_loss"), row.get("target")
    reward_risk = row.get("reward_risk")

    stale_notice = (
        format_stale_data_notice(row["Symbol"], history["Date"].max(), scan_date)
        if history is not None and not history.empty else None
    )

    return {
        "id": row["Symbol"],
        "symbol": row["Symbol"],
        "staleNotice": stale_notice,
        "priceFmt": _fmt_price(row.get("Price")),
        "price_raw": row.get("Price"),
        "changeFmt": _fmt_pct(change_pct),
        "changeColor": _change_color(change_pct),
        "category": category,
        "categoryLabel": style["label"],
        "categoryColor": style["color"],
        "categoryBg": style["bg"],
        "conf": conf_display,
        "confFraction": conf_frac,
        "gaugeBg": (f"conic-gradient({style['color']} {round(conf_frac * 360)}deg, "
                    f"oklch(0.28 0.012 250) {round(conf_frac * 360)}deg)"),
        "factors": _factor_chips(factors, row),
        "riskFlags": _risk_flag_chips(risk_flags, row),
        "vwapReclaim": get_vwap_reclaim_display(row),
        "cap": ", ".join(caps) if caps else None,
        "sector": row.get("Sector") or NA,
        "rsRating": rs_display,
        # Trade plan -- real values from categorize(), including WHY the
        # stop/target sit where they do (2.2/I-6 provenance), not just
        # the numbers.
        "plan": {
            "entry": _fmt_price(entry), "target": _fmt_price(target), "stop": _fmt_price(stop_loss),
            "rr": NA if reward_risk is None or pd.isna(reward_risk) else f"{reward_risk:.1f}",
            "stopProvenance": row.get("stop_provenance") or NA,
            "targetProvenance": row.get("target_provenance") or NA,
        },
        "confidenceScore": row.get("confidence_score"),
        "waterfall": build_score_waterfall(row.get("confidence_score") or 0.0, factors),
        "fundamentals": fetch_fundamentals_view(row["Symbol"]),
    }


def build_monitor_candidate_view(row: pd.Series, history: pd.DataFrame | None, scan_date=None) -> dict:
    """MONITOR-tier card + light modal detail -- deliberately missing
    every field build_candidate_view() computes from the calibrated
    model or categorize()'s post-model logic (conf/plan/waterfall/
    fundamentals), since MONITOR candidates are capped BEFORE reaching
    either (B-8, leadership_decision_engine.py: score>=40 but no
    confirmed pattern -- the ONLY way to land here, so "why capped" is
    unconditionally "No confirmed breakout yet", never fabricated
    per-candidate detail beyond that).

    factors/riskFlags are NOT in that "capped before reaching" list --
    verified directly against leadership_decision_engine.py: categorize()
    calls get_contributing_factors()/get_fakeout_risk_flags()
    unconditionally for every non-AVOID candidate, reading only
    candidate/sector_row technical & fundamental fields (Delivery_Pct,
    RSI_14, macd_signal, Pct_Uptrend, margin_trend_yoy, promoter_trend),
    none of which require a confirmed pattern or the model. A prior
    version of this function hardcoded both to [] anyway, silently
    discarding real values decision_engine.live_scorer.py had already put
    on this same row -- fixed here to read them the same way
    build_candidate_view() does.

    Shares CATEGORY_STYLE/id/symbol/price/change/sector/conf field NAMES
    with build_candidate_view()'s output so this can sit in the same
    all_candidates list ("All Filtered Candidates" table +
    falconOpenCandidate() click handling) without the template needing a
    second code path for those shared sections -- conf stays NA (the
    model genuinely was never consulted), unlike factors/riskFlags above.
    """
    style = CATEGORY_STYLE["MONITOR"]

    change_pct = compute_day_change_pct(history) if history is not None else None

    factors = [f for f in str(row.get("contributing_factors") or "").split(",") if f]
    risk_flags = [f for f in str(row.get("fakeout_risk_flags") or "").split(",") if f]

    rs_rating = row.get("RS_Rating")
    rs_display = NA if rs_rating is None or pd.isna(rs_rating) else f"{rs_rating:.0f}"

    setup_state = None
    if history is not None and not history.empty:
        setup_state = get_monitor_setup_state(history.iloc[-1].to_dict())

    stale_notice = (
        format_stale_data_notice(row["Symbol"], history["Date"].max(), scan_date)
        if history is not None and not history.empty else None
    )

    return {
        "id": row["Symbol"],
        "symbol": row["Symbol"],
        "staleNotice": stale_notice,
        "priceFmt": _fmt_price(row.get("Price")),
        "price_raw": row.get("Price"),
        "changeFmt": _fmt_pct(change_pct),
        "changeColor": _change_color(change_pct),
        "category": "MONITOR",
        "categoryLabel": style["label"],
        "categoryColor": style["color"],
        "categoryBg": style["bg"],
        # conf stays NA -- the model genuinely was never consulted (see
        # docstring). factors/riskFlags are real when categorize() found
        # any, same shape (label+tooltip dicts) as build_candidate_view().
        "conf": NA,
        "factors": _factor_chips(factors, row),
        "riskFlags": _risk_flag_chips(risk_flags, row),
        "sector": row.get("Sector") or NA,
        "rsRating": rs_display,
        # MONITOR-specific: real Trend_State (records_df's own column,
        # not re-derived), the one, always-correct reason this tier caps
        # here, and whatever real partial pattern state exists.
        "trendState": row.get("Trend_State") or NA,
        "monitorReason": "No confirmed breakout yet",
        "setupState": setup_state,
    }


def build_dashboard_context(
    records_df: pd.DataFrame,
    history_by_symbol: dict[str, pd.DataFrame],
    regime_snapshot: dict | None,
    index_quotes: dict,
    active_strategy_tab: str = "leadership",
    last_scan_completed_at=None,
) -> dict:
    """Top-level orchestrator -- the full template-variable dict for
    ui/dashboard_template.html, mirroring the mockup's own renderVals()
    output shape.

    last_scan_completed_at : the timestamp the current records_df was
        produced at (st.session_state.last_scan_completed_at) -- threaded
        into build_candidate_view()/build_chart_view() so each card/chart
        can carry format_stale_data_notice()'s warning when that specific
        candidate's own OHLCV history predates this scan (a silent
        per-ticker Phase 3/4 fetch failure, not a rendering bug). None
        degrades to no notice on any candidate, same as today's
        behavior."""
    market_pulse = build_market_pulse(regime_snapshot, index_quotes)
    sectors = build_sector_view(records_df) if not records_df.empty else []

    # MONITOR included here (not just EXECUTE/ALERT_WATCHLIST) as of the
    # MONITOR-watchlist-section spec -- real categorize() output that was
    # previously computed every scan and then silently dropped before
    # reaching this function at all (confirmed live: a real scan on
    # 2026-08-20 categorized 20 real MONITOR candidates, 0 EXECUTE, 0
    # WATCHLIST -- entirely invisible under the old two-category filter).
    real = records_df[records_df["category"].isin(["EXECUTE", "ALERT_WATCHLIST", "MONITOR"])].copy() if not records_df.empty else records_df

    execute_candidates = []
    watchlist_candidates = []
    monitor_candidates = []
    all_candidates = []
    # One real chart per EXECUTE/WATCHLIST/MONITOR candidate (not just
    # whichever one starts visible) -- clicking a candidate re-points the
    # main chart panel to it client-side (falconOpenCandidate() in
    # dashboard_template.html toggles which [data-chart-panel] is shown,
    # keyed by symbol), so every candidate needs its own real, independently
    # computed EMA/candle/volume data ready ahead of time rather than a
    # relabeled copy of whichever chart happened to render first. Reuses
    # history_by_symbol, which ui/dashboard.py already loads for every real
    # candidate (previously only used for the day-change % on its card) --
    # no extra I/O. Pre-fetching all of them (not a per-click round trip)
    # is deliberate: a real live scan's EXECUTE+WATCHLIST+MONITOR total was
    # 20 candidates (2026-08-20) -- build_chart_view() is pure local
    # pandas/string work per candidate, no network calls, so pre-rendering
    # even a few hundred of these costs well under a second total, far
    # cheaper than the actual scan pipeline that produces records_df in
    # the first place. A round trip would add real complexity (a new
    # Streamlit callback path, loading states) to solve a cost problem
    # that doesn't exist at this scale.
    all_charts = []

    for _, row in real.iterrows():
        history = history_by_symbol.get(row["Symbol"])
        category = row["category"]

        if category == "MONITOR":
            view = build_monitor_candidate_view(row, history, scan_date=last_scan_completed_at)
            monitor_candidates.append(view)
        else:
            view = build_candidate_view(row, history, scan_date=last_scan_completed_at)
            if category == "EXECUTE":
                execute_candidates.append(view)
            else:
                watchlist_candidates.append(view)
        all_candidates.append(view)

        if history is not None and not history.empty:
            change_pct = compute_day_change_pct(history)
            all_charts.append(
                build_chart_view(
                    history, view["symbol"], view["price_raw"], change_pct, view["sector"],
                    scan_date=last_scan_completed_at,
                )
            )

    if execute_candidates:
        default_chart_symbol = execute_candidates[0]["symbol"]
    elif watchlist_candidates:
        default_chart_symbol = watchlist_candidates[0]["symbol"]
    elif monitor_candidates:
        default_chart_symbol = monitor_candidates[0]["symbol"]
    else:
        default_chart_symbol = None

    # Kept for backward compatibility (the initially-visible chart, same
    # selection as before this candidate ever had its own [data-chart-panel])
    # -- the template now iterates all_charts and shows default_chart_symbol's
    # panel first, but "chart" alone is still enough to know whether there's
    # anything chartable at all.
    chart = next((c for c in all_charts if c["symbol"] == default_chart_symbol), None)

    strategy_tabs = [
        {"key": "leadership", "label": "Leadership", "comingSoon": False},
        {"key": "emergent", "label": "Emergent", "comingSoon": True},
        {"key": "reversal", "label": "Reversal", "comingSoon": True},
    ]

    return {
        "market_pulse": market_pulse,
        "sectors": sectors,
        "chart": chart,
        "all_charts": all_charts,
        "default_chart_symbol": default_chart_symbol,
        "strategy_tabs": strategy_tabs,
        "active_strategy_tab": active_strategy_tab,
        "execute_candidates": execute_candidates,
        "watchlist_candidates": watchlist_candidates,
        "monitor_candidates": monitor_candidates,
        "all_candidates": all_candidates,
        "na": NA,
    }
