from pathlib import Path

import pandas as pd

# =============================================================================
# Configuration
# =============================================================================

PROJECT_ROOT = Path(r"C:\TeraBoxDownload\SwingTradingPlatform")

INPUT_FILE = PROJECT_ROOT / "data" / "technical" / "WABAG.NS.parquet"

OUTPUT_FILE = (
    PROJECT_ROOT
    / "output"
    / "WABAG_1Y_YF_TECHNICAL.xlsx"
)

# =============================================================================

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

# Read parquet
df = pd.read_parquet(INPUT_FILE)

# Ensure Date is a column
if "Date" not in df.columns:
    df = df.reset_index()

# Sort by Date
df = df.sort_values("Date").reset_index(drop=True)

# Remove timezone (Excel doesn't support timezone-aware datetimes)
df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)

# Keep last one year (~252 trading days)
df = df.tail(252)

# Export to Excel
with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
    df.to_excel(writer, sheet_name="Technical", index=False)

    ws = writer.sheets["Technical"]

    # Freeze header
    ws.freeze_panes = "A2"

    # Enable filters
    ws.auto_filter.ref = ws.dimensions

    # Auto-fit columns
    for column_cells in ws.columns:
        length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = min(length + 3, 30)

print("=" * 80)
print("Export Complete")
print("=" * 80)
print(f"Rows exported : {len(df)}")
print(f"Output file   : {OUTPUT_FILE}")