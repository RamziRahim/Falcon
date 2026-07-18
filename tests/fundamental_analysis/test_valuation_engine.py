"""
Tests for fundamental_analysis/valuation_engine.py -- market-wide P/E
snapshot (cached per trade_date) and per-ticker relative-valuation
bucketing. pe_ratio()'s real column shape (['SYMBOL', 'SYMBOLP/E',
'ADJUSTEDP/E'], no docstring/constants entry existed beforehand) was
confirmed via a live call before writing any parsing logic.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

import fundamental_analysis.valuation_engine as valuation_engine
from fundamental_analysis.valuation_engine import get_market_pe_snapshot, get_relative_valuation


def _pe_response() -> pd.DataFrame:
    """Real shape confirmed live."""
    return pd.DataFrame({
        "SYMBOL": ["THERMAX", "WHEELS", "RIIL"],
        "SYMBOLP/E": [77.08, 24.05, 113.78],
        "ADJUSTEDP/E": [82.00, 24.05, 113.78],
    })


@pytest.fixture
def isolated_pe_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(valuation_engine, "PE_CACHE_DIR", tmp_path / "pe_cache")
    return tmp_path


class TestGetMarketPeSnapshot:

    def test_fetches_and_cleans_snapshot(self, isolated_pe_cache):
        with patch.object(valuation_engine.capital_market, "pe_ratio", return_value=_pe_response()):
            df = get_market_pe_snapshot(trade_date="17-07-2026")

        assert list(df.columns) == ["Symbol", "PE", "Adjusted_PE"]
        assert df.loc[df["Symbol"] == "THERMAX", "PE"].iloc[0] == pytest.approx(77.08)

    def test_repeated_calls_same_date_do_not_refetch(self, isolated_pe_cache):
        with patch.object(valuation_engine.capital_market, "pe_ratio") as mock_fetch:
            mock_fetch.return_value = _pe_response()

            get_market_pe_snapshot(trade_date="17-07-2026")
            get_market_pe_snapshot(trade_date="17-07-2026")
            get_market_pe_snapshot(trade_date="17-07-2026")

            assert mock_fetch.call_count == 1

    def test_different_dates_cached_separately(self, isolated_pe_cache):
        """Analogous to sector_map.py's staleness -> refetch behavior, but
        keyed by date rather than elapsed time: PE snapshots for a past
        date are immutable once fetched, so a *new* date always triggers
        its own fresh fetch regardless of how recently the last one ran."""
        with patch.object(valuation_engine.capital_market, "pe_ratio") as mock_fetch:
            mock_fetch.return_value = _pe_response()

            get_market_pe_snapshot(trade_date="16-07-2026")
            get_market_pe_snapshot(trade_date="17-07-2026")

            assert mock_fetch.call_count == 2

    def test_retries_backward_on_empty_response(self, isolated_pe_cache):
        """Simulates calling with no explicit trade_date on a Monday --
        'today' (Sunday, say) has no data, must fall back to the prior
        trading day."""
        call_dates = []

        def fake_pe_ratio(trade_date):
            call_dates.append(trade_date)
            if len(call_dates) == 1:
                return pd.DataFrame(columns=["SYMBOL", "SYMBOLP/E", "ADJUSTEDP/E"])
            return _pe_response()

        with patch.object(valuation_engine.capital_market, "pe_ratio", side_effect=fake_pe_ratio):
            df = get_market_pe_snapshot()

        assert len(call_dates) == 2
        assert not df.empty

    def test_all_attempts_fail_returns_empty_df_not_crash(self, isolated_pe_cache):
        with patch.object(valuation_engine.capital_market, "pe_ratio", side_effect=Exception("no data")):
            df = get_market_pe_snapshot()

        assert df.empty
        assert list(df.columns) == ["Symbol", "PE", "Adjusted_PE"]


def _snapshot_with_sector(pe_values: dict[str, float], sectors: dict[str, str]) -> pd.DataFrame:
    symbols = list(pe_values.keys())
    return pd.DataFrame({
        "Symbol": symbols,
        "PE": [pe_values[s] for s in symbols],
        "Adjusted_PE": [pe_values[s] for s in symbols],
        "Sector": [sectors[s] for s in symbols],
    })


class TestRelativeValuationBucketing:

    def test_sector_average_excludes_ticker_itself(self):
        snapshot = _snapshot_with_sector(
            {"TARGET": 200.0, "PEER_A": 100.0, "PEER_B": 100.0, "OTHER_SECTOR": 500.0},
            {"TARGET": "Tech", "PEER_A": "Tech", "PEER_B": "Tech", "OTHER_SECTOR": "Finance"},
        )
        result = get_relative_valuation("TARGET", "Tech", snapshot)
        assert result["sector_avg_pe"] == pytest.approx(100.0), (
            "Sector average must be computed from peers only (100, 100) -- "
            "including TARGET's own 200 would pull the average up and "
            "understate how expensive it really is."
        )

    def test_exactly_20_percent_above_is_fair_not_expensive(self):
        snapshot = _snapshot_with_sector(
            {"TARGET": 120.0, "PEER": 100.0}, {"TARGET": "Tech", "PEER": "Tech"},
        )
        result = get_relative_valuation("TARGET", "Tech", snapshot)
        assert result["relative"] == "FAIR"

    def test_just_over_20_percent_above_is_expensive(self):
        snapshot = _snapshot_with_sector(
            {"TARGET": 120.01, "PEER": 100.0}, {"TARGET": "Tech", "PEER": "Tech"},
        )
        result = get_relative_valuation("TARGET", "Tech", snapshot)
        assert result["relative"] == "EXPENSIVE"

    def test_exactly_20_percent_below_is_fair_not_cheap(self):
        snapshot = _snapshot_with_sector(
            {"TARGET": 80.0, "PEER": 100.0}, {"TARGET": "Tech", "PEER": "Tech"},
        )
        result = get_relative_valuation("TARGET", "Tech", snapshot)
        assert result["relative"] == "FAIR"

    def test_just_under_20_percent_below_is_cheap(self):
        snapshot = _snapshot_with_sector(
            {"TARGET": 79.99, "PEER": 100.0}, {"TARGET": "Tech", "PEER": "Tech"},
        )
        result = get_relative_valuation("TARGET", "Tech", snapshot)
        assert result["relative"] == "CHEAP"


class TestGracefulFallback:

    def test_missing_ticker_returns_unknown_not_crash(self):
        snapshot = _snapshot_with_sector({"OTHER": 100.0}, {"OTHER": "Tech"})
        result = get_relative_valuation("NOT_IN_SNAPSHOT", "Tech", snapshot)
        assert result == {"pe": None, "sector_avg_pe": None, "relative": "UNKNOWN"}

    def test_missing_sector_column_returns_pe_but_unknown_relative(self):
        snapshot = pd.DataFrame({"Symbol": ["TARGET"], "PE": [50.0]})
        result = get_relative_valuation("TARGET", "Tech", snapshot)
        assert result["pe"] == 50.0
        assert result["relative"] == "UNKNOWN"

    def test_no_sector_peers_returns_pe_but_unknown_relative(self):
        snapshot = _snapshot_with_sector({"TARGET": 100.0}, {"TARGET": "Tech"})
        result = get_relative_valuation("TARGET", "Tech", snapshot)
        assert result["pe"] == 100.0
        assert result["relative"] == "UNKNOWN"

    def test_nan_pe_for_ticker_returns_unknown(self):
        snapshot = pd.DataFrame({"Symbol": ["TARGET"], "PE": [float("nan")], "Sector": ["Tech"]})
        result = get_relative_valuation("TARGET", "Tech", snapshot)
        assert result["pe"] is None
        assert result["relative"] == "UNKNOWN"

    def test_empty_snapshot_returns_unknown_not_crash(self):
        result = get_relative_valuation("TARGET", "Tech", pd.DataFrame())
        assert result["relative"] == "UNKNOWN"

    def test_ticker_ns_suffix_normalized(self):
        snapshot = _snapshot_with_sector(
            {"TARGET": 100.0, "PEER": 80.0}, {"TARGET": "Tech", "PEER": "Tech"},
        )
        result = get_relative_valuation("TARGET.NS", "Tech", snapshot)
        assert result["pe"] == 100.0
