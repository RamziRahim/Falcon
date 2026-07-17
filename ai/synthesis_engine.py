"""
===============================================================================
Falcon AI Swing Trading Platform — Production AI Decision Support Engine
===============================================================================
Script      : synthesis_engine.py
Package     : AI Layer
===============================================================================
"""
from __future__ import annotations
import os
import glob
import time
import pandas as pd
from ai.prompt_templates import STRATEGIC_SYNTHESIS_PROMPT
from ai.providers import get_ai_provider
from fundamental_analysis import fundamental_engine

class AISynthesisEngine:
    def __init__(self, provider_type: str = "gemini"):
        # The engine stays structurally decoupled from underlying API models
        self.ai_client = get_ai_provider(provider_type)

    def compile_snapshot(self, ticker: str, technical_df: pd.DataFrame) -> str:
        """Fuses quantitative technical metrics with the master fundamental data packet."""
        latest = technical_df.iloc[-1]
        fa = fundamental_engine.get_complete_data_packet(ticker)
        
        snapshot = f"""
=== TECHNICAL & PATTERN SNAPSHOT ({ticker}) ===
Trend State         : {latest.get('Trend_State', 'UNKNOWN')}
VCP Breakout Status : {latest.get('Is_VCP_Breakout', False)}
VCP Structural Score: {latest.get('VCP_Score', 0.0)}%
Is Liquidity Sweep  : {latest.get('Is_Liquidity_Sweep', False)}

=== SEASONALLY-ADJUSTED FINANCIALS (VECTOR B.1) ===
Revenue YoY Growth           : {fa['quarterly_financials'].get('revenue_yoy_quarterly_growth', '0%')}
Revenue QoQ Growth           : {fa['quarterly_financials'].get('revenue_qoq_growth', '0%')}
Net Income QoQ Growth        : {fa['quarterly_financials'].get('net_income_qoq_growth', '0%')}
Days Remaining to Earnings  : {fa['quarterly_financials'].get('days_to_earnings', 999)}

=== BALANCE SHEET & RISK VITALS (VECTOR B.2) ===
Debt-to-Equity Ratio         : {fa['balance_sheet_vitals'].get('debt_to_equity', '0%')}
Free Float Share Count       : {fa['balance_sheet_vitals'].get('float_shares', 0)}

=== SHAREHOLDING DISTRIBUTION VECTORS (VECTOR B.3) ===
Public Retail Float %        : {fa['shareholding_distribution'].get('public_retail_float', '100%')}

=== RECENT CORPORATE NEWS & CATALYSTS (VECTOR C) ===
{fa['recent_catalysts']}
"""
        return snapshot

    def synthesize_trade_setup(self, ticker: str, technical_df: pd.DataFrame) -> dict:
        """Passes structured textual snapshots out to the decoupled provider gateway."""
        data_snapshot = self.compile_snapshot(ticker, technical_df)
        full_prompt = STRATEGIC_SYNTHESIS_PROMPT.format(data_snapshot=data_snapshot)
        return self.ai_client.generate_structured_synthesis(full_prompt)

    def run_single_stock_screening(self, ticker: str, data_directory: str = "data/patterns"):
        """Runs the entire multi-vector analysis for a single user-specified stock defensively."""
        clean_input = ticker.upper().strip()
        
        # Build array matrix of look-up paths to eliminate suffix/case anomalies
        possible_names = [
            clean_input,
            clean_input.replace(".NS", ""),
            f"{clean_input}.NS"
        ]
        
        file_path = None
        matched_ticker = None
        
        for name in possible_names:
            check_path = os.path.join(data_directory, f"{name}.parquet")
            if os.path.exists(check_path):
                file_path = check_path
                # Keep qualified NSE tracking notation for fundamental streams
                matched_ticker = name if name.endswith(".NS") else f"{name}.NS"
                break

        print("\n" + "="*80)
        print(f" 🎯 FALCON RISK RADAR TARGET ACQUISITION: {clean_input}")
        print("="*80)

        if not file_path:
            print(f"❌ [FILE NOT FOUND] Looked for file iterations: {', '.join([n + '.parquet' for n in possible_names])}")
            print(f"Verify files inside folder directory layout path: '{data_directory}/'")
            return

        try:
            # Format clean logging path display independent of Windows backslash quirks
            display_path = file_path.replace("\\", "/")
            print(f"✅ Target chart located at: {display_path}")
            print(f"» Extracting structural intelligence channels for {matched_ticker}...")
            
            technical_df = pd.read_parquet(file_path)
            analysis = self.synthesize_trade_setup(matched_ticker, technical_df)
            
            print("\n" + "="*80)
            print(f" 🔥 FALCON EXECUTIVE BREAKOUT BRIEFING: {matched_ticker}")
            print("="*80)
            print(f" STATUS ACTION    : {analysis.get('executive_action', 'UNKNOWN')}")
            print(f" VELOCITY SCORE   : {analysis.get('velocity_score', 0)}/100")
            print(f" GROWTH SUMMARY   : {analysis.get('fundamental_growth_synthesis', '')}")
            print(f" SUPPLY VERDICT   : {analysis.get('supply_and_float_verdict', '')}")
            print(f" DIVERGENCE FLAG  : {analysis.get('growth_divergence_flag', False)}")
            print("="*80 + "\n")

        except Exception as e:
            print(f"❌ [PIPELINE FAULT] Failed to screen single target {clean_input}: {e}")

    def run_batch_watchlist_screening(self, data_directory: str = "data/patterns"):
        """Dynamically loops through all available technical files in batch background mode."""
        search_path = os.path.join(data_directory, "*.parquet")
        target_files = glob.glob(search_path)
        
        if not target_files:
            print(f"\n[SYSTEM HALT] Zero technical pattern matrices found inside: '{data_directory}'")
            return

        print("\n" + "="*80)
        print(f" 🚀 FALCON WATCHLIST RADAR SCAN | PROCESSING {len(target_files)} COUNTERS")
        print("="*80)
        
        leaderboard = []

        for idx, file_path in enumerate(target_files, start=1):
            ticker = os.path.basename(file_path).replace(".parquet", "")
            print(f"[{idx}/{len(target_files)}] Processing screening matrix channels for: {ticker}...")
            
            try:
                technical_df = pd.read_parquet(file_path)
                if technical_df.empty:
                    continue
                
                analysis = self.synthesize_trade_setup(ticker, technical_df)
                analysis["ticker"] = ticker
                leaderboard.append(analysis)
                
                # Baseline padding rest period to protect free API limits
                time.sleep(3.5)
                
            except Exception as e:
                print(f"  ❌ [PIPELINE FAULT] Failed processing loops for {ticker}: {e}")

        # Segregate and print structured results boards
        executes = [r for r in leaderboard if r.get('executive_action') == 'EXECUTE']
        watchlists = [r for r in leaderboard if r.get('executive_action') == 'ALERT_WATCHLIST']
        avoids = [r for r in leaderboard if r.get('executive_action') == 'AVOID']

        executes.sort(key=lambda x: x.get('velocity_score', 0), reverse=True)

        print("\n" + "="*80)
        print(" 🔥 THE FALCON HIGH-VELOCITY REASONING EXECUTIVE BREAKOUT LEADERBOARD")
        print("="*80)

        print(f"\n⚡ [ACTIONABLE ALPHA TARGETS] — {len(executes)} SETUPS READY TO TRADE NOW")
        print("═"*80)
        for rank, item in enumerate(executes, start=1):
            print(f"#{rank} | {item['ticker'].upper():<12} | SCORE: {item['velocity_score']}/100 | ACTION: {item['executive_action']}")
            print(f"   Growth Metrics : {item['fundamental_growth_synthesis']}")
            print(f"   Supply Verdict : {item['supply_and_float_verdict']}")
            print("-" * 80)

        if watchlists:
            print(f"\n⏳ [MONITOR & WATCHLIST] — {len(watchlists)} SETUPS ENCOUNTERING MOVEMENT FRICTION")
            print("═"*80)
            for item in watchlists:
                print(f"• {item['ticker'].upper():<12} | SCORE: {item['velocity_score']}/100 | REASON: {item['fundamental_growth_synthesis'][:85]}...")

if __name__ == "__main__":
    engine = AISynthesisEngine(provider_type="gemini")
    
    print("====================================================")
    print("       FALCON AI SWING TRADING SYSTEM INITIALIZED     ")
    print("====================================================")
    print("1. Screen a Single Specific Stock Ticker (User Input)")
    print("2. Scan Entire Data Folder Watchlist (Batch Mode)")
    print("====================================================")
    
    choice = input("Select operational mode (1 or 2): ").strip()
    
    if choice == "1":
        user_ticker = input("Enter stock ticker symbol (e.g. CGPOWER or AMAGI): ").strip()
        if user_ticker:
            engine.run_single_stock_screening(user_ticker)
        else:
            print("Invalid input. Terminating execution pipeline.")
    elif choice == "2":
        engine.run_batch_watchlist_screening()
    else:
        print("Invalid selection. Defaulting to Single Stock Target Engine mode.")
        user_ticker = input("Enter stock ticker symbol: ").strip()
        if user_ticker:
            engine.run_single_stock_screening(user_ticker)