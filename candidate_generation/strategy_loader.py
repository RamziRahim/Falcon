"""
===============================================================================
Falcon - Candidate Generation
Module  : strategy_loader.py
Version : 1.1.0

Discovers strategy folders and loads query definitions exactly as mapped.
===============================================================================
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List

from common.logger import get_logger
from config import FALCON_VERSION

logger = get_logger("query_loader")


@dataclass
class Strategy:
    name: str
    query_path: Path
    query: str


def discover_strategies(strategy_root: str = "strategies") -> List[Strategy]:
    """
    Auto-discover strategy folders containing screen.query.

    Returns
    -------
    List[Strategy]
    """
    # Anchor the lookup to the candidate_generation package folder where it lives
    package_dir = Path(__file__).resolve().parent
    root = package_dir / strategy_root

    if not root.exists():
        raise FileNotFoundError(f"Strategy folder not found: {root}")

    strategies: List[Strategy] = []

    for folder in sorted(root.iterdir()):
        if not folder.is_dir():
            continue

        # Aligned to match your exact file name schema: screen.query
        query_file = folder / "screen.query"

        if not query_file.exists():
            logger.warning("Skipping %s (missing screen.query)", folder.name)
            continue

        query = query_file.read_text(encoding="utf-8").strip()

        if not query:
            logger.warning("Skipping %s (empty query)", folder.name)
            continue

        strategies.append(
            Strategy(
                name=folder.name,
                query_path=query_file,
                query=query,
            )
        )

    logger.info("Discovered %d strategies", len(strategies))
    return strategies


def load_strategy(name: str, strategy_root: str = "strategies") -> Strategy:
    """
    Load a single strategy by name.
    """
    package_dir = Path(__file__).resolve().parent
    folder = package_dir / strategy_root / name

    if not folder.exists():
        raise FileNotFoundError(f"Strategy path breakdown target missing: {name}")

    # Synchronized file name lookup logic
    query_file = folder / "screen.query"

    if not query_file.exists():
        raise FileNotFoundError(query_file)

    return Strategy(
        name=name,
        query_path=query_file,
        query=query_file.read_text(encoding="utf-8").strip(),
    )


if __name__ == "__main__":
    strategies = discover_strategies()

    for strategy in strategies:
        print(f"{strategy.name} -> {strategy.query_path}")