"""
Falcon
Module: table_parser.py
Version: 2.0.0

Parses Screener.in result table directly from the Playwright page.

This implementation intentionally does NOT use pandas.read_html().

Each HTML row becomes one stock record.

Responsibilities
----------------
• Ignore repeated header rows
• Extract Symbol and Name together
• Parse numeric columns
• Return a clean DataFrame
"""

from __future__ import annotations

import re
from typing import List

import pandas as pd
from playwright.sync_api import Page

from common.logger import get_logger
from candidate_generation.exceptions import TableParsingError

logger = get_logger("table_parser")


SYMBOL_REGEX = re.compile(r"/company/([^/]+)/", re.IGNORECASE)


# Updated 2026-08-18 (fundamental-data-sourcing-to-Screener spec): the
# Screener ACCOUNT's own column preferences (screener.in/user/columns/ --
# an account-level, persistent setting applied to every future scrape with
# this login, not a per-query URL param or a UI step this scraper has to
# drive at scrape time -- confirmed live, no such URL param exists) now
# include 9 new ratio columns beyond the original 13: Debt / Eq,
# Prom. Hold. %, Change in Prom Hold %, FII Hold %, Chg in FII Hold %,
# DII Hold %, Chg in DII Hold %, OPM Qtr %, and OPM PY Qtr % (OPM the same
# quarter one year ago -- needed to classify margin_trend_yoy the same
# YoY-comparison way the old Yahoo-sourced version did; a single "OPM Qtr %"
# snapshot alone can't show a trend direction).
#
# This account is on Screener's free tier, hard-capped at 15 selected
# columns -- already at that cap before OPM PY Qtr % was added, so "RSI"
# was dropped to make room (confirmed harmless: Screener's RSI was never
# consumed anywhere in this codebase -- Falcon computes its own RSI_14
# from real OHLCV data independently). Three further OLD columns are also
# gone from the account's column list entirely (not just reordered):
# "Mar Cap Rs.Cr.", "Div Yld %", "Sales Qtr Rs.Cr." -- confirmed harmless
# before removing them here too: none of the three is read anywhere
# outside this file and screen.query's own filter criteria (unrelated to
# display columns).
#
# Confirmed the resulting real column ORDER via direct DOM inspection of
# an actual query run (not assumed to match the order columns were added
# in) -- see the positional mapping in parse_results() below, cross-
# checked against MCX's real, independently-known values (0% promoter
# holding, near-zero debt -- both correct, well-known facts about MCX's
# demutualized exchange structure).
#
# EXPECTED_COLUMNS must always match the account's REAL current column
# list -- any future column-preference change on the Screener account
# (adding/removing/reordering, or hitting the free-tier cap again)
# requires re-verifying this list the same way (live DOM inspection), not
# just appending or assuming the UI-addition order.
EXPECTED_COLUMNS = [
    "Name",
    "Symbol",
    "CMP Rs.",
    "P/E",
    "NP Qtr Rs.Cr.",
    "Qtr Profit Var %",
    "Qtr Sales Var %",
    "ROCE %",
    "CMP / BV",
    "Debt / Eq",
    "Prom. Hold. %",
    "Change in Prom Hold %",
    "Chg in FII Hold %",
    "DII Hold %",
    "Chg in DII Hold %",
    "OPM Qtr %",
    "FII Hold %",
    "OPM PY Qtr %",
    "50 DMA Rs.",
    "200 DMA Rs.",
]


def _to_number(value: str):
    """
    Convert Screener numeric text to float.

    Empty values remain None.
    """

    value = value.strip()

    if value == "":
        return None

    value = value.replace(",", "")

    try:
        return float(value)
    except Exception:
        return value


def parse_results(page: Page) -> pd.DataFrame:
    """
    Parse Screener result table.

    Returns
    -------
    pandas.DataFrame
    """

    try:

        rows = page.locator("tr[data-row-company-id]")

        count = rows.count()

        logger.info("Found %d stock rows.", count)

        records: List[dict] = []

        for i in range(count):

            row = rows.nth(i)

            cells = row.locator("td")

            if cells.count() < 20:
                logger.warning(
                    "Skipping malformed row %d",
                    i + 1,
                )
                continue

            company_link = cells.nth(1).locator("a")

            name = company_link.inner_text().strip()

            href = company_link.get_attribute("href") or ""

            symbol = None

            match = SYMBOL_REGEX.search(href)

            if match:
                symbol = match.group(1).upper() + ".NS"

            values = []

            for j in range(2, cells.count()):
                values.append(
                    _to_number(
                        cells.nth(j).inner_text()
                    )
                )

            # Position mapping confirmed live against the account's real
            # current column order (see EXPECTED_COLUMNS' own comment) --
            # not the order columns were added in the Manage Columns UI.
            record = {
                "Name": name,
                "Symbol": symbol,
                "CMP Rs.": values[0],
                "P/E": values[1],
                "NP Qtr Rs.Cr.": values[2],
                "Qtr Profit Var %": values[3],
                "Qtr Sales Var %": values[4],
                "ROCE %": values[5],
                "CMP / BV": values[6],
                "Debt / Eq": values[7],
                "Prom. Hold. %": values[8],
                "Change in Prom Hold %": values[9],
                "Chg in FII Hold %": values[10],
                "DII Hold %": values[11],
                "Chg in DII Hold %": values[12],
                "OPM Qtr %": values[13],
                "FII Hold %": values[14],
                "OPM PY Qtr %": values[15],
                "50 DMA Rs.": values[16],
                "200 DMA Rs.": values[17],
            }

            records.append(record)

        df = pd.DataFrame(records)

        missing = set(EXPECTED_COLUMNS) - set(df.columns)

        if missing:
            raise TableParsingError(
                f"Missing columns: {missing}"
            )

        logger.info(
            "Parsed %d stocks successfully.",
            len(df),
        )

        return df

    except Exception as ex:

        raise TableParsingError(str(ex)) from ex


def has_next_page(page: Page) -> bool:
    """
    True when a "Next" pagination link is present on the currently-loaded
    results page.

    Screener's custom-query results always paginate at a fixed page size
    (Falcon requests the site's own maximum, 50/page) regardless of how
    many rows actually match the query -- a query matching more than 50
    stocks (e.g. the Leadership query's real 132-match, 3-page result set)
    silently returned only page 1's 50 rows before this existed. Confirmed
    live: the "Next" link is a plain `.pagination a` -- present on every
    page except the last, where Screener removes it entirely rather than
    disabling/greying it out, so a plain locator count is a reliable
    end-of-results signal.
    """
    return page.locator(".pagination a:has-text('Next')").count() > 0