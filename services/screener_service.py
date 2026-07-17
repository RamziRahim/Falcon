import os
import sys
import glob
import pandas as pd
from typing import List

# Structural path injection to maintain module integrity
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

# Direct imports of your true architectural singletons
from market_data.data_collection_engine import market_data_engine
from technical_analysis.indicator_engine import indicator_engine
from technical_analysis.pattern_engine import PatternEngine

def run_falcon_production_screener(ticker_universe: List[str]) -> pd.DataFrame:
    """
    Executes the entire Falcon deterministic data lifecycle sequentially.
    """
    
    # ─── PHASE 3: RAW MARKET INGESTION LAYER ──────────────────────────────────
    # Synchronizes cache, runs data_validator, outputs to data/raw/
    market_data_engine.run(symbols=ticker_universe)
    
    # ─── PHASE 4: TECHNICAL ANALYSIS ENRICHMENT LAYER ──────────────────────────
    # Runs indicator_calculator, maps MA ribbons, outputs to data/technical/
    indicator_engine.run(symbols=ticker_universe)
    
    # ─── PHASE 5: INSTITUTIONAL PATTERN DETECTION LAYER ────────────────────────
    # Extracts multi-scale fractals, VCP coiling configurations, and FVGs
    pattern_orchestrator = PatternEngine(src_dir="data/technical", dest_dir="data/patterns")
    pattern_orchestrator.execute_pipeline()
    
    # ─── PHASE 6: CONSOLIDATE & EXTRACT DRIVING SETUPS ────────────────────────
    leaderboard_records = []
    pattern_files = glob.glob(os.path.join("data/patterns", "*.parquet"))
    
    for file_path in pattern_files:
        ticker = os.path.basename(file_path).replace(".parquet", "")
        df = pd.read_parquet(file_path)
        
        if df.empty:
            continue
            
        latest_candle = df.iloc[-1]
        
        # Pulling your real Phase 4 & Phase 5 engineering outputs directly from columns!
        trend_state = latest_candle.get("Trend_State", "UNKNOWN")
        vcp_score = latest_candle.get("VCP_Score", 0.0)
        is_vcp_breakout = latest_candle.get("Is_VCP_Breakout", False)
        is_liquidity_sweep = latest_candle.get("Is_Liquidity_Sweep", False)
        
        # MOCK FUNDAMENTALS INTEGRATION (Replace with your actual fundamentals lookup logic)
        mock_fundamentals = {
            "HAL": {"ROCE": "28.6%", "YoY_Revenue": "+18.4%", "Debt_Equity": "0.09"},
            "ABBOTINDIA": {"ROCE": "39.2%", "YoY_Revenue": "+12.1%", "Debt_Equity": "0.02"},
        }.get(ticker.split(".")[0], {"ROCE": "N/A", "YoY_Revenue": "N/A", "Debt_Equity": "N/A"})
        
        # We only bubble up tickers that meet your strict trend or structural criteria
        if trend_state == "UPTREND" or vcp_score > 0:
            status_tag = "Breakout" if is_vcp_breakout else ("Pullback" if is_liquidity_sweep else "Strong Trend")
            
            leaderboard_records.append({
                "Symbol": ticker,
                "Price": round(latest_candle["Close"], 2),
                "Trend_State": trend_state,
                "VCP_Score": round(vcp_score, 1),
                "Status": status_tag,
                "ROCE": mock_fundamentals["ROCE"],
                "YoY_Rev": mock_fundamentals["YoY_Revenue"],
                "D_E": mock_fundamentals["Debt_Equity"]
            })
            
    return pd.DataFrame(leaderboard_records)