"""
===============================================================================
Falcon AI Swing Trading Platform — Corporate Risk & Health Metrics
===============================================================================
Script      : metrics_engine.py
Package     : Fundamental Analysis
===============================================================================
"""
from __future__ import annotations
from typing import Optional
import yfinance as yf
import pandas as pd

from common.logger import get_logger

logger = get_logger(__name__)


class MetricsEngine:
    def get_risk_vitals(self, ticker: str) -> dict:
        """
        Extracts structural balance sheet health and key float vitals.
        """
        results = {
            "debt_to_equity": "UNKNOWN",
            "float_shares": "UNKNOWN",
            "insider_percent": "UNKNOWN"
        }

        formatted_ticker = ticker if ticker.endswith(".NS") else f"{ticker}.NS"

        try:
            stock = yf.Ticker(formatted_ticker)
            info = stock.info

            if info:
                # 1. Debt Health Balance Check
                debt_eq = info.get("debtToEquity")
                if debt_eq is not None:
                    results["debt_to_equity"] = f"{debt_eq:.2f}%" if debt_eq > 0 else "DEBT_FREE"

                # 2. Float Size (Supply Dynamics)
                float_s = info.get("floatShares")
                if float_s is not None:
                    results["float_shares"] = f"{float_s / 1_000_000:.2f}M"

                # 3. Promoter / Insider Skin in the Game
                insider_p = info.get("heldPercentInsiders")
                if insider_p is not None:
                    results["insider_percent"] = f"{insider_p * 100:.2f}%"

        except Exception as e:
            logger.warning("Failed to parse info blocks for %s: %s", ticker, e)

        return results

    def get_roce(self, ticker: str) -> str:
        """
        Computes Return on Capital Employed: EBIT / (Total Assets - Current
        Liabilities). Prefers annual figures (less noisy than a single
        quarter) and falls back to quarterly statements when annual rows
        are incomplete.

        Balance sheet coverage for Indian small-caps via yfinance is patchy
        (the same data-quality gap already found with sector classification)
        — returns "N/A" rather than a fabricated number when the required
        rows can't be located.
        """
        formatted_ticker = ticker if ticker.endswith(".NS") else f"{ticker}.NS"

        try:
            stock = yf.Ticker(formatted_ticker)

            roce = self._compute_roce(stock.financials, stock.balance_sheet)

            if roce is None:
                roce = self._compute_roce(stock.quarterly_financials, stock.quarterly_balance_sheet)

            if roce is None:
                return "N/A"

            return f"{roce * 100:.2f}%"

        except Exception as e:
            logger.warning("ROCE computation failed for %s: %s", ticker, e)
            return "N/A"

    def _compute_roce(self, financials, balance_sheet) -> Optional[float]:
        """
        Extracts EBIT and capital employed from a single pair of statements
        (both annual or both quarterly), matching row labels dynamically
        rather than by position since yfinance's exact label text varies.
        """
        if financials is None or financials.empty or balance_sheet is None or balance_sheet.empty:
            return None

        ebit_label = [x for x in financials.index if "Operating Income" in x]
        assets_label = [x for x in balance_sheet.index if "Total Assets" in x]

        # Excludes "Total Non Current Liabilities ..." rows, which also
        # contain the substring "Current Liabilities".
        liabilities_label = [
            x for x in balance_sheet.index
            if "Current Liabilities" in x and "Non Current Liabilities" not in x
        ]

        if not ebit_label or not assets_label or not liabilities_label:
            return None

        try:
            ebit = financials.loc[ebit_label[0]].iloc[0]
            total_assets = balance_sheet.loc[assets_label[0]].iloc[0]
            current_liabilities = balance_sheet.loc[liabilities_label[0]].iloc[0]
        except IndexError:
            return None

        if pd.isna(ebit) or pd.isna(total_assets) or pd.isna(current_liabilities):
            return None

        capital_employed = total_assets - current_liabilities

        if capital_employed == 0:
            return None

        return ebit / capital_employed


# Global stateless instance
metrics_engine = MetricsEngine()