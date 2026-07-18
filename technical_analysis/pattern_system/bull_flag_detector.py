"""
===============================================================================
Falcon AI Swing Trading Platform — Bull Flag Detector
===============================================================================
Script      : bull_flag_detector.py
Package     : Technical Analysis / Pattern System

A continuation pattern, not a reversal one -- only valid within an
existing UPTREND (same trend-gate reasoning already established for VCP).
Conceptually closest to VCP but on a much shorter timeframe: a sharp
"flagpole" move, then a brief, shallow consolidation.
===============================================================================
"""
from __future__ import annotations
import pandas as pd

class BullFlagDetector:
    FLAGPOLE_LOOKBACK_DAYS = 10
    MIN_FLAGPOLE_GAIN_PCT = 15.0
    FLAG_MAX_DAYS = 10
    FLAG_MAX_RETRACE_PCT = 50.0   # of the flagpole's gain

    def analyze_bull_flag(self, df: pd.DataFrame, trend_state: str) -> dict:
        if trend_state != "UPTREND":
            return {
                "is_bull_flag_setup": False, "is_breakout_confirmed": False,
                "invalidated_reason": "NOT_IN_UPTREND",
            }

        # +1 so today (the potential breakout day) can be excluded from the
        # flag/pole window construction below -- same self-reference fix as
        # flat_base_detector.py and cup_handle_detector.py: a naive
        # df.tail(N) would include today's own High (always >= today's
        # Close), making price_crossed_pivot nearly impossible to satisfy
        # on a genuine breakout day.
        if len(df) < self.FLAGPOLE_LOOKBACK_DAYS + self.FLAG_MAX_DAYS + 1:
            return {
                "is_bull_flag_setup": False, "is_breakout_confirmed": False,
                "invalidated_reason": "INSUFFICIENT_HISTORY",
            }

        history = df.iloc[:-1]
        latest_row = df.iloc[-1]

        flag_window = history.tail(self.FLAG_MAX_DAYS)
        pole_window = history.tail(self.FLAGPOLE_LOOKBACK_DAYS + self.FLAG_MAX_DAYS).head(self.FLAGPOLE_LOOKBACK_DAYS)

        pole_start = pole_window["Close"].iloc[0]
        pole_end = pole_window["Close"].iloc[-1]
        pole_gain_pct = ((pole_end - pole_start) / pole_start) * 100 if pole_start > 0 else 0.0
        flagpole_valid = pole_gain_pct >= self.MIN_FLAGPOLE_GAIN_PCT

        flag_high = flag_window["High"].max()
        flag_low = flag_window["Low"].min()
        pole_range = pole_end - pole_start
        retrace_pct = ((flag_high - flag_low) / pole_range * 100) if pole_range > 0 else 100.0
        flag_valid = retrace_pct <= self.FLAG_MAX_RETRACE_PCT

        is_bull_flag_setup = flagpole_valid and flag_valid

        if not is_bull_flag_setup:
            reason = "FLAGPOLE_TOO_WEAK" if not flagpole_valid else "FLAG_RETRACE_TOO_DEEP"
            return {
                "is_bull_flag_setup": False, "is_breakout_confirmed": False,
                "flagpole_gain_pct": round(pole_gain_pct, 1),
                "invalidated_reason": reason,
            }

        latest_close = latest_row["Close"]
        latest_volume = latest_row["Volume"]
        volume_baseline = df["Volume_SMA_20"].iloc[-1] if "Volume_SMA_20" in df.columns \
            else df["Volume"].rolling(window=20).mean().iloc[-1]

        price_crossed_pivot = latest_close > flag_high
        breakout_volume_confirmed = (
            not pd.isna(volume_baseline) and volume_baseline > 0
            and latest_volume >= volume_baseline * 1.5
        )

        return {
            "is_bull_flag_setup": is_bull_flag_setup,
            "flagpole_gain_pct": round(pole_gain_pct, 1),
            "pivot_level": flag_high,
            "price_crossed_pivot": price_crossed_pivot,
            "breakout_volume_confirmed": breakout_volume_confirmed,
            "is_breakout_confirmed": is_bull_flag_setup and price_crossed_pivot and breakout_volume_confirmed,
            "invalidated_reason": None,
        }

bull_flag_detector = BullFlagDetector()
