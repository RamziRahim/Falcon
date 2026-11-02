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


def test_split_is_adjusted_from_corporate_action_record():
    # 2:1 split ex day 3: close drops 100 -> 51
    rows = _rows("X", "I", [100, 102, 51, 52])
    actions = pd.DataFrame({"exDate": [DATES[2]], "factor": [0.5], "subject": ["split"]})
    adjusted, events = adjust_entity(rows, actions)
    assert [e["factor"] for e in events] == pytest.approx([0.5]) and not events[0]["suspect"]
    assert adjusted["Close"].tolist() == pytest.approx([50, 51, 51, 52])
    assert adjusted["Volume"].tolist() == pytest.approx([2000, 2000, 1000, 1000])


@pytest.mark.parametrize("subject,factor", [
    ("Bonus 1:1", 0.5), ("Bonus 4:1", 0.2), ("Bonus 1:4", 0.8), ("Bonus 17:25", 25 / 42),
    ("Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share", 0.2),
    ("Face Value Split (Sub-Division) - From Rs 5/- Per Share To Re 1/- Per Share", 0.2),
    ("Bonus 1:1/Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share", 0.1),
    ("Bonus 2:1/Dividend- Rs 1.60 Per Share", 1 / 3),
    ("Fv Split Rs.10/- To Re.2/", 0.2), ("Fv Split Rs.2/- To Re.1/-", 0.5),
    ("Face Value Split From Rs.10/- To Rs.6/-", 0.6),
    ("Bonus Ncrps 1:116", None),
    ("Dividend - Rs 5 Per Share", None),
])
def test_parse_factor(subject, factor):
    from market_data.pit_universe import parse_factor
    assert parse_factor(subject) == (pytest.approx(factor) if factor is not None else None)


def test_build_matches_action_by_symbol():
    bhav = _rows("X", "I", [100, 102, 51, 52])
    actions = pd.DataFrame({"symbol": ["X"], "isin": ["I"], "exDate": [DATES[2]], "subject": ["Bonus 1:1"]})
    prices, log = build_adjusted_prices(bhav, actions)
    assert prices["Close"].tolist() == pytest.approx([50, 51, 51, 52]) and len(log) == 1


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


def test_demerger_uses_the_ex_date_drop_and_bonus_plus_split_combine():
    from market_data.pit_universe import parse_factor, DEMERGER
    assert parse_factor("Demerger") == DEMERGER
    rows = _rows("X", "I", [100, 100, 70, 71])
    rows.loc[2, "Open"] = 70.0
    adjusted, events = adjust_entity(rows, pd.DataFrame({"exDate": [DATES[2]], "factor": [DEMERGER], "subject": ["Demerger"]}))
    assert adjusted["Close"].tolist() == pytest.approx([70, 70, 70, 71])
    combo = pd.DataFrame({"exDate": [DATES[2]] * 2, "factor": [0.5, 0.1], "subject": ["Bonus 1:1", "split"]})
    rows2 = _rows("Y", "J", [100, 100, 5.1, 5.2])
    adjusted2, events2 = adjust_entity(rows2, combo)
    assert len(events2) == 1 and events2[0]["factor"] == pytest.approx(0.05) and not events2[0]["suspect"]


def test_symbol_change_links_pre_isin_rename():
    a = _rows("OLDCO", None, [10] * 5, DATES[:5])
    b = _rows("NEWCO", None, [10] * 5, DATES[5:10])
    bhav = pd.concat([a, b], ignore_index=True)
    assert link_entities(bhav).nunique() == 2
    assert link_entities(bhav, [("OLDCO", "NEWCO")]).nunique() == 1
