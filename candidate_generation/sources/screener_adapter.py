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


EXPECTED_COLUMNS = [
    "Name",
    "Symbol",
    "CMP Rs.",
    "P/E",
    "Mar Cap Rs.Cr.",
    "Div Yld %",
    "NP Qtr Rs.Cr.",
    "Qtr Profit Var %",
    "Sales Qtr Rs.Cr.",
    "Qtr Sales Var %",
    "ROCE %",
    "CMP / BV",
    "RSI",
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

            if cells.count() < 15:
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

            record = {
                "Name": name,
                "Symbol": symbol,
                "CMP Rs.": values[0],
                "P/E": values[1],
                "Mar Cap Rs.Cr.": values[2],
                "Div Yld %": values[3],
                "NP Qtr Rs.Cr.": values[4],
                "Qtr Profit Var %": values[5],
                "Sales Qtr Rs.Cr.": values[6],
                "Qtr Sales Var %": values[7],
                "ROCE %": values[8],
                "CMP / BV": values[9],
                "RSI": values[10],
                "50 DMA Rs.": values[11],
                "200 DMA Rs.": values[12],
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