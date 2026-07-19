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

macro_swing_detector = SwingDetector(window=5)
micro_swing_detector = SwingDetector(window=2)


def analyze_ticker(df: pd.DataFrame) -> dict:
    """
    Runs the full per-ticker detection chain (swing fractals, market
    structure, VCP, FVG, and all 4 continuation-pattern detectors, plus
    cross-pattern aggregation) against `df` exactly as given -- no
    truncation or other preprocessing happens here, that's the caller's
    job.

    Shared by PatternEngine.execute_pipeline() (live scan, full history)
    and backtesting/replay_engine.py (point-in-time replay, truncated
    history) so both paths run through the identical chain -- a backtest
    is only meaningful if it reconstructs precisely what the live system
    would have said, so this must never fork into two implementations.
    """
    macro_pivots = macro_swing_detector.detect_swings(df)
    micro_pivots = micro_swing_detector.detect_swings(df)

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

    # Aggregate which pattern(s) actually confirmed a breakout -- these
    # aren't mutually exclusive, a stock could satisfy more than one
    # shape at once.
    pattern_results = [
        ("VCP", vcp), ("Flat_Base", flat_base), ("Cup_Handle", cup_handle),
        ("Ascending_Triangle", triangle), ("Bull_Flag", bull_flag),
    ]
    aggregated = aggregate_confirmed_patterns(pattern_results)

    return {
        "struct": struct, "vcp": vcp, "fvg": fvg,
        "flat_base": flat_base, "cup_handle": cup_handle,
        "triangle": triangle, "bull_flag": bull_flag,
        **aggregated,
    }


def build_pattern_row_fields(analysis: dict) -> dict:
    """
    Builds the exact field values PatternEngine.execute_pipeline() writes
    as parquet columns per ticker (Trend_State, Is_VCP_Breakout,
    VCP_Pivot_Level, and the rest) from analyze_ticker()'s result -- as a
    plain dict, not written onto any dataframe here.

    Shared by execute_pipeline() (broadcasts each value across the whole
    historical dataframe as a column -- see its own comment on why that's
    correct for live scanning) and backtesting/replay_engine.py (needs
    just these values for one point-in-time candidate). Keeping this in
    one place is what guarantees the two paths can't silently diverge on
    column names or values.

    Deliberately excludes Delivery_Pct_20d_avg: unlike everything here
    (a single "current state" value meaningfully broadcast across an
    entire file), that one is a genuine per-row rolling column -- every
    row needs its own trailing 20-day average, not the latest row's value
    repeated everywhere. Each caller computes it separately for that
    reason.
    """
    struct = analysis["struct"]
    vcp = analysis["vcp"]
    fvg = analysis["fvg"]
    flat_base = analysis["flat_base"]
    cup_handle = analysis["cup_handle"]
    triangle = analysis["triangle"]
    bull_flag = analysis["bull_flag"]

    return {
        "Trend_State": struct["trend_state"],
        "Is_BOS": struct["is_break_of_structure"],
        "Is_Liquidity_Sweep": struct["is_liquidity_sweep"],
        "Sweep_Type": str(struct["sweep_type"]),
        "Is_VCP_Setup": vcp["is_vcp_setup"],
        "VCP_Score": vcp["vcp_score"],
        "Is_VCP_Breakout": vcp["is_vcp_breakout"],
        "Has_Active_FVG": fvg["has_active_fvg"],
        "Is_Flat_Base_Setup": flat_base.get("is_flat_base_setup", False),
        "Is_Flat_Base_Breakout": flat_base.get("is_breakout_confirmed", False),
        "Is_Cup_Handle_Setup": cup_handle.get("is_cup_handle_setup", False),
        "Is_Cup_Handle_Breakout": cup_handle.get("is_breakout_confirmed", False),
        "Is_Ascending_Triangle_Setup": triangle.get("is_ascending_triangle_setup", False),
        "Is_Ascending_Triangle_Breakout": triangle.get("is_breakout_confirmed", False),
        "Is_Bull_Flag_Setup": bull_flag.get("is_bull_flag_setup", False),
        "Is_Bull_Flag_Breakout": bull_flag.get("is_breakout_confirmed", False),
        "Pattern_Type": analysis["pattern_type"],
        "Any_Breakout_Confirmed": analysis["any_breakout_confirmed"],
        "Multiple_Patterns_Confirmed": analysis["multiple_patterns_confirmed"],
        "Price_In_FVG": fvg["is_price_in_fvg"],
        "VCP_Price_Crossed_Pivot": vcp.get("price_crossed_pivot", False),
        "VCP_Breakout_Volume_Confirmed": vcp.get("breakout_volume_confirmed", False),
        "Flat_Base_Price_Crossed_Pivot": flat_base.get("price_crossed_pivot", False),
        "Flat_Base_Breakout_Volume_Confirmed": flat_base.get("breakout_volume_confirmed", False),
        "Cup_Handle_Price_Crossed_Pivot": cup_handle.get("price_crossed_pivot", False),
        "Cup_Handle_Breakout_Volume_Confirmed": cup_handle.get("breakout_volume_confirmed", False),
        "Ascending_Triangle_Price_Crossed_Pivot": triangle.get("price_crossed_pivot", False),
        "Ascending_Triangle_Breakout_Volume_Confirmed": triangle.get("breakout_volume_confirmed", False),
        "Bull_Flag_Price_Crossed_Pivot": bull_flag.get("price_crossed_pivot", False),
        "Bull_Flag_Breakout_Volume_Confirmed": bull_flag.get("breakout_volume_confirmed", False),
        "VCP_Pivot_Level": vcp.get("pivot_level"),
        "VCP_Structural_Low": vcp.get("final_contraction_low"),
        "Flat_Base_Pivot_Level": flat_base.get("pivot_level"),
        "Flat_Base_Low": flat_base.get("base_low"),
        "Cup_Handle_Pivot_Level": cup_handle.get("pivot_level"),
        "Cup_Handle_Low": cup_handle.get("handle_low"),
        "Ascending_Triangle_Pivot_Level": triangle.get("pivot_level"),
        "Ascending_Triangle_Support": triangle.get("most_recent_rising_low"),
        "Bull_Flag_Pivot_Level": bull_flag.get("pivot_level"),
        "Bull_Flag_Low": bull_flag.get("flag_low"),
    }


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

            analysis = analyze_ticker(df)
            struct = analysis["struct"]
            vcp = analysis["vcp"]
            fvg = analysis["fvg"]
            flat_base = analysis["flat_base"]
            cup_handle = analysis["cup_handle"]
            triangle = analysis["triangle"]
            bull_flag = analysis["bull_flag"]

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

            pattern_type = analysis["pattern_type"]
            any_breakout_confirmed = analysis["any_breakout_confirmed"]
            multiple_patterns_confirmed = analysis["multiple_patterns_confirmed"]

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

            # 3. Append Data and Save Parquet -- broadcasting each field
            # from build_pattern_row_fields() as a column is correct here:
            # it's the ticker's single current pattern state, shown
            # against every historical row for the candidate table's
            # convenience, not a per-row historical series.
            for column, value in build_pattern_row_fields(analysis).items():
                df[column] = value

            # Rolling 20-day delivery-% baseline -- kept separate from
            # build_pattern_row_fields() (see that function's own
            # docstring): this genuinely is a per-row series, not a
            # broadcast scalar. Same defensive pattern already used for
            # Volume_SMA_20 elsewhere. Without this,
            # leadership_decision_engine.py's LOW_DELIVERY_CONVICTION
            # check silently compares against its hardcoded 100 fallback
            # in real usage, since nothing computed a real average before.
            df["Delivery_Pct_20d_avg"] = (
                df["Delivery_Pct"].rolling(window=20).mean()
                if "Delivery_Pct" in df.columns else None
            )

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