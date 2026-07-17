"""
===============================================================================
Falcon AI Swing Trading Platform — Volatility Contraction Pattern (VCP) Detector
===============================================================================
Script      : vcp_detector.py
Package     : Technical Analysis / Pattern System
===============================================================================
"""
from __future__ import annotations
import pandas as pd
from technical_analysis.pattern_system.models import SwingPoint, VCPContraction

class VCPDetector:
    def __init__(self, min_contractions: int = 2, max_contractions: int = 4):
        self.min_contractions = min_contractions
        self.max_contractions = max_contractions

    def analyze_vcp(self, df: pd.DataFrame, micro_pivots: list[SwingPoint], trend_state: str) -> dict:
        """Processes tightening cycles and tracks volume dry-up to find VCP formations."""
        if trend_state != "UPTREND":
            return {
                "is_vcp_setup": False, "contractions_count": 0,
                "vcp_score": 0.0, "is_vcp_breakout": False,
                "invalidated_reason": "NOT_IN_UPTREND",
            }

        if len(micro_pivots) < (self.min_contractions * 2):
            return {
                "is_vcp_setup": False, "contractions_count": 0,
                "vcp_score": 0.0, "is_vcp_breakout": False,
                "invalidated_reason": "INSUFFICIENT_PIVOTS",
            }

        contractions = []
        wave_idx = 1

        for i in range(len(micro_pivots) - 1):
            p1 = micro_pivots[i]
            p2 = micro_pivots[i + 1]

            if p1.type == "HIGH" and p2.type == "LOW":
                depth = ((p1.price - p2.price) / p1.price) * 100
                contractions.append(VCPContraction(
                    wave_number=wave_idx, swing_high_price=p1.price,
                    swing_low_price=p2.price, depth_percentage=round(depth, 2),
                    length_days=p2.index - p1.index
                ))
                wave_idx += 1

        contractions = contractions[-self.max_contractions:]

        if len(contractions) < self.min_contractions:
            return {
                "is_vcp_setup": False, "contractions_count": 0,
                "vcp_score": 0.0, "is_vcp_breakout": False,
                "invalidated_reason": "INSUFFICIENT_CONTRACTIONS",
            }

        # Check that each sequential wave depth is smaller than the last
        is_contracting = True
        for idx in range(len(contractions) - 1):
            if contractions[idx].depth_percentage <= contractions[idx + 1].depth_percentage:
                is_contracting = False
                break

        if not is_contracting:
            return {
                "is_vcp_setup": False, "contractions_count": len(contractions),
                "vcp_score": 0.0, "is_vcp_breakout": False,
                "invalidated_reason": "NOT_CONTRACTING",
            }

        # Volume Dry-Up Verification (VDU)
        df = df.sort_values(by="Date", ascending=True).reset_index(drop=True)
        recent_vol_avg = df["Volume"].tail(3).mean()
        vol_baseline = df["Volume_SMA_20"].iloc[-1] if "Volume_SMA_20" in df.columns else df["Volume"].rolling(window=20).mean().iloc[-1]
        vdu_confirmed = recent_vol_avg < vol_baseline

        # Score generation
        vcp_score = 50.0
        if vdu_confirmed:
            vcp_score += 25.0
        if contractions[-1].depth_percentage < 6.0:
            vcp_score += 25.0

        latest_close = df["Close"].iloc[-1]
        resistance_pivot = contractions[-1].swing_high_price

        latest_volume = df["Volume"].iloc[-1]
        volume_baseline = df["Volume_SMA_20"].iloc[-1] if "Volume_SMA_20" in df.columns \
            else df["Volume"].rolling(window=20).mean().iloc[-1]

        price_crossed_pivot = latest_close > resistance_pivot
        breakout_volume_confirmed = (
            not pd.isna(volume_baseline) and volume_baseline > 0
            and latest_volume >= (volume_baseline * 1.5)
        )

        is_breakout = price_crossed_pivot and breakout_volume_confirmed

        return {
            "is_vcp_setup": True,
            "contractions_count": len(contractions),
            "last_contraction_depth": contractions[-1].depth_percentage,
            "vdu_confirmed": vdu_confirmed,
            "vcp_score": vcp_score,
            "is_vcp_breakout": is_breakout,
            "price_crossed_pivot": price_crossed_pivot,
            "breakout_volume_confirmed": breakout_volume_confirmed,
            "pivot_level": resistance_pivot,
            "invalidated_reason": None,
        }
    
vcp_detector = VCPDetector()