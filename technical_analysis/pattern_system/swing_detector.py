"""
===============================================================================
Falcon AI Swing Trading Platform — Fractal Swing Point Detector
===============================================================================
Script      : swing_detector.py
Package     : Technical Analysis / Pattern System
===============================================================================
"""
from __future__ import annotations
import pandas as pd
from technical_analysis.pattern_system.models import SwingPoint

class SwingDetector:
    def __init__(self, window: int = 5):
        """
        Parameters
        ----------
        window : int
            The number of bars to check on both sides (left and right) to confirm a fractal pivot.
        """
        self.window = window

    def detect_swings(self, df: pd.DataFrame) -> list[SwingPoint]:
        """Scans a dataframe chronologically and extracts a list of validated Fractal SwingPoints."""
        swing_points = []
        df_len = len(df)
        df = df.sort_values(by="Date", ascending=True).reset_index(drop=True)

        for i in range(self.window, df_len - self.window):
            current_high = df.loc[i, "High"]
            current_low = df.loc[i, "Low"]
            current_date = str(df.loc[i, "Date"])

            # 1. Fractal High Test (Peak)
            is_high = True
            for r in range(1, self.window + 1):
                if df.loc[i - r, "High"] >= current_high or df.loc[i + r, "High"] > current_high:
                    is_high = False
                    break
            
            if is_high:
                prev_highs = [p for p in swing_points if p.type == "HIGH"]
                is_higher = True if not prev_highs else current_high > prev_highs[-1].price
                
                swing_points.append(SwingPoint(
                    index=i, date=current_date, price=float(current_high), 
                    type="HIGH", is_higher=is_higher
                ))
                continue

            # 2. Fractal Low Test (Trough)
            is_low = True
            for r in range(1, self.window + 1):
                if df.loc[i - r, "Low"] <= current_low or df.loc[i + r, "Low"] < current_low:
                    is_low = False
                    break
            
            if is_low:
                prev_lows = [p for p in swing_points if p.type == "LOW"]
                is_higher = True if not prev_lows else current_low > prev_lows[-1].price
                
                swing_points.append(SwingPoint(
                    index=i, date=current_date, price=float(current_low), 
                    type="LOW", is_higher=is_higher
                ))

        return swing_points
    
swing_detector = SwingDetector()
