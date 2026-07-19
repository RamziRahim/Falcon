"""
===============================================================================
Falcon AI Swing Trading Platform — Flat Base Detector
===============================================================================
Script      : flat_base_detector.py
Package     : Technical Analysis / Pattern System

A continuation pattern, not a reversal one -- only valid within an
existing UPTREND (same trend-gate reasoning already established for VCP).
Simplest of the four new continuation detectors: the base is just the
high/low range over the trailing window, no pivot-list traversal needed.
===============================================================================
"""
from __future__ import annotations
import pandas as pd

class FlatBaseDetector:
    MIN_DURATION_DAYS = 25   # ~5 weeks, O'Neil's minimum
    MAX_DEPTH_PCT = 15.0

    def analyze_flat_base(self, df: pd.DataFrame, macro_pivots: list, trend_state: str) -> dict:
        if trend_state != "UPTREND":
            return {
                "is_flat_base_setup": False, "is_breakout_confirmed": False,
                "invalidated_reason": "NOT_IN_UPTREND",
            }

        if len(df) < self.MIN_DURATION_DAYS + 1:
            return {
                "is_flat_base_setup": False, "is_breakout_confirmed": False,
                "invalidated_reason": "INSUFFICIENT_HISTORY",
            }

        # Base = the range over the trailing window EXCLUDING today. Today
        # is the potential breakout day being measured AGAINST the base,
        # not part of it -- including today (a naive df.tail(N)) creates a
        # self-reference bug: today's own High is always >= today's Close
        # by OHLC construction, so base_high would always incorporate
        # today's high, making price_crossed_pivot nearly impossible to
        # satisfy on the actual day of a genuine breakout (confirmed with a
        # concrete fixture during development: a legitimate breakout day
        # failed both the depth check and the price-cross check purely
        # because its own high inflated the base range it was being
        # compared against).
        base_window = df.iloc[-(self.MIN_DURATION_DAYS + 1):-1]
        latest_row = df.iloc[-1]

        base_high = base_window["High"].max()
        base_low = base_window["Low"].min()
        depth_pct = ((base_high - base_low) / base_high) * 100 if base_high > 0 else 100.0

        is_flat_base_setup = depth_pct <= self.MAX_DEPTH_PCT

        if not is_flat_base_setup:
            return {
                "is_flat_base_setup": False, "is_breakout_confirmed": False,
                "base_depth_pct": round(depth_pct, 1),
                "invalidated_reason": "BASE_TOO_DEEP",
            }

        latest_close = latest_row["Close"]
        latest_volume = latest_row["Volume"]
        # Fall back to a rolling recompute if Volume_SMA_20 isn't present --
        # same defensive convention already established for VCP, so a
        # missing indicator column degrades gracefully rather than raising.
        volume_baseline = df["Volume_SMA_20"].iloc[-1] if "Volume_SMA_20" in df.columns \
            else df["Volume"].rolling(window=20).mean().iloc[-1]

        price_crossed_pivot = latest_close > base_high
        breakout_volume_confirmed = (
            not pd.isna(volume_baseline) and volume_baseline > 0
            and latest_volume >= volume_baseline * 1.5
        )

        return {
            "is_flat_base_setup": is_flat_base_setup,
            "base_depth_pct": round(depth_pct, 1),
            "pivot_level": base_high,
            # Structural low of the base -- needed for a real, non-ATR-
            # fallback stop-loss/target.
            "base_low": base_low,
            "price_crossed_pivot": price_crossed_pivot,
            "breakout_volume_confirmed": breakout_volume_confirmed,
            "is_breakout_confirmed": is_flat_base_setup and price_crossed_pivot and breakout_volume_confirmed,
            "invalidated_reason": None,
        }

flat_base_detector = FlatBaseDetector()
