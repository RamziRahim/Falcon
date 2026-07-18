"""
===============================================================================
Falcon AI Swing Trading Platform — Robust Corporate Ingestion Layer
===============================================================================
Script      : corporate_engine.py
Package     : Fundamental Analysis
===============================================================================
"""
from __future__ import annotations
import yfinance as yf
import pandas as pd
from datetime import datetime

class CorporateEngine:
    def get_comprehensive_fundamentals(self, ticker: str) -> dict:
        """
        Extracts seasonal quarterly income footprints and computes immediate
        sequential QoQ and structural YoY growth trajectories defensively.
        """
        # Formulate search term cleanly for Indian listings
        formatted_ticker = ticker if ticker.endswith(".NS") else f"{ticker}.NS"
        
        # Absolute Fail-Safe Default Packet Structure
        fallback_packet = {
            "next_earnings_date": "UNKNOWN",
            "days_to_earnings": 999,
            "earnings_risk_flag": "HIGH",
            "latest_quarter_date": "UNKNOWN",
            "revenue_yoy_quarterly_growth": "DATA_GAP",
            "revenue_qoq_growth": "DATA_GAP",
            "net_income_yoy_quarterly_growth": "DATA_GAP",
            "net_income_qoq_growth": "DATA_GAP",
            "net_margin_pct": "DATA_GAP",
            "margin_trend_qoq": "DATA_GAP",
            "margin_trend_yoy": "DATA_GAP"
        }

        try:
            stock = yf.Ticker(formatted_ticker)
            
            # 1. EXTRACT QUARTERLY FINANCIAL MATRIX SAFETY LAYER
            quarterly_financials = stock.quarterly_financials
            
            if quarterly_financials is None or quarterly_financials.empty:
                # Try fallback to stripped token if .NS configuration yielded zero frames
                stock = yf.Ticker(ticker.replace(".NS", ""))
                quarterly_financials = stock.quarterly_financials
                
            if quarterly_financials is None or quarterly_financials.empty:
                return fallback_packet

            # Verify framework sizing profiles
            cols_count = len(quarterly_financials.columns)
            
            # CRITICAL SAFETY GATEWAY: For immediate 2-3 week trade swing velocity,
            # we need at least 2 quarters of history to map sequential trends.
            if cols_count < 2:
                print(f"  [CORPORATE ENGINE INFO] Insufficient historical runway for {ticker}. Slicing bypassed.")
                return fallback_packet

            # Extract calendar dates cleanly
            latest_quarter_date = str(quarterly_financials.columns[0]).split(" ")[0]

            # 2. DEFENSIVE METRIC CALCULATIONS
            # Safely locate row index labels regardless of row ordering changes in API
            financial_index = quarterly_financials.index
            
            # Find row positions dynamically rather than hardcoding numeric row indices
            rev_label = [x for x in financial_index if "Total Revenue" in x or "Revenue" in x]
            net_label = [x for x in financial_index if "Net Income" in x]

            if not rev_label or not net_label:
                return fallback_packet

            # Extract row arrays
            revenue_series = quarterly_financials.loc[rev_label[0]]
            net_income_series = quarterly_financials.loc[net_label[0]]

            # Sequential QoQ Velocity Extraction (Comparing Column 0 to Column 1)
            rev_q0 = revenue_series.iloc[0]
            rev_q1 = revenue_series.iloc[1]
            net_q0 = net_income_series.iloc[0]
            net_q1 = net_income_series.iloc[1]

            rev_qoq = self._calculate_percentage_growth(rev_q0, rev_q1)
            net_qoq = self._calculate_percentage_growth(net_q0, net_q1)

            # Structural YoY Vector Extraction (Requires at least 4 quarters of history, Column 0 to Column 4)
            if cols_count >= 5:
                rev_y4 = revenue_series.iloc[4]
                net_y4 = net_income_series.iloc[4]
                rev_yoy = self._calculate_percentage_growth(rev_q0, rev_y4)
                net_yoy = self._calculate_percentage_growth(net_q0, net_y4)
            else:
                rev_yoy = "DATA_GAP"
                net_yoy = "DATA_GAP"

            # Net Margin Trend (QoQ + YoY) -- revenue growth alone can mask a
            # company growing sales while margins erode (discounting, rising
            # input costs). Reuses revenue_series/net_income_series already
            # extracted above -- no new data fetch.
            margin_q0 = self._safe_margin_pct(net_q0, rev_q0)
            margin_q1 = self._safe_margin_pct(net_q1, rev_q1)

            net_margin_pct = "DATA_GAP"
            margin_trend_qoq = "DATA_GAP"
            margin_trend_yoy = "DATA_GAP"

            if pd.notna(margin_q0) and pd.notna(margin_q1):
                net_margin_pct = f"{margin_q0:.2f}%"
                margin_trend_qoq = self._classify_margin_trend(margin_q0, margin_q1)

            # YoY margin trend is the more reliable comparison for judging
            # genuine expansion/contraction -- QoQ alone can be noisy from
            # pure seasonality, same reasoning already applied to revenue/
            # net-income growth above.
            if cols_count >= 5 and pd.notna(margin_q0):
                margin_y4 = self._safe_margin_pct(net_income_series.iloc[4], revenue_series.iloc[4])
                if pd.notna(margin_y4):
                    margin_trend_yoy = self._classify_margin_trend(margin_q0, margin_y4)

            # 3. EARNINGS RUNWAY RADAR TIMING LAYER
            next_earnings_date = "UNKNOWN"
            days_to_earnings = 999
            earnings_risk_flag = "HIGH"

            try:
                calendar = stock.calendar
                if calendar is not None and "Earnings Date" in calendar:
                    dates_list = calendar["Earnings Date"]
                    if dates_list:
                        target_date = dates_list[0]
                        next_earnings_date = str(target_date).split(" ")[0]
                        
                        # Calculate numerical window distance
                        today = datetime.now().date()
                        delta = (target_date.date() - today).days
                        days_to_earnings = max(0, delta)
                        
                        # Set binary event risk alert thresholds
                        earnings_risk_flag = "CRITICAL" if days_to_earnings <= 7 else "LOW"
            except Exception:
                # Keep defaults if calendar data fields are unpopulated
                pass

            return {
                "next_earnings_date": next_earnings_date,
                "days_to_earnings": days_to_earnings,
                "earnings_risk_flag": earnings_risk_flag,
                "latest_quarter_date": latest_quarter_date,
                "revenue_yoy_quarterly_growth": rev_yoy,
                "revenue_qoq_growth": rev_qoq,
                "net_income_yoy_quarterly_growth": net_yoy,
                "net_income_qoq_growth": net_qoq,
                "net_margin_pct": net_margin_pct,
                "margin_trend_qoq": margin_trend_qoq,
                "margin_trend_yoy": margin_trend_yoy
            }

        except IndexError as ie:
            print(f"  [CORPORATE ENGINE WARNING] Handled thin-data index structure boundary for {ticker}: {ie}")
            return fallback_packet
        except Exception as e:
            print(f"  [CORPORATE ENGINE WARNING] Financial ingestion pipeline bypass for {ticker}: {e}")
            return fallback_packet

    def _calculate_percentage_growth(self, current_val: float, historical_val: float) -> str:
        """Computes growth rates and wraps output into parsed textual structures."""
        try:
            if pd.isna(current_val) or pd.isna(historical_val) or historical_val == 0:
                return "UNKNOWN"

            growth_pct = ((current_val - historical_val) / abs(historical_val)) * 100
            prefix = "+" if growth_pct >= 0 else ""
            return f"{prefix}{growth_pct:.2f}%"
        except Exception:
            return "UNKNOWN"

    def _safe_margin_pct(self, net_income: float, revenue: float) -> float:
        """
        Returns net margin % (net_income / revenue * 100), or NaN if
        revenue is missing/zero/negative -- a zero-revenue quarter (data
        glitch) or negative revenue (nonsensical) can't produce a
        meaningful margin ratio, and must not crash the whole fetch.
        """
        try:
            if pd.isna(net_income) or pd.isna(revenue) or revenue <= 0:
                return float("nan")

            return (net_income / revenue) * 100
        except Exception:
            return float("nan")

    def _classify_margin_trend(self, current: float, prior: float) -> str:
        """Classifies margin direction between two quarters."""
        if current > prior:
            return "EXPANDING"
        if current < prior:
            return "CONTRACTING"
        return "FLAT"

# Global stateless engine singleton instance
corporate_engine = CorporateEngine()

if __name__ == "__main__":
    # Isolated unit test verification path
    test_ticker = "AMAGI.NS"
    print(f"Executing robust parsing validation check for: {test_ticker}...")
    metrics = corporate_engine.get_comprehensive_fundamentals(test_ticker)
    import json
    print(json.dumps(metrics, indent=4))