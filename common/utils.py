"""
Common utility functions for Swing Trading Platform
"""

import os
import pandas as pd
import yfinance as yf
from config import MASTER_FILE, DATA_FOLDER, DOWNLOAD_PERIOD, DOWNLOAD_INTERVAL, AUTO_ADJUST

os.makedirs(DATA_FOLDER, exist_ok=True)


def load_master(sheet_name=0):
    """Load the master workbook."""
    return pd.read_excel(MASTER_FILE, sheet_name=sheet_name)


def save_master(df, sheet_name="Screener"):
    """Overwrite workbook with a single sheet."""
    with pd.ExcelWriter(MASTER_FILE, engine="openpyxl", mode="w") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)


def ensure_symbol(symbol: str) -> str:
    """Ensure NSE symbols end with .NS"""
    symbol = str(symbol).strip().upper()
    if symbol.endswith(".NS"):
        return symbol
    return symbol + ".NS"


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten yfinance MultiIndex columns."""
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)
    return df


def download_history(symbol: str):
    """Download historical OHLCV."""
    symbol = ensure_symbol(symbol)
    data = yf.download(
        symbol,
        period=DOWNLOAD_PERIOD,
        interval=DOWNLOAD_INTERVAL,
        auto_adjust=AUTO_ADJUST,
        progress=False
    )
    if data.empty:
        return None

    data = flatten_columns(data).reset_index()
    return data


def save_csv(symbol: str, df: pd.DataFrame):
    """Save historical data to data folder."""
    filename = ensure_symbol(symbol).replace(".NS", "") + ".csv"
    path = os.path.join(DATA_FOLDER, filename)
    df.to_csv(path, index=False)
    return path


def read_csv(symbol: str):
    """Read stock CSV."""
    filename = ensure_symbol(symbol).replace(".NS", "") + ".csv"
    path = os.path.join(DATA_FOLDER, filename)
    if not os.path.exists(path):
        return None
    return pd.read_csv(path)


def clean_numeric(df: pd.DataFrame, columns):
    """Convert columns to numeric."""
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def percentage_change(current, previous):
    if previous in (0, None) or pd.isna(previous):
        return None
    return ((current - previous) / previous) * 100


def safe_round(value, digits=2):
    try:
        if pd.isna(value):
            return None
        return round(float(value), digits)
    except Exception:
        return None


def remove_columns(df, columns):
    existing = [c for c in columns if c in df.columns]
    if existing:
        df.drop(columns=existing, inplace=True)
    return df


def merge_results(master_df, result_df):
    """Merge results into Screener by Symbol."""
    return master_df.merge(result_df, on="Symbol", how="left")


# Internal-only signal strings (e.g. fundamental_analysis' "DATA_GAP", used
# when a required data row can't be located) that must never reach the UI
# as literal text.
SENTINEL_DISPLAY_MAP = {"DATA_GAP": "N/A", "N/A": "N/A"}


def sentinel_to_display(raw) -> str:
    """Maps internal-only sentinel strings to user-facing display text."""
    raw_str = str(raw)
    return SENTINEL_DISPLAY_MAP.get(raw_str, raw_str)
