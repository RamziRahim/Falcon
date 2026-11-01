"""
The vectorised SwingDetector.detect_swings() must return exactly what the
original per-bar loop returned (it feeds every pattern detector, the
market regime and sector trend, so any drift would silently change every
backtest). The original loop is kept here verbatim as the reference.
"""
import numpy as np
import pandas as pd
import pytest

from technical_analysis.pattern_system.models import SwingPoint
from technical_analysis.pattern_system.swing_detector import SwingDetector


def _reference_detect_swings(window, df):
    swing_points = []
    df_len = len(df)
    df = df.sort_values(by="Date", ascending=True).reset_index(drop=True)
    last_high_price = None
    last_low_price = None
    for i in range(window, df_len - window):
        current_high = df.loc[i, "High"]
        current_low = df.loc[i, "Low"]
        current_date = str(df.loc[i, "Date"])
        is_high = True
        for r in range(1, window + 1):
            if df.loc[i - r, "High"] > current_high or df.loc[i + r, "High"] > current_high:
                is_high = False
                break
        if is_high:
            is_higher = True if last_high_price is None else current_high > last_high_price
            last_high_price = current_high
            swing_points.append(SwingPoint(index=i, date=current_date, price=float(current_high), type="HIGH", is_higher=is_higher))
            continue
        is_low = True
        for r in range(1, window + 1):
            if df.loc[i - r, "Low"] < current_low or df.loc[i + r, "Low"] < current_low:
                is_low = False
                break
        if is_low:
            is_higher = True if last_low_price is None else current_low > last_low_price
            last_low_price = current_low
            swing_points.append(SwingPoint(index=i, date=current_date, price=float(current_low), type="LOW", is_higher=is_higher))
    return swing_points


def _same(a, b):
    assert len(a) == len(b)
    for x, y in zip(a, b):
        assert (x.index, x.date, x.type, bool(x.is_higher)) == (y.index, y.date, y.type, bool(y.is_higher))
        assert (x.price == y.price) or (np.isnan(x.price) and np.isnan(y.price))
        assert type(x.is_higher) is type(y.is_higher)


def _frame(n, seed, ties=False, nans=False, shuffle=False, int_prices=False):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    high = close + rng.uniform(0, 2, n)
    low = close - rng.uniform(0, 2, n)
    if ties:
        high, low = np.round(high), np.round(low)      # many exact ties
    if int_prices:
        high, low = high.round().astype(int), low.round().astype(int)
    df = pd.DataFrame({"Date": pd.bdate_range("2023-01-02", periods=n), "High": high, "Low": low, "Close": close})
    if nans and n > 0:
        df.loc[rng.choice(n, size=max(1, n // 20), replace=False), "High"] = np.nan
        df.loc[rng.choice(n, size=max(1, n // 20), replace=False), "Low"] = np.nan
    if shuffle:
        df = df.sample(frac=1, random_state=seed)
    return df


@pytest.mark.parametrize("window", [1, 2, 3, 5])
@pytest.mark.parametrize("n", [0, 3, 10, 11, 12, 60, 400])
@pytest.mark.parametrize("variant", ["plain", "ties", "nans", "shuffle", "int"])
def test_matches_original_loop(window, n, variant):
    df = _frame(n, seed=n * 7 + window, ties=variant == "ties", nans=variant == "nans",
                shuffle=variant == "shuffle", int_prices=variant == "int")
    _same(SwingDetector(window).detect_swings(df), _reference_detect_swings(window, df))


def test_flat_series_all_ties():
    df = pd.DataFrame({"Date": pd.bdate_range("2024-01-01", periods=40), "High": 10.0, "Low": 9.0})
    _same(SwingDetector(5).detect_swings(df), _reference_detect_swings(5, df))
