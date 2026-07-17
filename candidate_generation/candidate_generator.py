"""
Falcon - Candidate Generation
Module: candidate_generator.py
Version: 1.1.0

Orchestrates candidate generation from all configured strategies.
"""

import pandas as pd

from config import SCREENER_USERNAME, SCREENER_PASSWORD
from common.logger import get_logger

from candidate_generation.auth import login, logout
from candidate_generation.session import create_session
from candidate_generation.strategy_loader import discover_strategies
from candidate_generation.source_runner import run_source
from candidate_generation.consolidator import consolidate
from config import FALCON_VERSION

logger = get_logger("candidate_generator")


from config import MASTER_FILE

def generate_candidates(
    output_file: str = MASTER_FILE
) -> pd.DataFrame:
    """
    Execute all discovered strategies and generate
    the Falcon Master Watchlist.
    """
    logger.info("Starting Candidate Generation")

    playwright, browser, page = login(
        SCREENER_USERNAME,
        SCREENER_PASSWORD,
    )

    session = create_session(
        provider="Screener",
        browser=browser,
        page=page,
        username=SCREENER_USERNAME,
    )
    session.set_authenticated(True)

    try:
        strategies = discover_strategies()

        logger.info("Discovered %d strategies.", len(strategies))

        candidate_frames = []

        for strategy in strategies:

            logger.info("Executing %s", strategy.name)

            try:
                df = run_source(session, strategy)

                if not df.empty:
                    candidate_frames.append(df)

                    logger.info(
                        "%s returned %d candidates.",
                        strategy.name,
                        len(df),
                    )

            except Exception as ex:
                logger.exception(
                    "Strategy '%s' failed: %s",
                    strategy.name,
                    ex,
                )

        master = consolidate(candidate_frames)

        master.to_excel(output_file, index=False)

        logger.info(
            "Master Watchlist exported: %s (%d stocks)",
            output_file,
            len(master),
        )

        return master

    finally:
        logout(playwright, browser)


if __name__ == "__main__":
    generate_candidates()
