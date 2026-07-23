
"""
Falcon AI - OHLCV Validation Tool

Validates locally cached Parquet OHLCV files against Yahoo Finance.

Requirements:
    pip install pandas pyarrow yfinance numpy
"""

from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

RAW_DATA_DIR = Path(r"C:\TeraBoxDownload\SwingTradingPlatform\data\raw")

PRICE_COLUMNS = [
    "Open",
    "High",
    "Low",
    "Close",
    "Adj Close",
]

FLOAT_TOLERANCE = 0.01


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def normalize_dates(df: pd.DataFrame) -> pd.DataFrame:
    d = pd.to_datetime(df["Date"])
    try:
        if d.dt.tz is not None:
            d = d.dt.tz_localize(None)
    except Exception:
        pass

    df["Date"] = d.dt.normalize()
    return df


def load_cache(file: Path) -> pd.DataFrame:
    df = pd.read_parquet(file)

    if "Date" not in df.columns:
        df = df.reset_index()

    df = normalize_dates(df)

    required = [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Adj Close",
        "Volume",
    ]

    return (
        df[required]
        .sort_values("Date")
        .reset_index(drop=True)
    )


def download_yahoo(symbol: str, start, end) -> pd.DataFrame:

    df = yf.download(
        symbol,
        start=start,
        end=end + pd.Timedelta(days=1),
        auto_adjust=False,
        progress=False,
    )

    if df.empty:
        raise RuntimeError("Yahoo returned no data.")

    df = df.reset_index()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = normalize_dates(df)

    required = [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Adj Close",
        "Volume",
    ]

    return (
        df[required]
        .sort_values("Date")
        .reset_index(drop=True)
    )


def compare_symbol(cache_df, yahoo_df):

    merged = cache_df.merge(
        yahoo_df,
        on="Date",
        how="outer",
        suffixes=("_CACHE", "_YAHOO"),
        indicator=True,
    )

    errors = []

    left_only = merged[merged["_merge"] == "left_only"]
    right_only = merged[merged["_merge"] == "right_only"]

    if not left_only.empty:
        errors.append(f"Missing in Yahoo : {len(left_only)} rows")

    if not right_only.empty:
        errors.append(f"Missing in Cache : {len(right_only)} rows")

    both = merged[merged["_merge"] == "both"].copy()

    for col in PRICE_COLUMNS:

        mask = ~np.isclose(
            both[f"{col}_CACHE"],
            both[f"{col}_YAHOO"],
            atol=FLOAT_TOLERANCE,
            rtol=0,
            equal_nan=True,
        )

        diff = both.loc[mask]

        if not diff.empty:
            errors.append(f"{col}: {len(diff)} mismatch(es)")
            print("\n", "=" * 80)
            print(col)
            print("=" * 80)
            print(
                diff[
                    [
                        "Date",
                        f"{col}_CACHE",
                        f"{col}_YAHOO",
                    ]
                ].tail(10)
            )

    vol = both[both["Volume_CACHE"] != both["Volume_YAHOO"]]

    if not vol.empty:
        errors.append(f"Volume: {len(vol)} mismatch(es)")
        print("\n", "=" * 80)
        print("Volume")
        print("=" * 80)
        print(
            vol[
                [
                    "Date",
                    "Volume_CACHE",
                    "Volume_YAHOO",
                ]
            ].tail(10)
        )

    return errors


def validate_file(file: Path):

    symbol = file.stem

    print("\n" + "=" * 100)
    print(symbol)
    print("=" * 100)

    cache = load_cache(file)

    yahoo = download_yahoo(
        symbol,
        cache["Date"].min(),
        cache["Date"].max(),
    )

    print(f"Cache Rows : {len(cache)}")
    print(f"Yahoo Rows : {len(yahoo)}")

    errors = compare_symbol(cache, yahoo)

    if errors:
        print("\nFAILED")
        for e in errors:
            print(" -", e)
    else:
        print("\nPASS")

    return symbol, errors


def main():

    files = sorted(RAW_DATA_DIR.glob("*.parquet"))

    if not files:
        print("No parquet files found.")
        return

    results = []

    for file in files:
        try:
            results.append(validate_file(file))
        except Exception as ex:
            print(f"\nERROR processing {file.name}: {ex}")
            results.append((file.stem, [str(ex)]))

    report = pd.DataFrame(
        {
            "Symbol": [r[0] for r in results],
            "Status": [
                "PASS" if len(r[1]) == 0 else "FAIL"
                for r in results
            ],
            "Issues": [
                "; ".join(r[1]) if r[1] else ""
                for r in results
            ],
        }
    )

    report.to_csv("ohlcv_validation_report.csv", index=False)

    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(report)

    print("\nCSV report written to:")
    print(Path("ohlcv_validation_report.csv").resolve())


if __name__ == "__main__":
    main()
