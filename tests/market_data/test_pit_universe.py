import numpy as np
import pandas as pd
import pytest

from market_data.pit_universe import (
    adjust_entity, build_adjusted_prices, last_trading_dates, link_entities, monthly_universe, primary_rows,
)

DATES = pd.bdate_range("2020-01-01", periods=300)


def _rows(symbol, isin, closes, dates=None, series="EQ", turnover=1e7, prev=None):
    dates = DATES[: len(closes)] if dates is None else dates
    closes = np.asarray(closes, dtype=float)
    prev = np.r_[closes[0], closes[:-1]] if prev is None else np.asarray(prev, dtype=float)
    return pd.DataFrame({"Date": dates, "Symbol": symbol, "ISIN": isin, "Series": series, "Open": closes,
                         "High": closes, "Low": closes, "Close": closes, "PrevClose": prev,
                         "Volume": 1000.0, "Turnover": turnover})


def test_rename_and_isin_change_are_one_entity():
    a = _rows("OLDNAME", "INE1", [10] * 5, DATES[:5])
    b = _rows("NEWNAME", "INE1", [10] * 5, DATES[5:10])        # rename, same ISIN
    c = _rows("NEWNAME", "INE2", [10] * 5, DATES[10:15])       # split -> new ISIN, same symbol
    d = _rows("OTHER", "INE9", [10] * 15)
    ids = link_entities(pd.concat([a, b, c, d], ignore_index=True))
    assert ids.iloc[:15].nunique() == 1 and ids.iloc[15:].nunique() == 1 and ids.iloc[0] != ids.iloc[15]


def test_split_is_adjusted_from_nse_prevclose():
    # 2:1 split on day 3: close drops 100 -> 50, NSE's PrevClose that day says 50
    rows = _rows("X", "I", [100, 102, 51, 52], prev=[100, 100, 51, 51])
    adjusted, events = adjust_entity(rows)
    assert [e["factor"] for e in events] == pytest.approx([0.5])
    assert adjusted["Close"].tolist() == pytest.approx([50, 51, 51, 52])
    assert adjusted["Volume"].tolist() == pytest.approx([2000, 2000, 1000, 1000])


def test_rounding_noise_is_not_an_adjustment():
    rows = _rows("X", "I", [100, 101], prev=[100, 100.05])
    _, events = adjust_entity(rows)
    assert events == []


def test_primary_series_prefers_eq():
    eq = _rows("X", "I", [10, 11], series="EQ", turnover=1.0)
    be = _rows("X", "I", [10.5, 11.5], series="BE", turnover=9.0)
    out = primary_rows(pd.concat([be, eq], ignore_index=True))
    assert (out["Series"] == "EQ").all() and len(out) == 2


def test_monthly_universe_is_point_in_time_and_keeps_later_delisted_stocks():
    big_then_gone = _rows("GONE", "I1", [10] * 200, turnover=5e8)       # stops trading after day 200
    steady = _rows("STEADY", "I2", [10] * 300, turnover=1e8)
    small = _rows("SMALL", "I3", [10] * 300, turnover=1e6)
    illiquid = _rows("ILLIQ", "I4", [10] * 300, turnover=9e9).iloc[::3]   # active 1/3 of days
    prices, _ = build_adjusted_prices(pd.concat([big_then_gone, steady, small, illiquid], ignore_index=True))
    uni = monthly_universe(prices, size=2, lookback=126)
    first = uni[uni["month_end"] == uni["month_end"].min()]
    assert list(first["symbol_then"]) == ["GONE", "STEADY"]           # ILLIQ fails the activity rule
    last = uni[uni["month_end"] == uni["month_end"].max()]
    assert "GONE" not in set(last["symbol_then"])                    # not ranked after it stopped trading
    assert last_trading_dates(prices).max() == DATES[299]


def test_universe_never_uses_future_turnover():
    early = _rows("A", "I1", [10] * 300, turnover=1e8)
    late_spike = _rows("B", "I2", [10] * 300, turnover=np.r_[np.full(200, 1e6), np.full(100, 1e10)])
    prices, _ = build_adjusted_prices(pd.concat([early, late_spike], ignore_index=True))
    uni = monthly_universe(prices, size=1, lookback=126)
    first_month = uni["month_end"].min()
    assert uni.loc[uni["month_end"] == first_month, "symbol_then"].tolist() == ["A"]
