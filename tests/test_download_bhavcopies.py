from datetime import date

import pandas as pd

from tests.download_bhavcopies import _legacy_url, _parse_legacy, _parse_udiff, _udiff_url


def test_urls():
    assert _legacy_url(date(2019, 1, 1)).endswith("/EQUITIES/2019/JAN/cm01JAN2019bhav.csv.zip")
    assert _udiff_url(date(2024, 7, 8)).endswith("BhavCopy_NSE_CM_0_0_0_20240708_F_0000.csv.zip")


def test_parse_legacy():
    raw = pd.DataFrame({"SYMBOL": ["INFY "], "SERIES": ["EQ"], "OPEN": [1.0], "HIGH": [2.0], "LOW": [0.5],
                        "CLOSE": [1.5], "LAST": [1.5], "PREVCLOSE": [1.4], "TOTTRDQTY": [10], "TOTTRDVAL": [15.0],
                        "TIMESTAMP": ["01-JAN-2019"], "TOTALTRADES": [3], "ISIN": ["INE009A01021"], "Unnamed: 13": [None]})
    out = _parse_legacy(raw, date(2019, 1, 1))
    assert out.iloc[0].to_dict() == {"Date": pd.Timestamp("2019-01-01"), "Symbol": "INFY", "ISIN": "INE009A01021",
                                     "Series": "EQ", "Open": 1.0, "High": 2.0, "Low": 0.5, "Close": 1.5,
                                     "PrevClose": 1.4, "Volume": 10, "Turnover": 15.0}


def test_parse_udiff_keeps_stocks_only():
    raw = pd.DataFrame({"TradDt": ["2024-07-08"] * 2, "FinInstrmTp": ["STK", "IDX"], "ISIN": ["INE009A01021", None],
                        "TckrSymb": ["INFY", "NIFTY"], "SctySrs": ["EQ", "EQ"], "OpnPric": [1.0, 9.0],
                        "HghPric": [2.0, 9.0], "LwPric": [0.5, 9.0], "ClsPric": [1.5, 9.0], "PrvsClsgPric": [1.4, 9.0],
                        "TtlTradgVol": [10, 0], "TtlTrfVal": [15.0, 0.0]})
    out = _parse_udiff(raw, date(2024, 7, 8))
    assert list(out["Symbol"]) == ["INFY"] and out.iloc[0]["PrevClose"] == 1.4
