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
from fundamental_analysis.screener_fundamentals_store import (
    get_promoter_holding_display,
    get_promoter_trend,
    get_fii_trend,
    get_dii_trend,
)

class InstitutionalEngine:
    def get_shareholding_profile(self, ticker: str) -> dict:
        """
        Extracts institutional presence, public distribution,
        and institutional stability flags.

        promoter_holding is sourced from the Screener fundamentals store
        as of docs/known_data_issues.md item #4 -- a company's disclosed
        promoter shareholding is a single unambiguous regulatory figure,
        not something that varies by data provider, so there's no
        definitional-gap risk here (unlike institutional_sponsorship
        below). institutional_sponsorship stays on Yahoo's
        heldPercentInstitutions deliberately, unchanged: Screener's own
        FII%+DII% is a narrower, different measurement (no mutual-fund/
        other-institutional holding), a real definitional gap, not a
        formatting difference -- see docs/known_data_issues.md item #4
        for the full reasoning. public_retail_float (unused anywhere
        outside this file's own tests and the disabled AI panel --
        confirmed via a full-codebase audit) still computes internally
        off Yahoo's own promoter/institutional figures, unchanged --
        not worth reconciling against a field nothing reads.
        """
        results = {
            "promoter_holding": get_promoter_holding_display(ticker),
            "institutional_sponsorship": "UNKNOWN",
            "public_retail_float": "UNKNOWN"
        }

        formatted_ticker = ticker if ticker.endswith(".NS") else f"{ticker}.NS"

        try:
            stock = yf.Ticker(formatted_ticker)
            info = stock.info

            if info:
                # Promoter Stake (Insider Ownership) -- kept for
                # public_retail_float's own internal math below only;
                # results["promoter_holding"] above already comes from
                # the Screener store, not this value.
                promoter = info.get("heldPercentInsiders")

                # Institutional Presence (Proxy tracking via Mutual Funds + Institutions)
                inst_mfs = info.get("heldPercentInstitutions")

                if inst_mfs is not None:
                    results["institutional_sponsorship"] = f"{inst_mfs * 100:.2f}%"

                # Calculate Retail / Public Float Residual Math
                if promoter is not None and inst_mfs is not None:
                    retail = 1.0 - (promoter + inst_mfs)
                    results["public_retail_float"] = f"{max(0.0, retail) * 100:.2f}%"

        except Exception as e:
            print(f"[INSTITUTIONAL ENGINE WARNING] Could not resolve shareholding data arrays for {ticker}: {e}")

        return results

    def get_shareholding_profile_with_trend(self, ticker: str, session: SourceSession) -> dict:
        """
        Supplements get_shareholding_profile()'s snapshot with
        Promoter/FII/DII QoQ trend -- catches a case the static snapshot
        alone can't: a promoter could still hold 60% while visibly
        reducing it quarter over quarter.

        As of docs/known_data_issues.md item #4, the trend itself is
        sourced from the Screener fundamentals store (the same
        candidate-generation scrape, already captured) instead of a
        separate per-ticker Screener.in company-page visit
        (candidate_generation/sources/shareholding_scraper.py) -- that
        scraper module still exists (unused by this call site now) in
        case anything else ever needs it.

        session is kept as a parameter purely for call-site compatibility
        with decision_engine/live_scorer.py -- unused now that the trend
        no longer needs its own authenticated page visit.
        """
        base = self.get_shareholding_profile(ticker)

        trend = {
            "promoter_trend": get_promoter_trend(ticker),
            "fii_trend": get_fii_trend(ticker),
            "dii_trend": get_dii_trend(ticker),
        }

        return {**base, **trend}

# Global stateless instance
institutional_engine = InstitutionalEngine()