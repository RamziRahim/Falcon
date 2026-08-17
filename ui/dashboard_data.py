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
  - P/E vs Sector -- no P/E data source exists in fundamental_cache.py/
    corporate_engine.py.
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
from typing import Optional

import pandas as pd

GREEN = "oklch(0.72 0.19 150)"
AMBER = "oklch(0.78 0.16 80)"
RED = "oklch(0.68 0.2 25)"
GREY = "oklch(0.55 0.01 250)"

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
}

NA = "—"


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


def build_chart_view(history: pd.DataFrame, symbol: str, price: float, change_pct: Optional[float], sector: str) -> dict:
    """Chart panel -- real OHLCV + EMA_20/EMA_50 (already-computed columns
    in data/patterns/*.parquet, not recomputed here). Pre-renders all
    three ranges (1M/3M/6M) server-side rather than a client-side
    charting engine -- range switching is a JS show/hide of pre-rendered
    blocks, same visual result as the mockup, simpler and independently
    testable in Python. Known v1 simplification: clicking a candidate
    card opens its detail modal but does not also re-point this chart
    (the mockup's own openCandidate() coupled both) -- deferred, not
    silently dropped; flagged in the build report."""
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

    return {
        "symbol": symbol,
        "priceFmt": _fmt_price(price),
        "changeFmt": _fmt_pct(change_pct),
        "changeColor": _change_color(change_pct),
        "sector": sector or NA,
        "ranges": range_blocks,
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

    return [
        {"k": "ROCE", "v": d(base.get("roce"))},
        {"k": "Revenue Growth (YoY)", "v": d(comprehensive.get("revenue_yoy_quarterly_growth"))},
        {"k": "Net Income Growth (YoY)", "v": d(comprehensive.get("net_income_yoy_quarterly_growth"))},
        {"k": "Margin Trend", "v": d(comprehensive.get("margin_trend_yoy"))},
        {"k": "Debt / Equity", "v": d(base.get("debt_to_equity"))},
        {"k": "P/E vs Sector", "v": NA},
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


def build_candidate_view(row: pd.Series, history: pd.DataFrame | None) -> dict:
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

    return {
        "id": row["Symbol"],
        "symbol": row["Symbol"],
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
        "factors": factors,
        "riskFlags": risk_flags,
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


def build_dashboard_context(
    records_df: pd.DataFrame,
    history_by_symbol: dict[str, pd.DataFrame],
    regime_snapshot: dict | None,
    index_quotes: dict,
    active_strategy_tab: str = "leadership",
) -> dict:
    """Top-level orchestrator -- the full template-variable dict for
    ui/dashboard_template.html, mirroring the mockup's own renderVals()
    output shape."""
    market_pulse = build_market_pulse(regime_snapshot, index_quotes)
    sectors = build_sector_view(records_df) if not records_df.empty else []

    real = records_df[records_df["category"].isin(["EXECUTE", "ALERT_WATCHLIST"])].copy() if not records_df.empty else records_df

    execute_candidates = []
    watchlist_candidates = []
    all_candidates = []

    for _, row in real.iterrows():
        history = history_by_symbol.get(row["Symbol"])
        view = build_candidate_view(row, history)
        all_candidates.append(view)
        if row["category"] == "EXECUTE":
            execute_candidates.append(view)
        else:
            watchlist_candidates.append(view)

    if execute_candidates:
        chart_subject = execute_candidates[0]
    elif watchlist_candidates:
        chart_subject = watchlist_candidates[0]
    else:
        chart_subject = None

    chart = None
    if chart_subject is not None:
        history = history_by_symbol.get(chart_subject["symbol"])
        if history is not None and not history.empty:
            change_pct = compute_day_change_pct(history)
            chart = build_chart_view(
                history, chart_subject["symbol"], chart_subject["price_raw"], change_pct, chart_subject["sector"],
            )

    strategy_tabs = [
        {"key": "leadership", "label": "Leadership", "comingSoon": False},
        {"key": "emergent", "label": "Emergent", "comingSoon": True},
        {"key": "reversal", "label": "Reversal", "comingSoon": True},
    ]

    return {
        "market_pulse": market_pulse,
        "sectors": sectors,
        "chart": chart,
        "strategy_tabs": strategy_tabs,
        "active_strategy_tab": active_strategy_tab,
        "execute_candidates": execute_candidates,
        "watchlist_candidates": watchlist_candidates,
        "all_candidates": all_candidates,
        "na": NA,
    }
