"""
Falcon - Candidate Generation
Module: source_runner.py
Version: 1.1.0

Executes a single strategy against Screener.in and returns a
normalized candidate DataFrame.
"""

from playwright.sync_api import Page

from candidate_generation.session import SourceSession
from candidate_generation.strategy_loader import Strategy
from candidate_generation.exceptions import (
    SessionExpiredError,
    QueryExecutionError,
)
from candidate_generation.sources.screener_adapter import parse_results
from candidate_generation.normalizer import normalize_dataframe
from common.logger import get_logger

logger = get_logger("source_runner")


from config import (
    SCREENER_QUERY_URL,
    SCREENER_TIMEOUT,
)

from config import FALCON_VERSION


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

    df = parse_results(page)

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
