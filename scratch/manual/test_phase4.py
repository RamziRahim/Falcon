"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Script      : test_phase4.py
Package     : Tests

Purpose
-------
Test runner to verify the execution of Phase 4 (Technical Analysis Engine).
Loads raw data, calculates indicators, validates output, and saves technical files
to both Parquet and Excel format.

Usage
-----
Open this file in VS Code and press F5 to execute.
===============================================================================
"""

from __future__ import annotations

from common.logger import get_logger
from technical_analysis.indicator_engine import indicator_engine
from technical_analysis.indicator_exporter import indicator_exporter

# Setup logging to see detailed step-by-step terminal outputs
logger = get_logger(__name__)


def run_phase4_test():
    logger.info("==================================================")
    logger.info("Initializing Phase 4 Technical Analysis Engine Test")
    logger.info("==================================================")

    # 1. Define a few test symbols that have clean raw data downloaded in Phase 3
    # Update these strings if you are tracking different tickers in your data/raw/ folder
    test_universe = ["BHEL.NS", "MMTC.NS"]

    logger.info("Target Test Universe: %s", test_universe)

    # 2. Run the technical engine pipeline
    # This automatically calls Loader -> Calculator -> Validator -> Exporter
    run_metrics = indicator_engine.run(symbols=test_universe)

    # 3. Print out a friendly summary using the exact properties of IndicatorEngineResult
    logger.info("==================================================")
    logger.info("                EXECUTION SUMMARY                 ")
    logger.info("==================================================")
    logger.info(f"Total Processed Successfully : {run_metrics.processed}")
    logger.info(f"Total Exported (Excel/Pqt)   : {run_metrics.exported}")
    logger.info(f"Total Failed Tickers         : {run_metrics.failed}")
    logger.info("==================================================")

    # 4. Verify that the files arrived safely on your hard drive
    for symbol in test_universe:
        if indicator_exporter.exists(symbol):
            logger.info(f"🎉 Success! Enriched technical data saved for {symbol}")
            
            # Let's inspect a quick sample view of the calculated data sheet
            sample_df = indicator_exporter.load(symbol)
            logger.info(f"[{symbol}] Total data rows calculated: {len(sample_df)}")
            logger.info(f"[{symbol}] Columns generated: {list(sample_df.columns)[:10]}... and more.")
        else:
            logger.error(f"❌ Verification failed: No technical file found for {symbol}")


if __name__ == "__main__":
    run_phase4_test()