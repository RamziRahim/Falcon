"""
Tests for backtesting/backtest_runner.py -- kept lean per spec.
"""
from __future__ import annotations

import pytest

from backtesting.backtest_runner import compute_expectancy, populate_sector_cache


class TestExpectancyFormula:

    def test_hand_computed_win_loss_produces_exact_expected_number(self):
        # win_rate=0.6, avg_win=+8.0%, loss_rate=0.4, avg_loss=-3.0%
        # Expectancy = (0.6 * 8.0) + (0.4 * -3.0) = 4.8 - 1.2 = 3.6
        expectancy = compute_expectancy(
            win_rate=0.6, avg_win_pct=8.0, loss_rate=0.4, avg_loss_pct=-3.0
        )

        assert expectancy == pytest.approx(3.6)


@pytest.fixture
def isolated_backtest_sector_map(monkeypatch, tmp_path):
    """A SectorMap instance pointed at temp override/cache files instead of
    the real project paths (same isolation as tests/scoring/conftest.py's
    isolated_sector_map, duplicated here since fixtures aren't shared
    across tests/ subdirectories without a root conftest.py), patched in
    as backtesting.backtest_runner's module-level sector_map so
    populate_sector_cache() itself is what's under test."""
    import scoring.sector_map as sm
    import backtesting.backtest_runner as backtest_runner

    monkeypatch.setattr(sm, "OVERRIDES_PATH", tmp_path / "no_overrides.csv")
    monkeypatch.setattr(sm, "SECTOR_MAP_PATH", tmp_path / "sector_map_test_cache.json")
    instance = sm.SectorMap()
    monkeypatch.setattr(backtest_runner, "sector_map", instance)
    return instance


@pytest.mark.integration
class TestPopulateSectorCacheRealYahooIntegration:
    """Hits the real yfinance API. Run explicitly with: pytest -m integration"""

    def test_five_known_nifty50_tickers_resolve_to_non_unknown_sectors(self, isolated_backtest_sector_map):
        known_tickers = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]

        populate_sector_cache(known_tickers)

        for ticker in known_tickers:
            sector = isolated_backtest_sector_map.get_sector(ticker)
            assert sector != "Unknown", f"{ticker} should resolve to a real sector, got Unknown"
