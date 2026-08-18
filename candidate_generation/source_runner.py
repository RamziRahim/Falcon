"""
Falcon - Candidate Generation
Module: source_runner.py
Version: 1.1.0

Executes a single strategy against Screener.in and returns a
normalized candidate DataFrame.
"""

import pandas as pd
from playwright.sync_api import Page

from candidate_generation.session import SourceSession
from candidate_generation.strategy_loader import Strategy
from candidate_generation.exceptions import (
    SessionExpiredError,
    QueryExecutionError,
)
from candidate_generation.sources.screener_adapter import parse_results, has_next_page
from candidate_generation.normalizer import normalize_dataframe
from common.logger import get_logger

logger = get_logger("source_runner")


from config import (
    SCREENER_QUERY_URL,
    SCREENER_TIMEOUT,
)

from config import FALCON_VERSION

# Safety cap on the pagination loop below -- Screener's own result sets
# have never come close to this many pages. Guards against an unexpected
# always-present "Next" link (a site change, a stale selector) turning
# this into an infinite loop instead of a real limit any of Falcon's own
# queries are expected to approach.
MAX_PAGES = 50


def _validate_session(session: SourceSession) -> None:
    if not session.is_authenticated():
        raise SessionExpiredError("Source session is not authenticated.")

    if session.page is None:
        raise SessionExpiredError("No active browser page available.")


def _execute_query(page: Page, query: str) -> None:
    try:
        page.goto(
            SCREENER_QUERY_URL,
            wait_until="domcontentloaded",
            timeout=SCREENER_TIMEOUT,
        )

        page.fill("textarea[name='query']", query)

        page.get_by_role(
            "button",
            name="Run this Query",
        ).click()

        page.wait_for_timeout(3000)

    except Exception as ex:
        raise QueryExecutionError(str(ex)) from ex


def collect_all_pages(page: Page) -> pd.DataFrame:
    """
    Parses the results page currently loaded (assumes _execute_query() has
    already navigated to and submitted the query, landing on page 1), then
    keeps clicking "Next" and re-parsing until Screener stops offering a
    next page (has_next_page() -- see its docstring) or MAX_PAGES is hit.

    Screener's custom-query results paginate at a fixed page size (Falcon
    requests the site's own maximum, 50/page); a query matching more than
    one page's worth silently returned only page 1 before this loop
    existed. wait_for_timeout(3000) after each click matches
    _execute_query()'s own existing wait convention for the initial query
    submission.
    """
    page_frames = []
    pages_fetched = 0

    while True:
        page_frames.append(parse_results(page))
        pages_fetched += 1

        if not has_next_page(page) or pages_fetched >= MAX_PAGES:
            break

        page.locator(".pagination a:has-text('Next')").click()
        page.wait_for_timeout(3000)

    df = pd.concat(page_frames, ignore_index=True) if len(page_frames) > 1 else page_frames[0]

    logger.info("Fetched %d page(s), %d total rows.", pages_fetched, len(df))

    return df


def run_source(
    session: SourceSession,
    strategy: Strategy,
):
    """
    Execute one strategy and return a normalized DataFrame.
    """

    logger.info("Running strategy: %s", strategy.name)

    _validate_session(session)

    page = session.page

    _execute_query(page, strategy.query)

    df = collect_all_pages(page)

    df = normalize_dataframe(
        df,
        strategy=strategy.name,
        source=session.provider,
    )

    logger.info(
        "Completed strategy %s (%d candidates)",
        strategy.name,
        len(df),
    )

    return df
