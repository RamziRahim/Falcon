"""
===============================================================================
Falcon AI Swing Trading Platform — Cup-with-Handle Detector
===============================================================================
Script      : cup_handle_detector.py
Package     : Technical Analysis / Pattern System

A continuation pattern, not a reversal one -- only valid within an
existing UPTREND (same trend-gate reasoning already established for VCP).

Worth being upfront about a real limitation: genuine "cup roundness" is
traditionally a visual/gestalt judgment, not something that reduces
perfectly to a formula. The heuristic here (low roughly centered in the
window) is a reasonable v1 simplification, not a claim of perfect
fidelity to the classic O'Neil pattern.
===============================================================================
"""
from __future__ import annotations
import pandas as pd

class CupHandleDetector:
    MIN_CUP_WEEKS, MAX_CUP_WEEKS = 7, 65      # O'Neil's own bounds
    MIN_CUP_DEPTH_PCT, MAX_CUP_DEPTH_PCT = 12.0, 50.0
    MAX_HANDLE_DEPTH_PCT = 12.0
    HANDLE_MIN_DAYS, HANDLE_MAX_DAYS = 5, 15  # HANDLE_MIN_DAYS reserved for a future refinement -- not yet enforced below

    def analyze_cup_handle(self, df: pd.DataFrame, trend_state: str) -> dict:
        if trend_state != "UPTREND":
            return {
                "is_cup_handle_setup": False, "is_breakout_confirmed": False,
                "invalidated_reason": "NOT_IN_UPTREND",
            }

        cup_window_days = self.MAX_CUP_WEEKS * 5  # trading days

        # +1 so today (the potential breakout day) can be excluded from
        # the cup/handle window construction below -- same self-reference
        # fix as flat_base_detector.py: a naive df.tail(N) would include
        # today's own High (always >= today's Close), making
        # price_crossed_pivot nearly impossible to satisfy on a genuine
        # breakout day (confirmed with a concrete fixture during
        # development, same failure mode as the flat base bug).
        if len(df) < cup_window_days + 1:
            return {
                "is_cup_handle_setup": False, "is_breakout_confirmed": False,
                "invalidated_reason": "INSUFFICIENT_HISTORY",
            }

        history = df.iloc[:-1]
        latest_row = df.iloc[-1]

        window = history.tail(cup_window_days)
        cup_high = window["High"].iloc[:len(window) // 3].max()  # left third = pre-decline high
        low_idx = window["Low"].idxmin()
        cup_low = window.loc[low_idx, "Low"]

        # Roundness proxy: the low should fall roughly in the middle third
        # of the window, not right at the start (still declining) or right
        # at the end (no time to recover) -- a crude but workable substitute
        # for true visual roundness.
        low_position_pct = (window.index.get_loc(low_idx) / len(window)) * 100
        is_roughly_centered = 25 <= low_position_pct <= 75

        depth_pct = ((cup_high - cup_low) / cup_high) * 100 if cup_high > 0 else 100.0
        depth_valid = self.MIN_CUP_DEPTH_PCT <= depth_pct <= self.MAX_CUP_DEPTH_PCT

        # Handle: last HANDLE_MAX_DAYS (excluding today), shallower pullback near cup_high
        handle_window = history.tail(self.HANDLE_MAX_DAYS)
        handle_high = handle_window["High"].max()
        handle_low = handle_window["Low"].min()
        handle_depth_pct = ((handle_high - handle_low) / handle_high) * 100 if handle_high > 0 else 100.0
        handle_valid = handle_depth_pct <= self.MAX_HANDLE_DEPTH_PCT

        is_cup_handle_setup = is_roughly_centered and depth_valid and handle_valid

        if not is_cup_handle_setup:
            if not is_roughly_centered:
                reason = "CUP_NOT_ROUNDED"
            elif not depth_valid:
                reason = "CUP_DEPTH_OUT_OF_RANGE"
            else:
                reason = "HANDLE_TOO_DEEP"
            return {
                "is_cup_handle_setup": False, "is_breakout_confirmed": False,
                "cup_depth_pct": round(depth_pct, 1), "handle_depth_pct": round(handle_depth_pct, 1),
                "invalidated_reason": reason,
            }

        latest_close = latest_row["Close"]
        latest_volume = latest_row["Volume"]
        volume_baseline = df["Volume_SMA_20"].iloc[-1] if "Volume_SMA_20" in df.columns \
            else df["Volume"].rolling(window=20).mean().iloc[-1]

        price_crossed_pivot = latest_close > handle_high
        breakout_volume_confirmed = (
            not pd.isna(volume_baseline) and volume_baseline > 0
            and latest_volume >= volume_baseline * 1.5
        )

        return {
            "is_cup_handle_setup": is_cup_handle_setup,
            "cup_depth_pct": round(depth_pct, 1),
            "handle_depth_pct": round(handle_depth_pct, 1),
            "pivot_level": handle_high,
            # Structural low of the handle -- needed for a real, non-ATR-
            # fallback stop-loss/target.
            "handle_low": handle_low,
            "price_crossed_pivot": price_crossed_pivot,
            "breakout_volume_confirmed": breakout_volume_confirmed,
            "is_breakout_confirmed": is_cup_handle_setup and price_crossed_pivot and breakout_volume_confirmed,
            "invalidated_reason": None,
        }

cup_handle_detector = CupHandleDetector()
