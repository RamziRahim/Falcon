"""
Tests for technical_analysis/consolidation_features.py (Phase 4.1/4.2,
docs/FALCON_V2_REDESIGN.md section 5) -- one synthetic fixture per
feature, kept lean per this codebase's own convention: a qualifying case
plus whatever invalidation/edge case actually matters for that feature,
not exhaustive coverage.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from technical_analysis.consolidation_features import (
    _find_base_boundaries,
    compute_base_depth_pct,
    compute_base_length_bars,
    compute_breakout_volume_ratio,
    compute_consolidation_features,
    compute_contraction_slope,
    compute_dist_52w_high,
    compute_pivot_proximity,
    compute_prior_trend_strength,
    compute_rs_line_new_high,
    compute_volume_dryup_ratio,
)
from technical_analysis.pattern_system.models import SwingPoint


def _ohlcv(closes, start="2024-01-01", volumes=None, highs=None, lows=None, atr=None, vol_sma=None):
    n = len(closes)
    dates = pd.date_range(start, periods=n, freq="D")
    closes = np.asarray(closes, dtype=float)
    df = pd.DataFrame({
        "Date": dates,
        "Open": closes,
        "High": highs if highs is not None else closes * 1.01,
        "Low": lows if lows is not None else closes * 0.99,
        "Close": closes,
        "Volume": volumes if volumes is not None else [100_000] * n,
    })
    if atr is not None:
        df["ATR_14"] = atr
    if vol_sma is not None:
        df["Volume_SMA_20"] = vol_sma
    return df


class TestFindBaseBoundaries:

    def test_returns_the_last_high_and_the_low_before_it(self):
        pivots = [
            SwingPoint(index=2, date="d", price=90.0, type="LOW", is_higher=True),
            SwingPoint(index=10, date="d", price=120.0, type="HIGH", is_higher=True),
            SwingPoint(index=15, date="d", price=105.0, type="LOW", is_higher=True),
        ]

        result = _find_base_boundaries(pivots, as_of_index=20)

        assert result is not None
        swing_low, swing_high = result
        assert swing_high.index == 10 and swing_high.price == 120.0
        assert swing_low.index == 2 and swing_low.price == 90.0

    def test_ignores_pivots_after_as_of_index(self):
        # Point-in-time correctness: a pivot confirmed only after the
        # as-of date must not be visible yet -- same lookahead-bias
        # discipline as backtesting/replay_engine.py's own docstring.
        pivots = [
            SwingPoint(index=2, date="d", price=90.0, type="LOW", is_higher=True),
            SwingPoint(index=10, date="d", price=120.0, type="HIGH", is_higher=True),
            SwingPoint(index=25, date="d", price=150.0, type="HIGH", is_higher=True),  # future
        ]

        result = _find_base_boundaries(pivots, as_of_index=15)

        assert result is not None
        _, swing_high = result
        assert swing_high.index == 10  # not the future 150.0 HIGH

    def test_no_high_pivot_yet_returns_none(self):
        pivots = [SwingPoint(index=2, date="d", price=90.0, type="LOW", is_higher=True)]

        assert _find_base_boundaries(pivots, as_of_index=20) is None

    def test_high_with_no_low_before_it_returns_none(self):
        pivots = [SwingPoint(index=2, date="d", price=120.0, type="HIGH", is_higher=True)]

        assert _find_base_boundaries(pivots, as_of_index=20) is None


class TestPriorTrendStrength:

    def test_matches_hand_computation(self):
        swing_low = SwingPoint(index=10, date="d", price=100.0, type="LOW", is_higher=True)
        swing_high = SwingPoint(index=30, date="d", price=130.0, type="HIGH", is_higher=True)

        result = compute_prior_trend_strength(swing_low, swing_high)

        assert result["prior_trend_pct_gain"] == pytest.approx(30.0)  # (130-100)/100 * 100
        assert result["prior_trend_slope"] == pytest.approx(1.5)      # 30% / 20 bars
        assert result["prior_trend_bars"] == 20

    def test_zero_bars_apart_returns_none_not_a_crash(self):
        swing_low = SwingPoint(index=10, date="d", price=100.0, type="LOW", is_higher=True)
        swing_high = SwingPoint(index=10, date="d", price=130.0, type="HIGH", is_higher=True)

        result = compute_prior_trend_strength(swing_low, swing_high)

        assert result["prior_trend_pct_gain"] is None
        assert result["prior_trend_slope"] is None


class TestBaseDepthPct:

    def test_matches_hand_computation(self):
        base_window = _ohlcv([100.0] * 10, highs=[110.0] * 10, lows=[95.0] * 10)

        result = compute_base_depth_pct(base_window)

        # abs tolerance, not the default tiny relative one -- the function
        # itself rounds to 2dp by design (a display/storage precision
        # choice), so comparing against an unrounded hand computation
        # needs a matching tolerance, not a bug in the function.
        assert result == pytest.approx((110.0 - 95.0) / 110.0 * 100, abs=0.01)

    def test_empty_window_returns_none(self):
        assert compute_base_depth_pct(pd.DataFrame(columns=["High", "Low"])) is None


class TestBaseLengthBars:

    def test_counts_rows(self):
        assert compute_base_length_bars(_ohlcv([100.0] * 17)) == 17


class TestContractionSlope:

    def test_shrinking_atr_gives_a_negative_slope(self):
        # ATR/Close shrinking steadily over the base -- the VCP essence.
        closes = [100.0] * 10
        atr = np.linspace(5.0, 1.0, 10)  # contracting
        base_window = _ohlcv(closes, atr=atr)

        slope = compute_contraction_slope(base_window)

        assert slope < 0

    def test_growing_atr_gives_a_positive_slope(self):
        closes = [100.0] * 10
        atr = np.linspace(1.0, 5.0, 10)  # expanding
        base_window = _ohlcv(closes, atr=atr)

        slope = compute_contraction_slope(base_window)

        assert slope > 0

    def test_missing_atr_column_returns_none(self):
        base_window = _ohlcv([100.0] * 10)  # no ATR_14 column

        assert compute_contraction_slope(base_window) is None

    def test_too_short_a_base_returns_none(self):
        base_window = _ohlcv([100.0, 101.0], atr=[2.0, 1.9])

        assert compute_contraction_slope(base_window) is None


class TestVolumeDryupRatio:

    def test_lower_base_volume_than_pre_base_is_a_dryup(self):
        base_window = _ohlcv([100.0] * 5, volumes=[50_000] * 5)
        pre_base_window = _ohlcv([95.0] * 5, volumes=[100_000] * 5)

        result = compute_volume_dryup_ratio(base_window, pre_base_window)

        assert result["volume_dryup_ratio"] == pytest.approx(0.5)

    def test_lighter_down_day_volume_than_up_day_volume_is_bullish(self):
        # 3 up days (Close >= Open) at high volume, 2 down days at low
        # volume -- accumulation, per O'Neil's own read.
        base_window = pd.DataFrame({
            "Date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "Open": [100.0, 100.0, 100.0, 100.0, 100.0],
            "Close": [105.0, 105.0, 105.0, 95.0, 95.0],  # up,up,up,down,down
            "Volume": [200_000, 200_000, 200_000, 50_000, 50_000],
            "High": [106.0] * 5, "Low": [94.0] * 5,
        })

        result = compute_volume_dryup_ratio(base_window, pd.DataFrame(columns=base_window.columns))

        assert result["volume_down_up_ratio"] == pytest.approx(50_000 / 200_000)

    def test_empty_windows_return_none_not_a_crash(self):
        empty = pd.DataFrame(columns=["Open", "Close", "Volume"])

        result = compute_volume_dryup_ratio(empty, empty)

        assert result == {"volume_dryup_ratio": None, "volume_down_up_ratio": None}


class TestPivotProximity:

    def test_matches_hand_computation(self):
        base_window = _ohlcv([100.0] * 5, highs=[110.0] * 5)

        result = compute_pivot_proximity(base_window, current_close=104.5)

        assert result == pytest.approx((110.0 - 104.5) / 110.0 * 100)

    def test_price_already_through_the_pivot_is_negative(self):
        base_window = _ohlcv([100.0] * 5, highs=[110.0] * 5)

        result = compute_pivot_proximity(base_window, current_close=115.0)

        assert result < 0


class TestBreakoutVolumeRatio:

    def test_matches_hand_computation_with_volume_sma_present(self):
        df = _ohlcv([100.0] * 5, volumes=[100_000, 100_000, 100_000, 100_000, 300_000],
                    vol_sma=[100_000] * 5)

        result = compute_breakout_volume_ratio(df)

        assert result == pytest.approx(3.0)

    def test_falls_back_to_rolling_mean_without_volume_sma(self):
        df = _ohlcv([100.0] * 21, volumes=[100_000] * 20 + [400_000])  # no Volume_SMA_20 column

        result = compute_breakout_volume_ratio(df)

        assert result == pytest.approx(4.0)

    def test_insufficient_data_returns_none(self):
        df = _ohlcv([100.0])

        assert compute_breakout_volume_ratio(df) is None


class TestDist52wHigh:

    def test_matches_hand_computation(self):
        # Constant High ceiling of 120 throughout; today's Close (the
        # value the distance is actually measured from) is 110. 10 rows,
        # lookback_bars=10 -- exactly enough history, not short.
        df = _ohlcv([100.0] * 9 + [110.0], highs=[120.0] * 10)

        result = compute_dist_52w_high(df, lookback_bars=10)

        assert result["invalidated_reason"] is None
        assert result["dist_52w_high"] == pytest.approx((120.0 - 110.0) / 120.0 * 100, abs=0.01)

    def test_sitting_at_the_52w_high_is_zero(self):
        # Today's Close equals the 52-week High itself.
        df = _ohlcv([100.0] * 9 + [120.0], highs=[120.0] * 10)

        result = compute_dist_52w_high(df, lookback_bars=10)

        assert result["dist_52w_high"] == pytest.approx(0.0, abs=1e-9)

    def test_under_the_lookback_fails_closed_not_a_silent_short_window(self):
        # 251 rows against a 252-bar lookback -- pandas' own .tail(252) on
        # a 251-row frame would silently return all 251 rows with no
        # error; this must refuse to answer instead of quietly computing
        # a "52-week high" over 251 days.
        df = _ohlcv([100.0] * 250 + [110.0], highs=[120.0] * 251)

        result = compute_dist_52w_high(df, lookback_bars=252)

        assert result == {"dist_52w_high": None, "invalidated_reason": "INSUFFICIENT_HISTORY"}

    def test_exactly_at_the_lookback_boundary_computes_normally(self):
        # Exactly 252 rows against a 252-bar lookback -- the boundary
        # itself must NOT be treated as insufficient.
        df = _ohlcv([100.0] * 251 + [110.0], highs=[120.0] * 252)

        result = compute_dist_52w_high(df, lookback_bars=252)

        assert result["invalidated_reason"] is None
        assert result["dist_52w_high"] == pytest.approx((120.0 - 110.0) / 120.0 * 100, abs=0.01)

    def test_one_bar_over_the_lookback_boundary_also_computes_normally(self):
        df = _ohlcv([100.0] * 252 + [110.0], highs=[120.0] * 253)

        result = compute_dist_52w_high(df, lookback_bars=252)

        assert result["invalidated_reason"] is None
        assert result["dist_52w_high"] == pytest.approx((120.0 - 110.0) / 120.0 * 100, abs=0.01)


class TestComputeConsolidationFeatures:

    def test_well_formed_base_produces_a_valid_full_vector(self):
        # Advance from bar 0 (Low pivot, 90) to bar 20 (High pivot, 130),
        # then a shallow base from bar 20 to the as-of bar (29).
        n = 30
        closes = list(np.linspace(90.0, 130.0, 21)) + list(np.linspace(128.0, 125.0, 9))
        atr = list(np.linspace(3.0, 1.0, n))
        df = _ohlcv(closes, atr=atr, vol_sma=[100_000] * n)
        pivots = [
            SwingPoint(index=0, date="d", price=90.0, type="LOW", is_higher=True),
            SwingPoint(index=20, date="d", price=130.0, type="HIGH", is_higher=True),
        ]

        result = compute_consolidation_features(df, pivots)

        assert result["valid"] is True
        assert result["invalidated_reason"] is None
        assert result["prior_trend_pct_gain"] == pytest.approx((130.0 - 90.0) / 90.0 * 100, abs=0.01)
        assert result["base_length_bars"] == 10  # bars 20..29 inclusive
        assert result["base_depth_pct"] is not None
        assert result["contraction_slope"] is not None
        # Only 30 rows total, well under the 252-bar 52-week lookback --
        # dist_52w_high must fail closed on ITS OWN, independent reason
        # without touching the top-level "invalidated_reason" the pivot
        # boundary already used (the base itself is genuinely valid; it's
        # only the 52-week comparison specifically that lacks history).
        assert result["dist_52w_high"] is None
        assert result["dist_52w_high_invalidated_reason"] == "INSUFFICIENT_HISTORY"

    def test_no_confirmed_pivots_yet_is_explicitly_invalid(self):
        df = _ohlcv([100.0] * 10)

        result = compute_consolidation_features(df, macro_pivots=[])

        assert result["valid"] is False
        assert result["invalidated_reason"] == "INSUFFICIENT_PIVOTS"
        assert result["base_depth_pct"] is None
        assert result["dist_52w_high"] is None
        assert result["dist_52w_high_invalidated_reason"] is None

    def test_genuinely_empty_dataframe_fails_closed_not_crash(self):
        # decision_engine/candidate_assembler.py (Phase 4.6) can hand this
        # function a bare pd.DataFrame() with no Date column at all when
        # no pattern history is available -- df.sort_values("Date") would
        # raise KeyError on that, not fail closed like every other branch.
        result = compute_consolidation_features(pd.DataFrame(), macro_pivots=[])

        assert result["valid"] is False
        assert result["invalidated_reason"] == "INSUFFICIENT_PIVOTS"
        assert result["base_depth_pct"] is None


class TestComputeRsLineNewHigh:

    def test_rs_line_high_within_the_recent_window_is_a_new_high(self):
        # Stock outperforms steadily; its RS-line peak (relative to a
        # flat benchmark) is the very last bar -- within any recency window.
        stock = _ohlcv(np.linspace(100.0, 150.0, 30))
        benchmark = _ohlcv([100.0] * 30)

        result = compute_rs_line_new_high(stock, benchmark, lookback_bars=30, recency_bars=5)

        assert result["rs_line_new_high"] is True

    def test_rs_line_high_well_before_the_recent_window_is_not_a_new_high(self):
        # RS line peaks in the middle of the window, then the stock
        # underperforms into the as-of date -- the all-time high (over the
        # lookback) sits well outside the last 5 bars.
        stock_closes = list(np.linspace(100.0, 200.0, 15)) + list(np.linspace(200.0, 120.0, 15))
        stock = _ohlcv(stock_closes)
        benchmark = _ohlcv([100.0] * 30)

        result = compute_rs_line_new_high(stock, benchmark, lookback_bars=30, recency_bars=5)

        assert result["rs_line_new_high"] is False

    def test_non_overlapping_dates_return_none_not_a_crash(self):
        stock = _ohlcv([100.0] * 10, start="2024-01-01")
        benchmark = _ohlcv([100.0] * 10, start="2030-01-01")  # no shared dates at all

        result = compute_rs_line_new_high(stock, benchmark)

        assert result == {"rs_line_new_high": None, "invalidated_reason": "NO_OVERLAPPING_DATES", "rs_line_value": None}

    def test_under_the_lookback_fails_closed_not_a_silent_short_window(self):
        # 251 overlapping days against a 252-bar lookback -- pandas' own
        # .tail(252) on a 251-row series would silently return all 251
        # with no error; this must refuse to answer instead of quietly
        # computing a "252-day new high" over 251 days -- the exact gap
        # confirmed against real HDFCBANK.NS data before this fix existed.
        stock = _ohlcv(np.linspace(100.0, 150.0, 251))
        benchmark = _ohlcv([100.0] * 251)

        result = compute_rs_line_new_high(stock, benchmark, lookback_bars=252, recency_bars=5)

        assert result == {"rs_line_new_high": None, "invalidated_reason": "INSUFFICIENT_HISTORY", "rs_line_value": None}

    def test_exactly_at_the_lookback_boundary_computes_normally(self):
        stock = _ohlcv(np.linspace(100.0, 150.0, 252))
        benchmark = _ohlcv([100.0] * 252)

        result = compute_rs_line_new_high(stock, benchmark, lookback_bars=252, recency_bars=5)

        assert result["invalidated_reason"] is None
        assert result["rs_line_new_high"] is True  # steadily outperforming, peak is the last bar

    def test_one_bar_over_the_lookback_boundary_also_computes_normally(self):
        stock = _ohlcv(np.linspace(100.0, 150.0, 253))
        benchmark = _ohlcv([100.0] * 253)

        result = compute_rs_line_new_high(stock, benchmark, lookback_bars=252, recency_bars=5)

        assert result["invalidated_reason"] is None
        assert result["rs_line_new_high"] is True
