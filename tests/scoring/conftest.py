"""
Shared fixtures for scoring/ engine tests.

Corrected 2026-07-15 to match the ACTUAL interfaces built (function names,
class-based sector_map, real config constants) rather than the interface
assumed before implementation existed. Verified against the real
implementation before being committed as the regression suite.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def synthetic_returns_series() -> pd.Series:
    """5-ticker series with unambiguous, strictly-ordered returns."""
    return pd.Series({
        "TICKER_A": -0.10,
        "TICKER_B": 0.00,
        "TICKER_C": 0.05,
        "TICKER_D": 0.15,
        "TICKER_E": 0.30,
    })


def _price_frame(prices: np.ndarray, volume: int = 100_000) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=len(prices), freq="D")
    return pd.DataFrame({"Date": dates, "Close": prices, "Volume": volume})


@pytest.fixture
def synthetic_multi_ticker_history() -> dict[str, pd.DataFrame]:
    """
    Three tickers, 400 daily bars each, with deliberately different
    recent-vs-older performance profiles — tests that the composite
    RS Rating actually reflects recency weighting (0.4/0.2/0.2/0.2 on
    3M/6M/9M/12M per scoring/relative_strength.py), not just total return.
    """
    n_days = 400
    flat_then_rally = np.concatenate([np.full(300, 100.0), np.linspace(100, 160, 100)])
    steady = np.linspace(100, 140, n_days)
    rally_then_drop = np.concatenate([np.linspace(100, 180, 300), np.linspace(180, 140, 100)])

    return {
        "RECENT_WINNER": _price_frame(flat_then_rally),
        "STEADY_CLIMBER": _price_frame(steady),
        "RECENT_LOSER": _price_frame(rally_then_drop),
    }


@pytest.fixture
def synthetic_short_and_long_history() -> dict[str, pd.DataFrame]:
    """One ticker with insufficient history for a 12M window, one with plenty."""
    return {
        "SHORT": _price_frame(np.linspace(100, 110, 100)),   # < WINDOW_12M (252)
        "LONG": _price_frame(np.linspace(100, 110, 300)),
    }


@pytest.fixture
def synthetic_ohlcv_steady_volume() -> pd.DataFrame:
    """30 days of constant 100_000 volume. Rel_Vol should be ~1.0 throughout."""
    dates = pd.date_range("2026-01-01", periods=30, freq="D")
    return pd.DataFrame({
        "Date": dates, "Open": 100, "High": 101, "Low": 99, "Close": 100,
        "Volume": [100_000] * 30,
    })


@pytest.fixture
def synthetic_ohlcv_volume_spike() -> pd.DataFrame:
    """29 days of steady volume, then a 10x spike on the last day."""
    dates = pd.date_range("2026-01-01", periods=30, freq="D")
    return pd.DataFrame({
        "Date": dates, "Open": 100, "High": 101, "Low": 99, "Close": 100,
        "Volume": [100_000] * 29 + [1_000_000],
    })


@pytest.fixture
def sector_overrides_csv(tmp_path):
    """Temp sector_overrides.csv for testing manual-override precedence."""
    path = tmp_path / "sector_overrides.csv"
    path.write_text("Symbol,Sector\nOVERRIDDEN.NS,Defence\n")
    return path


@pytest.fixture
def isolated_sector_map(monkeypatch, sector_overrides_csv, tmp_path):
    """
    A SectorMap instance pointed at temp override/cache files instead of
    the real project paths, so tests never touch real data/sector_map.json.
    """
    import scoring.sector_map as sm

    monkeypatch.setattr(sm, "OVERRIDES_PATH", sector_overrides_csv)
    monkeypatch.setattr(sm, "SECTOR_MAP_PATH", tmp_path / "sector_map_test_cache.json")
    return sm.SectorMap()
