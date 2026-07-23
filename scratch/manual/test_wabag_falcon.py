from pathlib import Path

import pandas as pd

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

PROJECT_ROOT = Path(r"C:\TeraBoxDownload\SwingTradingPlatform")

INPUT_FILE = PROJECT_ROOT / "data" / "raw" / "WABAG.NS.parquet"

OUTPUT_FILE = PROJECT_ROOT / "output" / "WABAG_1y_yf.csv"

# -----------------------------------------------------------------------------

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

df = pd.read_parquet(INPUT_FILE)

# Ensure Date is a column
if "Date" not in df.columns:
    df = df.reset_index()

# Sort by date
df = df.sort_values("Date").reset_index(drop=True)

# Remove timezone (CSV/Excel friendly)
df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)

# Keep only required columns
df = df[
    [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]
]

# Last one year (approximately 252 trading days)
df = df.tail(252)

# Export
df.to_csv(OUTPUT_FILE, index=False)

print("=" * 80)
print("Export Complete")
print("=" * 80)
print(f"Rows exported : {len(df)}")
print(f"Output file   : {OUTPUT_FILE}")