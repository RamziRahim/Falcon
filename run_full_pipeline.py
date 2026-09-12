"""
Falcon — Manual Full Pipeline Runner

Runs the complete chain that the "New Scan" button in app.py currently
DOESN'T: candidate generation -> market data download -> indicator
calculation -> pattern detection. Use this to populate real data/patterns/
files so the app has something real to show, until this chain gets wired
directly into the New Scan button (separate task).

Usage:
    python run_full_pipeline.py
"""
from candidate_generation.candidate_generator import generate_candidates
from market_data.data_collection_engine import DataCollectionEngine
from technical_analysis.indicator_engine import IndicatorEngine
from technical_analysis.pattern_engine import PatternEngine


def main():
    print("=" * 60)
    print("STEP 1/4 — Candidate Generation (Screener.in scan)")
    print("=" * 60)
    candidates_df = generate_candidates()

    if candidates_df.empty or "Symbol" not in candidates_df.columns:
        print("No candidates generated — check Screener.in credentials in .env")
        return

    ticker_universe = [
        f"{sym}.NS" if not str(sym).endswith(".NS") else str(sym)
        for sym in candidates_df["Symbol"].tolist()
    ]
    print(f"\nGot {len(ticker_universe)} candidates: {ticker_universe}\n")

    print("=" * 60)
    print("STEP 2/4 — Market Data Collection (downloading OHLCV)")
    print("=" * 60)
    DataCollectionEngine().run(symbols=ticker_universe)

    print("\n" + "=" * 60)
    print("STEP 3/4 — Indicator Calculation")
    print("=" * 60)
    IndicatorEngine().run(symbols=ticker_universe)

    print("\n" + "=" * 60)
    print("STEP 4/4 — Pattern Detection")
    print("=" * 60)
    PatternEngine().execute_pipeline()

    print("\n" + "=" * 60)
    print(f"DONE — data/patterns/ should now have real files for "
          f"{len(ticker_universe)} tickers. Run the app and check.")
    print("=" * 60)


if __name__ == "__main__":
    main()
