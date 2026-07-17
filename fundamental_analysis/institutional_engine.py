"""
===============================================================================
Falcon AI Swing Trading Platform — FII / DII & Shareholding Tracking Engine
===============================================================================
Script      : institutional_engine.py
Package     : Fundamental Analysis
===============================================================================
"""
from __future__ import annotations
import yfinance as yf

class InstitutionalEngine:
    def get_shareholding_profile(self, ticker: str) -> dict:
        """
        Extracts institutional presence, public distribution, 
        and institutional stability flags.
        """
        results = {
            "promoter_holding": "UNKNOWN",
            "institutional_sponsorship": "UNKNOWN",
            "public_retail_float": "UNKNOWN"
        }
        
        formatted_ticker = ticker if ticker.endswith(".NS") else f"{ticker}.NS"

        try:
            stock = yf.Ticker(formatted_ticker)
            info = stock.info
            
            if info:
                # 1. Promoter Stake (Insider Ownership)
                promoter = info.get("heldPercentInsiders")
                
                # 2. Institutional Presence (Proxy tracking via Mutual Funds + Institutions)
                inst_mfs = info.get("heldPercentInstitutions")
                
                if promoter is not None:
                    results["promoter_holding"] = f"{promoter * 100:.2f}%"
                    
                if inst_mfs is not None:
                    results["institutional_sponsorship"] = f"{inst_mfs * 100:.2f}%"
                    
                # 3. Calculate Retail / Public Float Residual Math
                if promoter is not None and inst_mfs is not None:
                    retail = 1.0 - (promoter + inst_mfs)
                    results["public_retail_float"] = f"{max(0.0, retail) * 100:.2f}%"

        except Exception as e:
            print(f"[INSTITUTIONAL ENGINE WARNING] Could not resolve shareholding data arrays for {ticker}: {e}")
            
        return results

# Global stateless instance
institutional_engine = InstitutionalEngine()