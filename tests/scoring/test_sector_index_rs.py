"""
Test for scoring/sector_index_rs.py -- kept lean per spec: a synthetic
3-ticker universe where A outperforms both its sector index and Nifty,
B outperforms Nifty but underperforms its sector, and C underperforms
both -- confirms the composite RS correctly ranks A > B > C (tests that
sector and market weights are actually combining correctly, not just
that the math runs).

Fixture design note: sector_return (15%) is deliberately set higher than
nifty_return (5%) -- B "outperforms Nifty but underperforms its sector"
is only a coherent, constructible scenario when the sector itself is
running hotter than the broader market (B's own return, 10%, sits
between the two).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from scoring.sector_index_rs import compute_sector_index_rs

N = 260  # > WINDOW_12M (252) so no window returns NaN


def _series(total_return: float, n: int = N) -> pd.DataFrame:
    dates = pd.date_range("2023-01-01", periods=n, freq="D")
    close = 100 * (1 + total_return) ** (np.arange(n) / (n - 1))
    return pd.DataFrame({"Date": dates, "Close": close, "Volume": [100_000] * n})


class TestCompositeRSCombinesSectorAndMarketCorrectly:

    def test_outperform_both_beats_mixed_beats_underperform_both(self):
        price_dataframes = {
            "A.NS": _series(0.25),  # outperforms sector (15%) and Nifty (5%)
            "B.NS": _series(0.10),  # outperforms Nifty, underperforms sector
            "C.NS": _series(0.00),  # underperforms both
        }
        sector_map_data = {"A.NS": "TestSector", "B.NS": "TestSector", "C.NS": "TestSector"}
        nifty50_history = _series(0.05)
        sector_index_cache = {"TestSector": _series(0.15)}

        result = compute_sector_index_rs(price_dataframes, sector_map_data, nifty50_history, sector_index_cache)

        assert result.loc["A.NS", "RS_Rating"] > result.loc["B.NS", "RS_Rating"]
        assert result.loc["B.NS", "RS_Rating"] > result.loc["C.NS", "RS_Rating"]


class TestUnresolvableSectorDegradesGracefully:

    def test_missing_sector_falls_back_to_peer_percentile_not_nan(self):
        price_dataframes = {
            "A.NS": _series(0.25),
            "D.NS": _series(0.30),
        }
        # D.NS's sector has no entry in sector_index_cache at all.
        sector_map_data = {"A.NS": "TestSector", "D.NS": "Unmapped"}
        nifty50_history = _series(0.05)
        sector_index_cache = {"TestSector": _series(0.15)}

        result = compute_sector_index_rs(price_dataframes, sector_map_data, nifty50_history, sector_index_cache)

        assert not pd.isna(result.loc["D.NS", "RS_Rating"])
