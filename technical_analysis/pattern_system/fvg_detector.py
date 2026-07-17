"""
===============================================================================
Falcon AI Swing Trading Platform — Fair Value Gap (FVG) Detector
===============================================================================
Script      : fvg_detector.py
Package     : Technical Analysis / Pattern System
===============================================================================
"""
from __future__ import annotations
import pandas as pd

class FVGDetector:
    def detect_fvgs(self, df: pd.DataFrame) -> dict:
        """
        Scans daily price logs to isolate active, unmitigated Bullish FVGs.
        Formula: Candle_1_High < Candle_3_Low
        """
        df = df.sort_values(by="Date", ascending=True).reset_index(drop=True)
        df_len = len(df)
        
        results = {
            "has_active_fvg": False,
            "fvg_top": None,
            "fvg_bottom": None,
            "is_price_in_fvg": False
        }

        if df_len < 3:
            return results

        active_fvgs = []

        # 1. Rolling 3-candle structural scans across history
        for i in range(1, df_len - 1):
            c1_high = df.loc[i - 1, "High"]
            c3_low = df.loc[i + 1, "Low"]

            # Check if an imbalance exists
            if c3_low > c1_high:
                active_fvgs.append({
                    "top": float(c3_low),
                    "bottom": float(c1_high),
                    "index": i
                })

        if not active_fvgs:
            return results

        # 2. Mitigation Filter: Verify if subsequent price action filled the gap
        latest_close = df["Close"].iloc[-1]
        valid_fvg = None

        # Suffix-min of Low, so "did any candle after index j dip to/below X"
        # is an O(1) lookup instead of an O(n) inner scan per FVG.
        suffix_min_low = df["Low"].iloc[::-1].cummin().iloc[::-1]

        # Check from the most recent FVG backward
        for fvg in reversed(active_fvgs):
            fvg_index = fvg["index"]
            scan_start = fvg_index + 2

            mitigated = (
                scan_start < df_len
                and suffix_min_low.iloc[scan_start] <= fvg["bottom"]
            )

            if not mitigated:
                valid_fvg = fvg
                break

        if valid_fvg:
            results["has_active_fvg"] = True
            results["fvg_top"] = valid_fvg["top"]
            results["fvg_bottom"] = valid_fvg["bottom"]
            
            # Check if current closing price is resting safely inside the gap boundary
            if valid_fvg["bottom"] <= latest_close <= valid_fvg["top"]:
                results["is_price_in_fvg"] = True

        return results

# Global stateless instance
fvg_detector = FVGDetector()