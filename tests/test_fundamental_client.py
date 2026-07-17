# fundamental_analysis/test_client.py
from __future__ import annotations
import json
from fundamental_analysis.corporate_engine import corporate_engine
from fundamental_analysis.metrics_engine import metrics_engine
from fundamental_analysis.institutional_engine import institutional_engine

def run_comprehensive_fundamental_check(ticker: str):
    print("=" * 70)
    print(f"   FALCON CORE FUNDAMENTAL ANALYSIS DATA STREAM: {ticker}   ")
    print("=" * 70)
    
    # Ingest from all 3 sub-engines
    time_series = corporate_engine.get_comprehensive_fundamentals(ticker)
    vitals = metrics_engine.get_risk_vitals(ticker)
    shareholding = institutional_engine.get_shareholding_profile(ticker)
    
    master_fundamental_packet = {
        "ticker_identity": ticker,
        "quarterly_financials": time_series,
        "balance_sheet_vitals": vitals,
        "shareholding_distribution": shareholding
    }
    
    print(json.dumps(master_fundamental_packet, indent=4))
    print("=" * 70)

if __name__ == "__main__":
    run_comprehensive_fundamental_check("CGPOWER")