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
    from ui.header import MARKET_OPEN_TIME, MARKET_CLOSE_TIME
    from market_data.holiday_calendar import get_nse_holidays

    is_weekday = now.weekday() < 5
    is_trading_hours = MARKET_OPEN_TIME <= now.time() <= MARKET_CLOSE_TIME
    is_holiday = now.date() in get_nse_holidays()
    return is_weekday and is_trading_hours and not is_holiday


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


def render(records_df: pd.DataFrame, height: int = 1400) -> None:
    """Renders the full Falcon dashboard from real scan data.

    records_df : the exact DataFrame app.py already stores in
        st.session_state.screener_records -- decision_engine.live_scorer.
        score_live_candidates()'s own output (category/predicted_p/
        model_version/entry/stop_loss/target/.../RS_Rating/Sector, all
        real, no placeholder columns invented here).
    """
    from ui.header import get_index_quotes, get_market_regime_snapshot

    now = datetime.now(IST)

    real_symbols = []
    if not records_df.empty and "category" in records_df.columns:
        real_symbols = records_df[records_df["category"].isin(["EXECUTE", "ALERT_WATCHLIST"])]["Symbol"].tolist()
    history_by_symbol = {sym: _load_price_history(sym) for sym in real_symbols}

    context = build_dashboard_context(
        records_df=records_df,
        history_by_symbol=history_by_symbol,
        regime_snapshot=get_market_regime_snapshot(),
        index_quotes=get_index_quotes(),
    )
    context["session_label"] = _session_label(now)
    context["market_open"] = _is_market_open(now)

    body_html = _jinja_env.get_template("dashboard_template.html").render(**context)
    full_html = _DOCUMENT_SHELL.format(body=body_html)

    components.html(full_html, height=height, scrolling=True)
