"""
===============================================================================
Falcon AI Swing Trading Platform — Integration Snapshot Exporter
===============================================================================

Script      : integration_snapshot_excel.py
Package     : Tests

Purpose     : Scans all computed data inside data/technical/, extracts the 
              latest indicators row for every ticker, and creates a consolidated
              master spreadsheet dashboard.

Usage       : Run via F5 in VS Code. Outputs to data/excel/Master_Signal_Snapshot.xlsx
===============================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd

from common.logger import get_logger

logger = get_logger(__name__)


def generate_latest_snapshot():
    logger.info("==================================================")
    logger.info("   LAUNCHING LATEST INDICATOR SNAPSHOT ENGINE    ")
    logger.info("==================================================")

    # 1. Establish project directory boundaries safely
    root_path = Path(__file__).resolve().parent.parent
    tech_dir = root_path / "data" / "technical"
    output_dir = root_path / "data" / "excel"
    
    # Ensure our export directory exists cleanly
    output_dir.mkdir(parents=True, exist_ok=True)

    # 2. Check if technical data exists
    if not tech_dir.exists() or not any(tech_dir.glob("*.parquet")):
        logger.error("❌ Integration Error: No technical data found in data/technical/.")
        logger.error("Please execute your indicator engine first to calculate data points.")
        return

    snapshot_records = []
    compiled_count = 0
    failed_count = 0

    # 3. Scan through every computed stock file in the technical folder
    for parquet_file in tech_dir.glob("*.parquet"):
        symbol = parquet_file.stem
        try:
            # Load the complete technical indicator history
            df = pd.read_parquet(parquet_file)
            
            if df.empty:
                logger.warning("[%s] Technical data file is completely empty. Skipping.", symbol)
                continue
                
            # Sort chronological history to ensure the last row is truly the latest market data
            df = df.sort_values(by="Date", ascending=True)
            
            # Extract the very last row (the most recent trading day)
            latest_row = df.iloc[-1].copy()
            
            # Add the stock name directly into the row dictionary for clear tracking
            latest_data = {"Symbol": symbol}
            
            # Map out all indicator columns into our record dictionary safely
            for column in df.columns:
                latest_data[column] = latest_row[column]
                
            snapshot_records.append(latest_data)
            compiled_count += 1
            logger.info("[%s] Successfully extracted latest indicator snapshot row.", symbol)

        except Exception as ex:
            failed_count += 1
            logger.error("[%s] Failed to extract indicator row: %s", symbol, str(ex))

    # 4. Compile everything into a master DataFrame matrix
    if not snapshot_records:
        logger.error("❌ No valid rows could be extracted. Snapshot generation aborted.")
        return

    master_snapshot_df = pd.DataFrame(snapshot_records)

    # Reorder columns to put identity information first
    if "Date" in master_snapshot_df.columns:
        cols = ["Symbol", "Date"] + [col for col in master_snapshot_df.columns if col not in ["Symbol", "Date"]]
        master_snapshot_df = master_snapshot_df[cols]

    # 5. Export out to a beautiful master spreadsheet
    destination_path = output_dir / "Master_Signal_Snapshot.xlsx"
    
    try:
        master_snapshot_df.to_excel(destination_path, index=False, sheet_name="Latest Indicators")
        
        # Output clean pipeline metrics to console
        print("\n" + "="*60)
        print("        INTEGRATION SNAPSHOT GENERATION METRICS        ")
        print("="*60)
        print(f" SUCCESSFUL TICKERS COMPILED : {compiled_count}")
        print(f" FAILED TICKERS              : {failed_count}")
        print(f" OUTPUT PATH                 : {destination_path.name}")
        print("="*60 + "\n")
        
    except Exception as ex:
        logger.error("Failed to write Master Snapshot Excel sheet: %s", str(ex))


if __name__ == "__main__":
    # Ensure paths map correctly if script is run stand-alone
    script_root = Path(__file__).resolve().parent.parent
    if str(script_root) not in sys.path:
        sys.path.insert(0, str(script_root))
        
    generate_latest_snapshot()