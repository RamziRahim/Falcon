"""
===============================================================================
Falcon AI Swing Trading Platform — Core Orchestration Pattern Engine
===============================================================================
Script      : pattern_engine.py
Package     : Technical Analysis
===============================================================================
"""
from __future__ import annotations
import os
import glob
import pandas as pd

from technical_analysis.pattern_system.swing_detector import SwingDetector
from technical_analysis.pattern_system.market_structure import market_structure_engine
from technical_analysis.pattern_system.vcp_detector import vcp_detector
from technical_analysis.pattern_system.fvg_detector import fvg_detector

class PatternEngine:
    def __init__(self, src_dir: str = "data/technical", dest_dir: str = "data/patterns"):
        self.src_dir = src_dir
        self.dest_dir = dest_dir
        os.makedirs(self.dest_dir, exist_ok=True)
        
        self.macro_detector = SwingDetector(window=5)
        self.micro_detector = SwingDetector(window=2)

    def execute_pipeline(self):
        print("============================================================")
        print("          FALCON PHASE 5 PATTERN DETECTION ENGINE           ")
        print("============================================================")
        
        search_path = os.path.join(self.src_dir, "*.parquet")
        files = glob.glob(search_path)
        
        if not files:
            print(f"[ERROR] No parquet datasets found inside {self.src_dir}. Please run Phase 4 first.")
            return

        metrics = {"total": 0, "uptrends": 0, "vcp": 0, "bos": 0, "sweeps": 0, "fvgs": 0}

        for file_path in files:
            ticker = os.path.basename(file_path).replace(".parquet", "")
            df = pd.read_parquet(file_path)
            
            if len(df) < 20:
                continue
                
            metrics["total"] += 1

            # 1. Preprocess Multi-Scale Fractals
            macro_pivots = self.macro_detector.detect_swings(df)
            micro_pivots = self.micro_detector.detect_swings(df)

            # 2. Extract Institutional Variables
            struct = market_structure_engine.analyze_structure(df, macro_pivots)
            vcp = vcp_detector.analyze_vcp(df, micro_pivots, struct["trend_state"])
            fvg = fvg_detector.detect_fvgs(df)

            if struct["trend_state"] == "UPTREND":
                metrics["uptrends"] += 1
            if struct["is_break_of_structure"]:
                metrics["bos"] += 1
            if struct["is_liquidity_sweep"]:
                metrics["sweeps"] += 1
            if vcp["is_vcp_setup"]:
                metrics["vcp"] += 1
            if fvg["has_active_fvg"]:
                metrics["fvgs"] += 1

            # Console logging dashboard for strategic confluences
            if vcp["is_vcp_setup"] or struct["is_liquidity_sweep"] or fvg["is_price_in_fvg"]:
                print(f"\n[TARGET TICKER] {ticker} -> Structure: {struct['trend_state']}")
                if struct['is_liquidity_sweep']:
                    print(f"  ↳ ⚠️ Institutional {struct['sweep_type']} Sweep Found within 10 days!")
                if fvg['has_active_fvg']:
                    print(f"  ↳ 🗺️ Active FVG Imbalance: ₹{fvg['fvg_bottom']} - ₹{fvg['fvg_top']}")
                    if fvg['is_price_in_fvg']:
                        print("    ⚡ Tactics: Price is currently cooling down inside the FVG buy zone.")
                if vcp['is_vcp_setup']:
                    print(f"  ↳ 🔥 VCP Setup (Score: {vcp['vcp_score']}% | Breakout: {vcp['is_vcp_breakout']})")

            # 3. Append Data and Save Parquet
            df["Trend_State"] = struct["trend_state"]
            df["Is_BOS"] = struct["is_break_of_structure"]
            df["Is_Liquidity_Sweep"] = struct["is_liquidity_sweep"]
            df["Sweep_Type"] = str(struct["sweep_type"])
            df["Is_VCP_Setup"] = vcp["is_vcp_setup"]
            df["VCP_Score"] = vcp["vcp_score"]
            df["Is_VCP_Breakout"] = vcp["is_vcp_breakout"]
            df["Has_Active_FVG"] = fvg["has_active_fvg"]
            df["Price_In_FVG"] = fvg["is_price_in_fvg"]

            df.to_parquet(os.path.join(self.dest_dir, f"{ticker}.parquet"))

        print("\n============================================================")
        print("         FALCON PHASE 5 PIPELINE EXECUTION METRICS          ")
        print("============================================================")
        print(f" TOTAL TICKERS PROCESSED      : {metrics['total']}")
        print(f" BULLISH UPTRENDS IDENTIFIED  : {metrics['uptrends']}")
        print(f" ACTIVE VCP SETUPS FOUND      : {metrics['vcp']}")
        print(f" BREAKS OF STRUCTURE (BOS)    : {metrics['bos']}")
        print(f" LIQUIDITY SWEEPS DETECTED    : {metrics['sweeps']}")
        print(f" ACTIVE UNMITIGATED FVGS MAP  : {metrics['fvgs']}")
        print(" OUTPUT EXPORT STATUS         : SUCCESS (.parquet Generated)")
        print("============================================================")

if __name__ == "__main__":
    engine = PatternEngine()
    engine.execute_pipeline()