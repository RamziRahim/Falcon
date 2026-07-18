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

from candidate_generation.session import SourceSession
from candidate_generation.sources.shareholding_scraper import get_shareholding_trend

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

    def get_shareholding_profile_with_trend(self, ticker: str, session: SourceSession) -> dict:
        """
        Supplements get_shareholding_profile()'s Yahoo-sourced snapshot with
        a Screener.in-scraped QoQ trend for Promoter/FII/DII stake --
        catches a case the static snapshot alone can't: a promoter could
        still hold 60% while visibly reducing it quarter over quarter.

        session must already be authenticated (candidate_generation.auth.login()
        + session.create_session()) -- this reuses that Playwright session
        rather than opening a new one per ticker.
        """
        base = self.get_shareholding_profile(ticker)

        company_slug = ticker.upper().replace(".NS", "")
        trend = get_shareholding_trend(session, company_slug)

        return {**base, **trend}

# Global stateless instance
institutional_engine = InstitutionalEngine()