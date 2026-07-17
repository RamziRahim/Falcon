"""
===============================================================================
Falcon AI Swing Trading Platform
===============================================================================

Module      : indicator_engine.py
Package     : Technical Analysis

Purpose
-------
Orchestrates Falcon's Technical Analysis Engine and outputs execution statistics.
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from common.logger import get_logger
from technical_analysis.indicator_loader import indicator_loader
from technical_analysis.indicator_validator import indicator_validator
from technical_analysis.indicator_calculator import indicator_calculator
from technical_analysis.indicator_exporter import indicator_exporter

logger = get_logger(__name__)


@dataclass(slots=True)
class IndicatorEngineResult:
    processed: int = 0
    exported: int = 0
    failed: int = 0
    skipped: int = 0
    passed_list: list[str] = field(default_factory=list)
    failed_list: list[str] = field(default_factory=list)
    skipped_list: list[str] = field(default_factory=list)


class IndicatorEngine:

    def run(self, symbols: list[str] | None = None) -> IndicatorEngineResult:
        logger.info("Starting Technical Analysis Engine...")
        result = IndicatorEngineResult()

        # Handle loading dataset mappings
        if symbols is None:
            datasets = indicator_loader.load_all()
        else:
            datasets = {}
            for sym in symbols:
                try:
                    datasets[sym] = indicator_loader.load(sym)
                except Exception:
                    # If loading a specific file fails completely, mark as skipped/not found
                    result.skipped += 1
                    result.skipped_list.append(sym)

        # Main processing pipeline loop
        for symbol, dataframe in datasets.items():
            try:
                # 1. Structural Validation Check
                validation = indicator_validator.validate(dataframe)
                if not validation.valid:
                    logger.warning(f"[{symbol}] Skipped: Insufficient data rows (< 200 candles).")
                    result.skipped += 1
                    result.skipped_list.append(symbol)
                    continue

                # 2. Run Indicator Math Pipeline
                enriched = indicator_calculator.calculate(dataframe)

                # 3. Export to Parquet and Excel
                indicator_exporter.save(symbol, enriched)

                # 4. Increment Success Metrics
                result.processed += 1
                result.exported += 1
                result.passed_list.append(symbol)

            except Exception as ex:
                result.failed += 1
                result.failed_list.append(symbol)
                logger.exception(f"Technical analysis failed for {symbol} : {str(ex)}")

        # ------------------------------------------------------------------ #
        # VISUAL CONSOLE METRIC DASHBOARD
        # ------------------------------------------------------------------ #
        print("\n" + "="*60)
        print("          FALCON PHASE 4 DATA PIPELINE METRICS         ")
        print("="*60)
        print(f" SUCCESSFUL (Parquet & Excel Generated) : {result.exported}")
        if result.passed_list:
            print(f"   ↳ Tickers: {', '.join(result.passed_list)}")
            
        print(f" SKIPPED (Not found or too short)       : {result.skipped}")
        if result.skipped_list:
            print(f"   ↳ Tickers: {', '.join(result.skipped_list)}")
            
        print(f" FAILED ERRORS                          : {result.failed}")
        if result.failed_list:
            print(f"   ↳ Tickers: {', '.join(result.failed_list)}")
        print("="*60 + "\n")

        return result


indicator_engine = IndicatorEngine()

# ===============================================================================
# SELF-EXECUTABLE RUNNER BLOCK (For Direct Execution / Quick Production Runs)
# ===============================================================================
if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Safety path patch so it can find 'common' and 'market_data' when run directly
    root_path = Path(__file__).resolve().parent.parent
    if str(root_path) not in sys.path:
        sys.path.insert(0, str(root_path))
        
    try:
        from market_data.cache_manager import cache_manager
        
        # 1. Automatically look inside data/raw to see what stocks you have downloaded
        raw_dir = root_path / "data" / "raw"
        
        if not raw_dir.exists() or not any(raw_dir.glob("*.parquet")):
            print("\n❌ Error: No raw market data found in data/raw/ folder.")
            print("Please run your Phase 3 data collection pipeline first.\n")
            sys.exit(1)
            
        # Extract the symbols from your filenames (e.g., BHEL.NS.parquet -> BHEL.NS)
        downloaded_universe = [f.stem for f in raw_dir.glob("*.parquet")]
        
        # 2. Automatically fire the engine over your existing files!
        indicator_engine.run(symbols=downloaded_universe)
        
    except Exception as e:
        print(f"\n❌ Failed to run indicator engine directly: {str(e)}\n")