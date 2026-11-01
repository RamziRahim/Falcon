"""
===============================================================================
Falcon AI Swing Trading Platform — Fractal Swing Point Detector
===============================================================================
Script      : swing_detector.py
Package     : Technical Analysis / Pattern System
===============================================================================
"""
from __future__ import annotations
import numpy as np
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
        """Scans a dataframe chronologically and extracts a list of validated Fractal SwingPoints.

        A bar is a swing HIGH if no bar within `window` bars on either side
        has a strictly higher High (strict '>' on both sides, so an exact
        tie doesn't invalidate a pivot -- previously the left side used
        '>=', rejecting a tie there while the right side's '>' tolerated
        the identical tie, asymmetric with no rationale). Otherwise it is a
        swing LOW if no neighbour has a strictly lower Low. is_higher
        compares each pivot with the previous pivot of the same type.

        Vectorised 2026-11-01 (was a per-bar loop of scalar df.loc reads,
        ~80% of all backtest time). Same comparisons on the same values in
        the same order, so the output is identical -- see
        tests/technical_analysis/test_swing_detector_equivalence.py, which
        checks it against the original loop on real and adversarial data.
        """
        swing_points = []
        df_len = len(df)
        df = df.sort_values(by="Date", ascending=True).reset_index(drop=True)
        w = self.window
        if df_len <= 2 * w:
            return swing_points

        highs = df["High"].to_numpy()
        lows = df["Low"].to_numpy()
        centre = slice(w, df_len - w)

        # A neighbour that is strictly beyond the centre bar disqualifies
        # it. NaN compares False, exactly as the scalar loop did.
        beaten_high = np.zeros(df_len - 2 * w, dtype=bool)
        beaten_low = np.zeros(df_len - 2 * w, dtype=bool)
        for r in range(1, w + 1):
            left = slice(w - r, df_len - w - r)
            right = slice(w + r, df_len - w + r)
            beaten_high |= (highs[left] > highs[centre]) | (highs[right] > highs[centre])
            beaten_low |= (lows[left] < lows[centre]) | (lows[right] < lows[centre])

        is_high = ~beaten_high
        is_low = ~beaten_low & beaten_high          # LOW is only tested when not a HIGH
        candidates = np.flatnonzero(is_high | is_low) + w
        if len(candidates) == 0:
            return swing_points

        dates = df["Date"]
        last_high_price = None
        last_low_price = None

        for i in candidates:
            i = int(i)
            current_date = str(dates.iloc[i])
            if is_high[i - w]:
                current_high = highs[i]
                is_higher = True if last_high_price is None else current_high > last_high_price
                last_high_price = current_high
                swing_points.append(SwingPoint(
                    index=i, date=current_date, price=float(current_high),
                    type="HIGH", is_higher=is_higher
                ))
            else:
                current_low = lows[i]
                is_higher = True if last_low_price is None else current_low > last_low_price
                last_low_price = current_low
                swing_points.append(SwingPoint(
                    index=i, date=current_date, price=float(current_low),
                    type="LOW", is_higher=is_higher
                ))

        return swing_points

swing_detector = SwingDetector()
