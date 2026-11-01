"""
===============================================================================
Falcon AI Swing Trading Platform — Fair Value Gap (FVG) Detector
===============================================================================
Script      : fvg_detector.py
Package     : Technical Analysis / Pattern System
===============================================================================
"""
from __future__ import annotations
import numpy as np
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

        # 1. Rolling 3-candle structural scans across history. Vectorised
        # 2026-11-01 (was a per-bar loop of scalar df.loc reads); same
        # comparison on the same values, so the same gaps in the same order
        # -- see tests/technical_analysis/test_fvg_detector_equivalence.py.
        highs = df["High"].to_numpy()
        lows = df["Low"].to_numpy()
        c1_highs = highs[:-2]                  # candle i-1 for i = 1..n-2
        c3_lows = lows[2:]                     # candle i+1
        gap_positions = np.flatnonzero(c3_lows > c1_highs)
        active_fvgs = [
            {"top": float(c3_lows[k]), "bottom": float(c1_highs[k]), "index": int(k) + 1}
            for k in gap_positions
        ]

        if not active_fvgs:
            return results

        # 2. Mitigation Filter: Verify if subsequent price action filled the gap
        latest_close = df["Close"].iloc[-1]
        valid_fvg = None

        # Suffix-min of Low, so "did any candle after index j dip to/below X"
        # is an O(1) lookup instead of an O(n) inner scan per FVG.
        suffix_min_low = df["Low"].iloc[::-1].cummin().iloc[::-1].to_numpy()

        # Check from the most recent FVG backward
        for fvg in reversed(active_fvgs):
            fvg_index = fvg["index"]
            scan_start = fvg_index + 2

            mitigated = (
                scan_start < df_len
                and suffix_min_low[scan_start] <= fvg["bottom"]
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