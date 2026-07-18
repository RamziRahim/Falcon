"""
===============================================================================
Falcon AI Swing Trading Platform — Ascending Triangle Detector
===============================================================================
Script      : ascending_triangle_detector.py
Package     : Technical Analysis / Pattern System

A continuation pattern, not a reversal one -- only valid within an
existing UPTREND (same trend-gate reasoning already established for VCP).
Reuses swing_detector.py's full pivot list (both highs and lows) -- needs
rising lows and a flat resistance ceiling simultaneously. Unlike
flat_base_detector.py / bull_flag_detector.py's raw tail-window approach,
using confirmed pivots here means the current/forming bar is naturally
never part of the resistance_level itself (a pivot requires confirmation
bars on both sides), so there's no self-reference risk between the
breakout bar and its own pivot level.
===============================================================================
"""
from __future__ import annotations
import pandas as pd

class AscendingTriangleDetector:
    RESISTANCE_TOLERANCE_PCT = 3.0   # highs within this % count as "flat"
    MIN_TOUCHES = 2                   # at least 2 highs near the same level

    def analyze_ascending_triangle(self, df: pd.DataFrame, swing_points: list, trend_state: str) -> dict:
        if trend_state != "UPTREND":
            return {
                "is_ascending_triangle_setup": False, "is_breakout_confirmed": False,
                "invalidated_reason": "NOT_IN_UPTREND",
            }

        highs = sorted([p for p in swing_points if p.type == "HIGH"], key=lambda p: p.index)
        lows = sorted([p for p in swing_points if p.type == "LOW"], key=lambda p: p.index)

        if len(highs) < self.MIN_TOUCHES or len(lows) < self.MIN_TOUCHES:
            return {
                "is_ascending_triangle_setup": False, "is_breakout_confirmed": False,
                "invalidated_reason": "INSUFFICIENT_PIVOTS",
            }

        recent_highs = highs[-self.MIN_TOUCHES:]
        recent_lows = lows[-self.MIN_TOUCHES:]

        resistance_level = sum(p.price for p in recent_highs) / len(recent_highs)
        highs_are_flat = all(
            abs(p.price - resistance_level) / resistance_level * 100 <= self.RESISTANCE_TOLERANCE_PCT
            for p in recent_highs
        )
        lows_are_rising = all(
            recent_lows[i].price < recent_lows[i + 1].price
            for i in range(len(recent_lows) - 1)
        )

        is_ascending_triangle_setup = highs_are_flat and lows_are_rising

        if not is_ascending_triangle_setup:
            reason = "RESISTANCE_NOT_FLAT" if not highs_are_flat else "LOWS_NOT_RISING"
            return {
                "is_ascending_triangle_setup": False, "is_breakout_confirmed": False,
                "resistance_level": round(resistance_level, 2),
                "invalidated_reason": reason,
            }

        latest_close = df["Close"].iloc[-1]
        latest_volume = df["Volume"].iloc[-1]
        volume_baseline = df["Volume_SMA_20"].iloc[-1] if "Volume_SMA_20" in df.columns \
            else df["Volume"].rolling(window=20).mean().iloc[-1]

        price_crossed_pivot = latest_close > resistance_level
        breakout_volume_confirmed = (
            not pd.isna(volume_baseline) and volume_baseline > 0
            and latest_volume >= volume_baseline * 1.5
        )

        return {
            "is_ascending_triangle_setup": is_ascending_triangle_setup,
            "resistance_level": round(resistance_level, 2),
            "pivot_level": resistance_level,
            "price_crossed_pivot": price_crossed_pivot,
            "breakout_volume_confirmed": breakout_volume_confirmed,
            "is_breakout_confirmed": is_ascending_triangle_setup and price_crossed_pivot and breakout_volume_confirmed,
            "invalidated_reason": None,
        }

ascending_triangle_detector = AscendingTriangleDetector()
