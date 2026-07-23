"""
===============================================================================
Falcon AI Swing Trading Platform — Fundamental Engine Test Harness
===============================================================================
Script      : test_fundamental_engine.py
Objective   : Verify raw 4-layer fundamental data parsing & structural health
===============================================================================
"""
from __future__ import annotations
import json
import sys
from fundamental_analysis import fundamental_engine

def run_isolated_fundamental_check(target_ticker: str):
    print("=" * 75)
    print(f" TESTING ISOLATED FUNDAMENTAL ENGINE HARVESTER FOR: {target_ticker}")
    print("=" * 75)
    
    try:
        print(f"» Dispatching master coordinator data sweep for {target_ticker}...")
        # Pull the complete synthesized data matrix block
        data_packet = fundamental_engine.get_complete_data_packet(target_ticker)
        
        print("\n✅ SUCCESS: Structural Master Packet Recovered Successfully!")
        print("\n=== MASTER CONSOLIDATED DATA PACKET LAYOUT ===")
        print(json.dumps(data_packet, indent=4))
        print("=" * 75)
        
    except IndexError as ie:
        print(f"\n❌ INDEX ERROR DETECTED: Data tracking bounds overflowed. {ie}")
        print("Verify your corporate_engine.py contains length checks against raw columns.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ RUNTIME CRASH: Engine failed to process asset: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Test a rock-solid known baseline counter first
    run_isolated_fundamental_check("CGPOWER")