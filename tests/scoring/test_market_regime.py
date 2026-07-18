"""
Tests for scoring/market_regime.py -- India VIX regime bucketing (A1) and
O'Neil-style distribution-day counting (A2). VIX column names/dtypes
confirmed via a live call to nselib's india_vix_data() (CLOSE_INDEX_VAL /
VIX_PERC_CHG are plain floats, no comma-cleaning needed).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

import scoring.market_regime as market_regime
from scoring.market_regime import count_distribution_days, get_current_vix


def _vix_response(level: float, change_pct: float = 1.0) -> pd.DataFrame:
    """Real shape confirmed live: TIMESTAMP + CLOSE_INDEX_VAL + VIX_PERC_CHG
    among others, both already numeric (float64)."""
    return pd.DataFrame({
        "TIMESTAMP": ["16-JUL-2026", "17-JUL-2026"],
        "INDEX_NAME": ["INDIA VIX", "INDIA VIX"],
        "OPEN_INDEX_VAL": [level - 0.5, level - 0.2],
        "CLOSE_INDEX_VAL": [level - 0.3, level],
        "HIGH_INDEX_VAL": [level + 0.5, level + 0.3],
        "LOW_INDEX_VAL": [level - 1.0, level - 0.5],
        "PREV_CLOSE": [level - 0.6, level - 0.3],
        "VIX_PTS_CHG": [0.3, level - (level - 0.3)],
        "VIX_PERC_CHG": [1.5, change_pct],
    })


@pytest.fixture
def isolated_vix_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(market_regime, "VIX_CACHE_PATH", tmp_path / "vix_test_cache.json")
    return tmp_path


class TestVixRegimeBoundaries:
    """Boundary conditions are the easiest place to get an off-by-one wrong:
    LOW (<15), NORMAL (15-20 inclusive), ELEVATED (>20)."""

    def test_14_9_is_low(self, isolated_vix_cache):
        with patch.object(market_regime.capital_market, "india_vix_data", return_value=_vix_response(14.9)):
            result = get_current_vix()
        assert result["regime"] == "LOW"

    def test_15_0_is_normal(self, isolated_vix_cache):
        with patch.object(market_regime.capital_market, "india_vix_data", return_value=_vix_response(15.0)):
            result = get_current_vix()
        assert result["regime"] == "NORMAL"

    def test_20_0_is_normal(self, isolated_vix_cache):
        with patch.object(market_regime.capital_market, "india_vix_data", return_value=_vix_response(20.0)):
            result = get_current_vix()
        assert result["regime"] == "NORMAL"

    def test_20_1_is_elevated(self, isolated_vix_cache):
        with patch.object(market_regime.capital_market, "india_vix_data", return_value=_vix_response(20.1)):
            result = get_current_vix()
        assert result["regime"] == "ELEVATED"


class TestVixResultShape:

    def test_returns_level_and_change_pct(self, isolated_vix_cache):
        with patch.object(market_regime.capital_market, "india_vix_data", return_value=_vix_response(13.15, 2.08)):
            result = get_current_vix()
        assert result["level"] == pytest.approx(13.15)
        assert result["change_pct"] == pytest.approx(2.08)


class TestVixCaching:

    def test_repeated_calls_within_refresh_window_do_not_refetch(self, isolated_vix_cache):
        with patch.object(market_regime.capital_market, "india_vix_data") as mock_fetch:
            mock_fetch.return_value = _vix_response(16.0)

            get_current_vix()
            get_current_vix()
            get_current_vix()

            assert mock_fetch.call_count == 1

    def test_stale_cache_triggers_refetch(self, isolated_vix_cache):
        with patch.object(market_regime.capital_market, "india_vix_data") as mock_fetch:
            mock_fetch.return_value = _vix_response(16.0)
            get_current_vix()

            import json
            with open(market_regime.VIX_CACHE_PATH, "r", encoding="utf-8") as fh:
                cached = json.load(fh)
            cached["fetched_at"] = (
                datetime.now() - timedelta(hours=market_regime.REFRESH_INTERVAL_HOURS + 1)
            ).isoformat()
            with open(market_regime.VIX_CACHE_PATH, "w", encoding="utf-8") as fh:
                json.dump(cached, fh)

            get_current_vix()

            assert mock_fetch.call_count == 2


class TestVixGracefulFallback:

    def test_fetch_exception_returns_none_not_crash(self, isolated_vix_cache):
        with patch.object(market_regime.capital_market, "india_vix_data") as mock_fetch:
            mock_fetch.side_effect = Exception("simulated network failure")
            assert get_current_vix() is None

    def test_empty_response_returns_none_not_crash(self, isolated_vix_cache):
        with patch.object(market_regime.capital_market, "india_vix_data") as mock_fetch:
            mock_fetch.return_value = pd.DataFrame()
            assert get_current_vix() is None


def _distribution_day_fixture() -> pd.DataFrame:
    """26 bars (lookback=25 + 1 for pct_change). Exactly 3 qualifying
    distribution days at indices 5, 12, 20 (down 1% on 1.5x volume). Two
    decoys: index 8 (down 1% but LOWER volume -- tests the AND condition)
    and index 16 (down only 0.1%, under threshold, but 2x volume -- tests
    the price-decline threshold matters too)."""
    closes = [100.0] * 26
    volumes = [100_000.0] * 26

    closes[5] = closes[4] * 0.99
    volumes[5] = volumes[4] * 1.5
    closes[12] = closes[11] * 0.99
    volumes[12] = volumes[11] * 1.5
    closes[20] = closes[19] * 0.99
    volumes[20] = volumes[19] * 1.5

    closes[8] = closes[7] * 0.99
    volumes[8] = volumes[7] * 0.5

    closes[16] = closes[15] * 0.999
    volumes[16] = volumes[15] * 2.0

    return pd.DataFrame({"Close": closes, "Volume": volumes})


class TestDistributionDayCount:

    def test_counts_exactly_the_known_qualifying_days(self):
        count = count_distribution_days(_distribution_day_fixture(), lookback=25)
        assert count == 3, (
            f"Expected exactly 3 distribution days (hand-built at known "
            f"indices), got {count}. A decoy down-day-on-low-volume or "
            f"small-decline-on-high-volume incorrectly counting would "
            f"produce 4 or 5 here."
        )

    def test_volume_condition_alone_is_not_sufficient(self):
        """Regression guard for the AND logic specifically: a down day on
        merely-not-lower volume (equal, not strictly higher) must not count."""
        closes = [100.0, 99.0]
        volumes = [100_000.0, 100_000.0]  # equal, not higher
        df = pd.DataFrame({"Close": closes, "Volume": volumes})
        assert count_distribution_days(df, lookback=1) == 0

    def test_missing_columns_returns_none_not_crash(self):
        df = pd.DataFrame({"Close": [100.0, 99.0]})  # no Volume
        assert count_distribution_days(df) is None

    def test_empty_dataframe_returns_none_not_crash(self):
        assert count_distribution_days(pd.DataFrame()) is None
