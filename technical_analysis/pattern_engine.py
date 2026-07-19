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
from technical_analysis.pattern_system.flat_base_detector import flat_base_detector
from technical_analysis.pattern_system.cup_handle_detector import cup_handle_detector
from technical_analysis.pattern_system.ascending_triangle_detector import ascending_triangle_detector
from technical_analysis.pattern_system.bull_flag_detector import bull_flag_detector

def aggregate_confirmed_patterns(pattern_results: list[tuple[str, dict]]) -> dict:
    """
    Aggregates which continuation pattern(s) actually confirmed a breakout
    across the five detectors (VCP + the four new continuation patterns).
    These aren't mutually exclusive -- a stock could satisfy more than one
    shape at once.

    Parameters
    ----------
    pattern_results : list of (pattern_name, detector_result_dict) pairs.

    Returns
    -------
    dict with keys: pattern_type (str | None, comma-joined confirmed
    names), any_breakout_confirmed (bool), multiple_patterns_confirmed (bool).
    """

    confirmed_patterns = [name for name, result in pattern_results if result.get("is_breakout_confirmed")]

    return {
        "pattern_type": ", ".join(confirmed_patterns) if confirmed_patterns else None,
        "any_breakout_confirmed": len(confirmed_patterns) > 0,
        "multiple_patterns_confirmed": len(confirmed_patterns) > 1,
    }


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

        metrics = {
            "total": 0, "uptrends": 0, "vcp": 0, "bos": 0, "sweeps": 0, "fvgs": 0,
            "flat_base": 0, "cup_handle": 0, "ascending_triangle": 0, "bull_flag": 0,
            "any_breakout": 0, "multiple_patterns": 0,
        }

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

            # Continuation patterns -- all four require the same UPTREND
            # trend-gate as VCP, for the same methodology reason: only
            # valid setups within an existing advance, not standalone
            # shapes. Flat Base and Ascending Triangle reuse macro_pivots
            # (same multi-week timeframe as market structure); Bull Flag
            # operates on raw price/volume over a much shorter window.
            flat_base = flat_base_detector.analyze_flat_base(df, macro_pivots, struct["trend_state"])
            cup_handle = cup_handle_detector.analyze_cup_handle(df, struct["trend_state"])
            triangle = ascending_triangle_detector.analyze_ascending_triangle(df, macro_pivots, struct["trend_state"])
            bull_flag = bull_flag_detector.analyze_bull_flag(df, struct["trend_state"])

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
            if flat_base.get("is_flat_base_setup"):
                metrics["flat_base"] += 1
            if cup_handle.get("is_cup_handle_setup"):
                metrics["cup_handle"] += 1
            if triangle.get("is_ascending_triangle_setup"):
                metrics["ascending_triangle"] += 1
            if bull_flag.get("is_bull_flag_setup"):
                metrics["bull_flag"] += 1

            # Aggregate which pattern(s) actually confirmed a breakout --
            # these aren't mutually exclusive, a stock could satisfy more
            # than one shape at once.
            pattern_results = [
                ("VCP", vcp), ("Flat_Base", flat_base), ("Cup_Handle", cup_handle),
                ("Ascending_Triangle", triangle), ("Bull_Flag", bull_flag),
            ]
            aggregated = aggregate_confirmed_patterns(pattern_results)
            pattern_type = aggregated["pattern_type"]
            any_breakout_confirmed = aggregated["any_breakout_confirmed"]
            multiple_patterns_confirmed = aggregated["multiple_patterns_confirmed"]

            if any_breakout_confirmed:
                metrics["any_breakout"] += 1
            if multiple_patterns_confirmed:
                metrics["multiple_patterns"] += 1

            # Console logging dashboard for strategic confluences
            if vcp["is_vcp_setup"] or struct["is_liquidity_sweep"] or fvg["is_price_in_fvg"] or any_breakout_confirmed:
                print(f"\n[TARGET TICKER] {ticker} -> Structure: {struct['trend_state']}")
                if struct['is_liquidity_sweep']:
                    print(f"  ↳ ⚠️ Institutional {struct['sweep_type']} Sweep Found within 10 days!")
                if fvg['has_active_fvg']:
                    print(f"  ↳ 🗺️ Active FVG Imbalance: ₹{fvg['fvg_bottom']} - ₹{fvg['fvg_top']}")
                    if fvg['is_price_in_fvg']:
                        print("    ⚡ Tactics: Price is currently cooling down inside the FVG buy zone.")
                if vcp['is_vcp_setup']:
                    print(f"  ↳ 🔥 VCP Setup (Score: {vcp['vcp_score']}% | Breakout: {vcp['is_vcp_breakout']})")
                if any_breakout_confirmed:
                    print(f"  ↳ 🚀 Pattern Breakout Confirmed: {pattern_type}")

            # 3. Append Data and Save Parquet
            df["Trend_State"] = struct["trend_state"]
            df["Is_BOS"] = struct["is_break_of_structure"]
            df["Is_Liquidity_Sweep"] = struct["is_liquidity_sweep"]
            df["Sweep_Type"] = str(struct["sweep_type"])
            df["Is_VCP_Setup"] = vcp["is_vcp_setup"]
            df["VCP_Score"] = vcp["vcp_score"]
            df["Is_VCP_Breakout"] = vcp["is_vcp_breakout"]
            df["Has_Active_FVG"] = fvg["has_active_fvg"]
            df["Is_Flat_Base_Setup"] = flat_base.get("is_flat_base_setup", False)
            df["Is_Flat_Base_Breakout"] = flat_base.get("is_breakout_confirmed", False)
            df["Is_Cup_Handle_Setup"] = cup_handle.get("is_cup_handle_setup", False)
            df["Is_Cup_Handle_Breakout"] = cup_handle.get("is_breakout_confirmed", False)
            df["Is_Ascending_Triangle_Setup"] = triangle.get("is_ascending_triangle_setup", False)
            df["Is_Ascending_Triangle_Breakout"] = triangle.get("is_breakout_confirmed", False)
            df["Is_Bull_Flag_Setup"] = bull_flag.get("is_bull_flag_setup", False)
            df["Is_Bull_Flag_Breakout"] = bull_flag.get("is_breakout_confirmed", False)
            df["Pattern_Type"] = pattern_type
            df["Any_Breakout_Confirmed"] = any_breakout_confirmed
            df["Multiple_Patterns_Confirmed"] = multiple_patterns_confirmed
            df["Price_In_FVG"] = fvg["is_price_in_fvg"]

            # Rolling 20-day delivery-% baseline -- same defensive pattern
            # already used for Volume_SMA_20 elsewhere (computed inline,
            # not itself a persisted column). Without this,
            # leadership_decision_engine.py's LOW_DELIVERY_CONVICTION
            # check silently compares against its hardcoded 100 fallback
            # in real usage, since nothing computed a real average before.
            df["Delivery_Pct_20d_avg"] = (
                df["Delivery_Pct"].rolling(window=20).mean()
                if "Delivery_Pct" in df.columns else None
            )

            # Granular per-pattern breakout sub-fields -- needed for
            # WEAK_VOLUME_CONFIRMATION (can't be computed today from just
            # the combined Is_X_Breakout booleans above) and for the
            # backtest replay engine to reconstruct a decision from
            # parquet alone, without re-running the detectors.
            df["VCP_Price_Crossed_Pivot"] = vcp.get("price_crossed_pivot", False)
            df["VCP_Breakout_Volume_Confirmed"] = vcp.get("breakout_volume_confirmed", False)
            df["Flat_Base_Price_Crossed_Pivot"] = flat_base.get("price_crossed_pivot", False)
            df["Flat_Base_Breakout_Volume_Confirmed"] = flat_base.get("breakout_volume_confirmed", False)
            df["Cup_Handle_Price_Crossed_Pivot"] = cup_handle.get("price_crossed_pivot", False)
            df["Cup_Handle_Breakout_Volume_Confirmed"] = cup_handle.get("breakout_volume_confirmed", False)
            df["Ascending_Triangle_Price_Crossed_Pivot"] = triangle.get("price_crossed_pivot", False)
            df["Ascending_Triangle_Breakout_Volume_Confirmed"] = triangle.get("breakout_volume_confirmed", False)
            df["Bull_Flag_Price_Crossed_Pivot"] = bull_flag.get("price_crossed_pivot", False)
            df["Bull_Flag_Breakout_Volume_Confirmed"] = bull_flag.get("breakout_volume_confirmed", False)

            # Pivot level and structural low per pattern -- needed for a
            # real (non-ATR-fallback) stop-loss/target, and for the
            # backtest replay engine to price historical trades off each
            # pattern's own structure instead of a generic ATR multiple.
            # None (not 0.0) when a pattern never confirmed a setup at
            # all, since these fields are only meaningful in that context.
            df["VCP_Pivot_Level"] = vcp.get("pivot_level")
            df["VCP_Structural_Low"] = vcp.get("final_contraction_low")
            df["Flat_Base_Pivot_Level"] = flat_base.get("pivot_level")
            df["Flat_Base_Low"] = flat_base.get("base_low")
            df["Cup_Handle_Pivot_Level"] = cup_handle.get("pivot_level")
            df["Cup_Handle_Low"] = cup_handle.get("handle_low")
            df["Ascending_Triangle_Pivot_Level"] = triangle.get("pivot_level")
            df["Ascending_Triangle_Support"] = triangle.get("most_recent_rising_low")
            df["Bull_Flag_Pivot_Level"] = bull_flag.get("pivot_level")
            df["Bull_Flag_Low"] = bull_flag.get("flag_low")

            df.to_parquet(os.path.join(self.dest_dir, f"{ticker}.parquet"))

        print("\n============================================================")
        print("         FALCON PHASE 5 PIPELINE EXECUTION METRICS          ")
        print("============================================================")
        print(f" TOTAL TICKERS PROCESSED      : {metrics['total']}")
        print(f" BULLISH UPTRENDS IDENTIFIED  : {metrics['uptrends']}")
        print(f" ACTIVE VCP SETUPS FOUND      : {metrics['vcp']}")
        print(f" FLAT BASE SETUPS FOUND       : {metrics['flat_base']}")
        print(f" CUP-WITH-HANDLE SETUPS FOUND : {metrics['cup_handle']}")
        print(f" ASCENDING TRIANGLE SETUPS    : {metrics['ascending_triangle']}")
        print(f" BULL FLAG SETUPS FOUND       : {metrics['bull_flag']}")
        print(f" ANY PATTERN BREAKOUT CONFIRMED : {metrics['any_breakout']}")
        print(f" MULTIPLE PATTERNS CONFIRMED  : {metrics['multiple_patterns']}")
        print(f" BREAKS OF STRUCTURE (BOS)    : {metrics['bos']}")
        print(f" LIQUIDITY SWEEPS DETECTED    : {metrics['sweeps']}")
        print(f" ACTIVE UNMITIGATED FVGS MAP  : {metrics['fvgs']}")
        print(" OUTPUT EXPORT STATUS         : SUCCESS (.parquet Generated)")
        print("============================================================")

if __name__ == "__main__":
    engine = PatternEngine()
    engine.execute_pipeline()