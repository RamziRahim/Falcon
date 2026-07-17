"""
===============================================================================
Falcon AI Swing Trading Platform — Master Fundamental & Catalyst Coordinator
===============================================================================
Script      : fundamental_analysis.py
Package     : Fundamental Analysis
===============================================================================
"""
from __future__ import annotations
from fundamental_analysis.corporate_engine import corporate_engine
from fundamental_analysis.metrics_engine import metrics_engine
from fundamental_analysis.institutional_engine import institutional_engine
from fundamental_analysis.news_engine import news_engine

class FundamentalEngine:
    def get_complete_data_packet(self, ticker: str) -> dict:
        """
        Executes all 4 underlying sub-engines and synthesizes them into
        a single modular data packet.
        """
        # Execute sub-engines cleanly
        time_series = corporate_engine.get_comprehensive_fundamentals(ticker)
        vitals = metrics_engine.get_risk_vitals(ticker)
        shareholding = institutional_engine.get_shareholding_profile(ticker)
        news_data = news_engine.get_ticker_catalysts(ticker, max_headlines=5)
        
        # Unified Master Data Packet Structure
        return {
            "ticker_identity": ticker,
            "quarterly_financials": time_series,
            "balance_sheet_vitals": vitals,
            "shareholding_distribution": shareholding,
            "recent_catalysts": news_data
        }

# Global stateless orchestrator instance
fundamental_engine = FundamentalEngine()