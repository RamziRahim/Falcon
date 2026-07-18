"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : shareholding_scraper.py
Package     : Candidate Generation / Sources

Purpose
-------
Extracts per-ticker Promoter/FII/DII shareholding trend (QoQ) from
Screener.in's Shareholding Pattern table, reusing the existing
authenticated session (candidate_generation/auth.py + session.py).

Confirmed via a live Playwright session (not guessed): the #shareholding
section's "Quarterly" table is present directly in the page's DOM on
load -- no tab click needed, unlike the AJAX-loaded per-entity "View
Shareholders" breakdown (a different feature on the same page, triggered
only on click). Row labels are "Promoters", "FIIs", "DIIs", "Government",
"Public" (each followed by a decorative "+" expand icon in the DOM text),
plus a "No. of Shareholders" sub-row. Columns are quarters in ASCENDING
chronological order (oldest first, most recent last) -- the opposite of
yfinance's quarterly_financials, which is most-recent-first.
===============================================================================
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config import DATA_FOLDER

from common.logger import get_logger
from candidate_generation.session import SourceSession

logger = get_logger("shareholding_scraper")

CACHE_DIR = Path(DATA_FOLDER) / "shareholding_trend_cache"

# Shareholding is disclosed quarterly -- refresh on a long cycle, matching
# holiday_calendar.py's cadence, not the per-scan default.
REFRESH_INTERVAL_DAYS = 30

ROW_LABELS = {
    "promoter": "Promoters",
    "fii": "FIIs",
    "dii": "DIIs",
}

EMPTY_RESULT = {
    "promoter_pct_latest": None, "promoter_trend": None,
    "fii_pct_latest": None, "fii_trend": None,
    "dii_pct_latest": None, "dii_trend": None,
}


def _cache_path_for(company_slug: str) -> Path:
    return CACHE_DIR / f"{company_slug.upper()}.json"


def _load_cache_if_fresh(company_slug: str) -> Optional[dict]:

    cache_path = _cache_path_for(company_slug)

    if not cache_path.exists():
        return None

    try:

        with open(cache_path, "r", encoding="utf-8") as fh:
            cached = json.load(fh)

        fetched_at = datetime.fromisoformat(cached["fetched_at"])

        if datetime.now() - fetched_at > timedelta(days=REFRESH_INTERVAL_DAYS):
            return None

        return cached["result"]

    except Exception as ex:

        logger.warning("Failed to load shareholding cache for %s: %s", company_slug, ex)
        return None


def _save_cache(company_slug: str, result: dict) -> None:

    try:

        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        with open(_cache_path_for(company_slug), "w", encoding="utf-8") as fh:
            json.dump({"fetched_at": datetime.now().isoformat(), "result": result}, fh, indent=2)

    except Exception as ex:

        logger.warning("Failed to save shareholding cache for %s: %s", company_slug, ex)


def _classify_trend(current: float, prior: float) -> str:
    if current > prior:
        return "INCREASING"
    if current < prior:
        return "DECREASING"
    return "FLAT"


def _parse_pct(text: str) -> float:
    try:
        return float(text.strip().replace("%", "").replace(",", ""))
    except (ValueError, AttributeError):
        return float("nan")


def _extract_from_page(page) -> dict:
    """
    Parses the #shareholding section's quarterly table. Returns
    EMPTY_RESULT (never raises) if the section/table/a given row isn't
    found -- degrades one category at a time rather than all-or-nothing.
    """

    result = dict(EMPTY_RESULT)

    table = page.locator("#shareholding table.data-table").first

    if table.count() == 0:
        logger.warning("Shareholding table not found on page.")
        return result

    rows = table.locator("tbody tr")
    row_count = rows.count()

    for key, label in ROW_LABELS.items():

        for i in range(row_count):

            row = rows.nth(i)
            cells = row.locator("td")
            cell_count = cells.count()

            if cell_count == 0:
                continue

            label_text = cells.nth(0).inner_text().strip()

            if not label_text.startswith(label):
                continue

            # First <td> is the row label; remaining are quarter values in
            # ascending chronological order -- last two are latest/prior.
            if cell_count < 3:
                break

            latest = _parse_pct(cells.nth(cell_count - 1).inner_text())
            prior = _parse_pct(cells.nth(cell_count - 2).inner_text())

            if not math.isnan(latest) and not math.isnan(prior):
                result[f"{key}_pct_latest"] = latest
                result[f"{key}_trend"] = _classify_trend(latest, prior)

            break

    return result


def get_shareholding_trend(session: SourceSession, company_slug: str) -> dict:
    """
    Visits https://www.screener.in/company/{company_slug}/ using the
    existing authenticated session and extracts Promoter/FII/DII
    shareholding % for the latest and prior quarter, classifying the QoQ
    trend as INCREASING/DECREASING/FLAT.

    Cached per company for REFRESH_INTERVAL_DAYS -- shareholding is
    disclosed quarterly, no need to refetch every scan.

    Returns a dict of Nones (see EMPTY_RESULT), with a logged warning, if
    the section/table isn't found or the fetch fails -- never crashes the
    fundamentals fetch over this one field.
    """

    cached = _load_cache_if_fresh(company_slug)

    if cached is not None:
        return cached

    try:

        page = session.page

        if page is None:
            raise ValueError("SourceSession has no active page")

        url = f"https://www.screener.in/company/{company_slug}/"

        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1000)

        result = _extract_from_page(page)

        _save_cache(company_slug, result)

        return result

    except Exception as ex:

        logger.warning("Shareholding trend fetch failed for %s: %s", company_slug, ex)
        return dict(EMPTY_RESULT)
