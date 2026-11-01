"""
The vectorised FVGDetector.detect_fvgs() must return exactly what the
original per-bar loop returned. The original is kept here verbatim
(as a function) as the reference.
"""
import numpy as np
import pandas as pd
import pytest

from technical_analysis.pattern_system.fvg_detector import FVGDetector


def _reference_detect_fvgs(df):
    """
    Scans daily price logs to isolate active, unmitigated Bullish FVGs.
    Formula: Candle_1_High < Candle_3_Low
    """
    df = df.sort_values(by="Date", ascending=True).reset_index(drop=True)
    df_len = len(df)
    
    results = {
        "has_active_fvg": False,
        "fvg_top": None,
        "fvg_bottom": None,
        "is_price_in_fvg": False
    }

    if df_len < 3:
        return results

    active_fvgs = []

    # 1. Rolling 3-candle structural scans across history
    for i in range(1, df_len - 1):
        c1_high = df.loc[i - 1, "High"]
        c3_low = df.loc[i + 1, "Low"]

        # Check if an imbalance exists
        if c3_low > c1_high:
            active_fvgs.append({
                "top": float(c3_low),
                "bottom": float(c1_high),
                "index": i
            })

    if not active_fvgs:
        return results

    # 2. Mitigation Filter: Verify if subsequent price action filled the gap
    latest_close = df["Close"].iloc[-1]
    valid_fvg = None

    # Suffix-min of Low, so "did any candle after index j dip to/below X"
    # is an O(1) lookup instead of an O(n) inner scan per FVG.
    suffix_min_low = df["Low"].iloc[::-1].cummin().iloc[::-1]

    # Check from the most recent FVG backward
    for fvg in reversed(active_fvgs):
        fvg_index = fvg["index"]
        scan_start = fvg_index + 2

        mitigated = (
            scan_start < df_len
            and suffix_min_low.iloc[scan_start] <= fvg["bottom"]
        )

        if not mitigated:
            valid_fvg = fvg
            break

    if valid_fvg:
        results["has_active_fvg"] = True
        results["fvg_top"] = valid_fvg["top"]
        results["fvg_bottom"] = valid_fvg["bottom"]
        
        # Check if current closing price is resting safely inside the gap boundary
        if valid_fvg["bottom"] <= latest_close <= valid_fvg["top"]:
            results["is_price_in_fvg"] = True

    return results


def _frame(n, seed, gappy=False, nans=False, shuffle=False):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0.3 if gappy else 0, 3 if gappy else 1, n))
    high = close + rng.uniform(0, 1, n)
    low = close - rng.uniform(0, 1, n)
    df = pd.DataFrame({"Date": pd.bdate_range("2023-01-02", periods=n), "High": high, "Low": low, "Close": close})
    if nans and n > 0:
        df.loc[rng.choice(n, size=max(1, n // 15), replace=False), "Low"] = np.nan
        df.loc[rng.choice(n, size=max(1, n // 15), replace=False), "High"] = np.nan
    if shuffle:
        df = df.sample(frac=1, random_state=seed)
    return df


@pytest.mark.parametrize("n", [0, 2, 3, 4, 30, 500])
@pytest.mark.parametrize("variant", ["plain", "gappy", "nans", "shuffle"])
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_matches_original_loop(n, variant, seed):
    df = _frame(n, seed, gappy=variant == "gappy", nans=variant == "nans", shuffle=variant == "shuffle")
    assert FVGDetector().detect_fvgs(df) == _reference_detect_fvgs(df)
