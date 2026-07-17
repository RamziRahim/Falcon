"""
===============================================================================
Falcon AI Swing Trading Platform — Volume-Filtered Market Structure Engine
===============================================================================
Script      : market_structure.py
Package     : Technical Analysis / Pattern System
===============================================================================
"""
from __future__ import annotations
import pandas as pd
from technical_analysis.pattern_system.models import SwingPoint

class MarketStructureEngine:
    def __init__(self, lookback_window: int = 10, volume_multiplier: float = 1.5):
        self.lookback_window = lookback_window
        self.volume_multiplier = volume_multiplier

    def analyze_structure(self, df: pd.DataFrame, macro_pivots: list[SwingPoint]) -> dict:
        """Evaluates historical rolling windows with strict volume-anomaly validation."""
        df = df.sort_values(by="Date", ascending=True).reset_index(drop=True)
        df_len = len(df)
        
        results = {
            "trend_state": "CHOPPY",
            "is_break_of_structure": False,
            "is_liquidity_sweep": False,
            "sweep_type": None,
            "active_resistance": None,
            "active_support": None
        }

        if not macro_pivots or df_len < self.lookback_window:
            return results

        # Make sure Volume SMA exists from Phase 4 indicator engine
        if "Volume_SMA_20" not in df.columns:
            df["Volume_SMA_20"] = df["Volume"].rolling(window=20).mean()

        recent_highs = [p for p in macro_pivots if p.type == "HIGH"]
        recent_lows = [p for p in macro_pivots if p.type == "LOW"]

        if not recent_highs or not recent_lows:
            return results

        last_macro_high = recent_highs[-1]
        last_macro_low = recent_lows[-1]
        
        results["active_resistance"] = last_macro_high.price
        results["active_support"] = last_macro_low.price

        # 1. Macro Trend Determination
        if last_macro_high.is_higher and last_macro_low.is_higher:
            results["trend_state"] = "UPTREND"
        elif not last_macro_high.is_higher and not last_macro_low.is_higher:
            results["trend_state"] = "DOWNTREND"

        # 2. Break of Structure (BOS)
        if df["Close"].iloc[-1] > last_macro_high.price:
            results["is_break_of_structure"] = True

        # 3. Volume-Filtered Rolling Sweep Scan
        start_idx = max(0, df_len - self.lookback_window)
        
        for idx in range(start_idx, df_len):
            day_low = df.loc[idx, "Low"]
            day_high = df.loc[idx, "High"]
            day_close = df.loc[idx, "Close"]
            day_vol = df.loc[idx, "Volume"]
            vol_sma = df.loc[idx, "Volume_SMA_20"]

            # Avoid division by zero or errors on early data rows
            if pd.isna(vol_sma) or vol_sma == 0:
                continue

            # Check if session has institutional volume expansion
            is_volume_anomaly = day_vol >= (vol_sma * self.volume_multiplier)

            if is_volume_anomaly:
                # Sellside Sweep (Stop Hunt on Longs with heavy volume recovery)
                if day_low < last_macro_low.price and day_close > last_macro_low.price:
                    results["is_liquidity_sweep"] = True
                    results["sweep_type"] = "SELLSIDE"
                    break
                    
                # Buyside Sweep (Stop Hunt on Shorts with heavy volume rejection)
                if day_high > last_macro_high.price and day_close < last_macro_high.price:
                    results["is_liquidity_sweep"] = True
                    results["sweep_type"] = "BUYSIDE"
                    break

        return results

# Global stateless instance with 1.5x Volume Multiplier Requirement
market_structure_engine = MarketStructureEngine(lookback_window=10, volume_multiplier=1.5)