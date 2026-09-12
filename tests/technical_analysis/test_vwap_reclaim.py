"""
Tests for technical_analysis/vwap_reclaim.py -- synthetic 1-minute bar
fixtures chosen so the cumulative VWAP is easy to hand-verify: High=Low=
Close (typical price == close) and constant per-bar volume, so VWAP at
bar t is simply the running mean of closes 1..t.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from technical_analysis.vwap_reclaim import compute_vwap_reclaim_status


def _bars(closes: list[float], volumes: list[float] | None = None, start: str = "2026-09-04 09:15:00") -> pd.DataFrame:
    start_ts = datetime.fromisoformat(start)
    n = len(closes)
    volumes = volumes or [1000.0] * n
    return pd.DataFrame({
        "Datetime": [start_ts + timedelta(minutes=i) for i in range(n)],
        "Open": closes,
        "High": closes,
        "Low": closes,
        "Close": closes,
        "Volume": volumes,
    })


class TestClearReclaim:

    def test_dip_then_recovery_is_reported_as_reclaimed(self):
        # Running mean after bar 10 (5x100, 5x80) = 90; bar 6 close=80 < 90
        # -> dipped. Running mean after bar 20 (+10x130) = 110; close=130
        # > 110 -> currently above. Both true => reclaimed.
        closes = [100.0] * 5 + [80.0] * 5 + [130.0] * 10
        result = compute_vwap_reclaim_status(_bars(closes))

        assert result["invalidated_reason"] is None
        assert result["dipped_below_vwap_today"] is True
        assert result["currently_above_vwap"] is True
        assert result["vwap_reclaimed"] is True
        assert result["vwap_value"] == pytest.approx(110.0)


class TestAlwaysAboveVwap:

    def test_monotonically_rising_closes_never_dip_below_running_mean(self):
        closes = [100.0 + i for i in range(20)]
        result = compute_vwap_reclaim_status(_bars(closes))

        assert result["invalidated_reason"] is None
        assert result["dipped_below_vwap_today"] is False
        assert result["currently_above_vwap"] is True
        # The defining distinction the spec calls out: "always strong" is
        # NOT the same state as "recovered from weakness".
        assert result["vwap_reclaimed"] is False


class TestStillBelowVwap:

    def test_monotonically_falling_closes_stay_below(self):
        closes = [130.0 - i for i in range(20)]
        result = compute_vwap_reclaim_status(_bars(closes))

        assert result["invalidated_reason"] is None
        assert result["dipped_below_vwap_today"] is True
        assert result["currently_above_vwap"] is False
        assert result["vwap_reclaimed"] is False


class TestInsufficientBarsEarlySession:

    def test_fewer_than_minimum_bars_fails_closed(self):
        closes = [100.0, 101.0, 99.0, 102.0, 103.0]  # 5 bars, well-formed
        result = compute_vwap_reclaim_status(_bars(closes))

        assert result["invalidated_reason"] == "insufficient_bars_early_session"
        assert result["vwap_reclaimed"] is False
        assert result["currently_above_vwap"] is False
        assert result["vwap_value"] is None
        assert result["dipped_below_vwap_today"] is False

    def test_none_input_fails_closed(self):
        result = compute_vwap_reclaim_status(None)
        assert result["invalidated_reason"] == "no_intraday_bars"

    def test_empty_dataframe_fails_closed(self):
        result = compute_vwap_reclaim_status(pd.DataFrame())
        assert result["invalidated_reason"] == "no_intraday_bars"


class TestMalformedData:

    def test_missing_required_column_fails_closed(self):
        df = _bars([100.0] * 20).drop(columns=["Volume"])
        result = compute_vwap_reclaim_status(df)

        assert result["invalidated_reason"] == "missing_required_columns"
        assert result["vwap_reclaimed"] is False

    def test_non_numeric_prices_fail_closed(self):
        df = _bars([100.0] * 20)
        df["Close"] = "not-a-number"
        result = compute_vwap_reclaim_status(df)

        assert result["invalidated_reason"] == "malformed_data"

    def test_negative_price_fails_closed(self):
        closes = [100.0] * 19 + [-5.0]
        result = compute_vwap_reclaim_status(_bars(closes))

        assert result["invalidated_reason"] == "malformed_data"

    def test_zero_total_volume_fails_closed(self):
        closes = [100.0] * 20
        result = compute_vwap_reclaim_status(_bars(closes, volumes=[0.0] * 20))

        assert result["invalidated_reason"] == "malformed_data"


class TestInsufficientCoverageRatio:
    """Deliberate refinement beyond the spec's literal fail-closed wording
    (agreed with the user before implementation, per Part 1's investigation
    finding real, large intraday coverage gaps on thinner NSE tickers live):
    enough raw bars can still span too little of the elapsed session to
    trust the resulting VWAP."""

    def test_sparse_bars_over_a_long_elapsed_window_fails_closed(self):
        # 20 real bars, but scattered every 5 minutes -> spans 96 minutes
        # for only 20 bars actually present (~21% coverage), well under
        # the 70% floor, even though MIN_BARS_REQUIRED (15) is cleared.
        start_ts = datetime.fromisoformat("2026-09-04 09:15:00")
        closes = [100.0] * 20
        df = pd.DataFrame({
            "Datetime": [start_ts + timedelta(minutes=5 * i) for i in range(20)],
            "High": closes, "Low": closes, "Close": closes,
            "Volume": [1000.0] * 20,
        })
        result = compute_vwap_reclaim_status(df)

        assert result["invalidated_reason"] == "insufficient_bar_coverage"
        assert result["vwap_reclaimed"] is False
