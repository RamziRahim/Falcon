"""
===============================================================================
Falcon AI Swing Trading Platform
Module  : dashboard.py
Package : ui

Purpose
-------
Streamlit-facing wrapper around ui/dashboard_data.py (pure data adapter)
and ui/dashboard_template.html (Jinja2, converted from
reference_mockup_annotated.html's markup byte-for-byte). Renders the full
dashboard as one embedded component via st.components.v1.html() -- app.py
keeps session state and the scan trigger; this module owns the visible
surface.

st.components.v1.html() renders in a sandboxed iframe (its own document),
so the Jinja2-rendered body content is wrapped here in a complete HTML
document (fonts, base styles, and real :hover CSS -- the mockup's own
style-hover attribute isn't real CSS, browsers ignore it silently;
.falcon-card-hover/.falcon-row-hover:hover below reproduce the intended
effect for real).
===============================================================================
"""
from __future__ import annotations

import os
from datetime import datetime

import jinja2
import pandas as pd
import pytz
import streamlit.components.v1 as components

from ui.dashboard_data import build_dashboard_context

IST = pytz.timezone("Asia/Kolkata")

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(_TEMPLATE_DIR),
    autoescape=False,  # every value here is either a Falcon-computed number/string or a style value we built ourselves -- no user-supplied HTML is ever interpolated
)

_DOCUMENT_SHELL = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  body{{margin:0;background:oklch(0.16 0.012 250);}}
  *{{box-sizing:border-box;}}
  ::-webkit-scrollbar{{width:8px;height:8px;}}
  ::-webkit-scrollbar-thumb{{background:oklch(0.32 0.012 250);border-radius:4px;}}
  .mono{{font-family:'JetBrains Mono',monospace;}}
  .fadein{{animation:fadein .15s ease-out;}}
  @keyframes fadein{{from{{opacity:0;transform:translateY(4px);}}to{{opacity:1;transform:none;}}}}
  /* Real :hover rules -- the mockup's own style-hover attribute isn't
     real CSS and browsers ignore it silently; this reproduces the
     intended effect. */
  .falcon-card-hover:hover{{background:oklch(0.225 0.014 250) !important;}}
  .falcon-row-hover:hover{{background:oklch(0.2 0.014 250) !important;}}
  /* Which candidate's chart the main panel currently shows -- toggled by
     falconHighlightChartedCard() in dashboard_template.html on click and
     on initial page load, so it's never ambiguous after several clicks. */
  .falcon-card-active{{border-color:oklch(0.72 0.19 150) !important;box-shadow:0 0 0 1px oklch(0.72 0.19 150 / 0.5);}}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def _session_label(now: datetime) -> str:
    return f"NSE · {now.strftime('%H:%M')} IST"


def _is_market_open(now: datetime) -> bool:
    """Derives from ui.header.get_market_status() -- the single real
    source of the OPEN/CLOSED determination -- rather than reimplementing
    the weekday/hours/holiday check a second time, which could silently
    drift from it."""
    from ui.header import get_market_status

    return "OPEN" in get_market_status(now)


def _load_price_history(symbol: str) -> pd.DataFrame | None:
    path = f"data/patterns/{symbol}.parquet"
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_parquet(path)
        df["Date"] = pd.to_datetime(df.get("Date", df.index))
        return df.sort_values("Date").reset_index(drop=True)
    except Exception:
        return None


def render(records_df: pd.DataFrame, height: int = 1400, last_scan_completed_at: datetime | None = None) -> None:
    """Renders the full Falcon dashboard from real scan data.

    records_df : the exact DataFrame app.py already stores in
        st.session_state.screener_records -- decision_engine.live_scorer.
        score_live_candidates()'s own output (category/predicted_p/
        model_version/entry/stop_loss/target/.../RS_Rating/Sector, all
        real, no placeholder columns invented here).

    last_scan_completed_at : st.session_state.last_scan_completed_at --
        threaded through to build_dashboard_context() so any candidate
        whose own OHLCV history predates this scan gets a visible
        staleness notice (format_stale_data_notice()) instead of silently
        showing old data with no signal that anything's off.
    """
    from ui.header import get_index_quotes, get_market_regime_snapshot

    now = datetime.now(IST)

    real_symbols = []
    if not records_df.empty and "category" in records_df.columns:
        # MONITOR included here -- confirmed live (2026-08-21) that
        # leaving it out of THIS filter (while build_dashboard_context()'s
        # own internal filter already included MONITOR) meant
        # history_by_symbol never had an entry for any MONITOR ticker, so
        # every MONITOR candidate's `history` came through as None: no
        # chart, no setup-state, no real change% -- clicking a MONITOR
        # card found no matching [data-chart-panel] to switch to at all.
        real_symbols = records_df[
            records_df["category"].isin(["EXECUTE", "ALERT_WATCHLIST", "MONITOR"])
        ]["Symbol"].tolist()
    history_by_symbol = {sym: _load_price_history(sym) for sym in real_symbols}

    context = build_dashboard_context(
        records_df=records_df,
        history_by_symbol=history_by_symbol,
        regime_snapshot=get_market_regime_snapshot(),
        index_quotes=get_index_quotes(),
        last_scan_completed_at=last_scan_completed_at,
    )
    context["session_label"] = _session_label(now)
    context["market_open"] = _is_market_open(now)

    body_html = _jinja_env.get_template("dashboard_template.html").render(**context)
    full_html = _DOCUMENT_SHELL.format(body=body_html)

    components.html(full_html, height=height, scrolling=True)
