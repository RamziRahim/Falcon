"""
Falcon -- price-cache integrity scan / repair.

Run from the project root, inside the Falcon venv (Python 3.12):

    python repair_price_cache.py            # SCAN ONLY: writes nothing except the report CSV
    python repair_price_cache.py --apply    # repair what can be repaired (backs up first)

What it fixes (see market_data/price_integrity.py for the full story):
  * SERIES_FLIP     -> re-downloaded from NSE (equity series only), split-adjusted
  * UNADJUSTED_STEP -> split/bonus adjusted from the cached file itself, only where
                       NSE's corporate-action records confirm the jump
Everything else is left alone and listed as UNRESOLVED for a human to look at.

Originals are copied to data/technical_backup_pre_integrity_repair/ before any
file is overwritten. Indicators are recomputed from the corrected prices.
"""
import sys
sys.path.insert(0, ".")

import argparse
import datetime as dt
import time

import pandas as pd

from config import DATA_FOLDER
from market_data.corporate_actions import load_corporate_actions
from market_data.price_integrity import CLEAN, process_directory

TECHNICAL_DIR = DATA_FOLDER / "technical"
BACKUP_DIR = DATA_FOLDER / "technical_backup_pre_integrity_repair"
REPORT_PATH = DATA_FOLDER / "price_integrity_report.csv"
BASE_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume", "Deliverable_Qty", "Delivery_Pct"]
HISTORY_YEARS = 10


def _fetch_full_history(symbol: str) -> pd.DataFrame:
    from market_data.providers.nse_provider import NSEProvider

    today = dt.date.today()
    return NSEProvider().get_history(symbol, today - dt.timedelta(days=365 * HISTORY_YEARS), today)


def _save(symbol: str, repaired: pd.DataFrame) -> None:
    from technical_analysis.indicator_calculator import indicator_calculator
    from technical_analysis.indicator_exporter import indicator_exporter
    from market_data.cache_manager import cache_manager

    base = repaired[[c for c in BASE_COLUMNS if c in repaired.columns]].copy()
    indicator_exporter.save(symbol, indicator_calculator.calculate(base))
    if cache_manager.exists(symbol):          # keep the live raw cache consistent too
        cache_manager.save(symbol, base)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="repair (default is scan-only)")
    args = parser.parse_args()

    actions = load_corporate_actions() if args.apply else None
    if args.apply and actions is None:
        sys.exit("Corporate-action records unavailable; refusing to repair without them.")

    outcomes = process_directory(
        TECHNICAL_DIR, actions, _fetch_full_history, _save,
        apply=args.apply, backup_dir=BACKUP_DIR, pause=lambda: time.sleep(1.0),
    )

    report = pd.DataFrame([{
        "symbol": o.symbol, "before": o.before.status, "action": o.action,
        "after": o.after.status if o.after else "", "jumps": o.before.jumps,
        "flips": o.before.flips, "detail": o.detail,
    } for o in outcomes])
    report.to_csv(REPORT_PATH, index=False)

    print(f"\n{'APPLIED' if args.apply else 'SCAN ONLY'} -- {len(outcomes)} tickers")
    print(report["action" if args.apply else "before"].value_counts().to_string())
    problems = report[(report["before"] != CLEAN)]
    if not problems.empty:
        print("\nNeeds attention:")
        print(problems.to_string(index=False))
    print(f"\nReport: {REPORT_PATH}")


if __name__ == "__main__":
    main()
