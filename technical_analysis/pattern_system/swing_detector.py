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

        last_high_price = None
        last_low_price = None

        for i in range(self.window, df_len - self.window):
            current_high = df.loc[i, "High"]
            current_low = df.loc[i, "Low"]
            current_date = str(df.loc[i, "Date"])

            # 1. Fractal High Test (Peak) -- strict '>' on both sides, so an
            # exact tie doesn't invalidate a pivot (previously the left side
            # used '>=', rejecting a tie there while the right side's '>'
            # tolerated the identical tie -- asymmetric with no rationale).
            is_high = True
            for r in range(1, self.window + 1):
                if df.loc[i - r, "High"] > current_high or df.loc[i + r, "High"] > current_high:
                    is_high = False
                    break

            if is_high:
                is_higher = True if last_high_price is None else current_high > last_high_price
                last_high_price = current_high

                swing_points.append(SwingPoint(
                    index=i, date=current_date, price=float(current_high),
                    type="HIGH", is_higher=is_higher
                ))
                continue

            # 2. Fractal Low Test (Trough) -- strict '<' on both sides (see above).
            is_low = True
            for r in range(1, self.window + 1):
                if df.loc[i - r, "Low"] < current_low or df.loc[i + r, "Low"] < current_low:
                    is_low = False
                    break

            if is_low:
                is_higher = True if last_low_price is None else current_low > last_low_price
                last_low_price = current_low

                swing_points.append(SwingPoint(
                    index=i, date=current_date, price=float(current_low),
                    type="LOW", is_higher=is_higher
                ))

        return swing_points
    
swing_detector = SwingDetector()
