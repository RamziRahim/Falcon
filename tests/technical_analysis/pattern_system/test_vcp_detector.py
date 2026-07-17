"""
Tests for technical_analysis/pattern_system/vcp_detector.py — written against
the Falcon Phase 5 spec's definition of correct behavior (trend-context gate,
volume-confirmed breakout, continuous score), not against what the
pre-fix code happens to produce. Expected to fail against unfixed code:
every test calls analyze_vcp(df, micro_pivots, trend_state) -- the 3-arg
signature the spec introduces -- so they fail loudly (TypeError) until the
trend-gate parameter exists, rather than silently passing on the old code.
"""
from __future__ import annotations

import pandas as pd
import pytest

from technical_analysis.pattern_system.models import SwingPoint
from technical_analysis.pattern_system.vcp_detector import VCPDetector


def _pivots_from_depths(depths: list[float], base_high: float = 100.0) -> list[SwingPoint]:
    """Alternating HIGH(base_high)/LOW(base_high*(1-depth/100)) pivots, one
    wave per depth. Resistance stays fixed at base_high across waves so only
    the depths (not the price levels) drive the contraction math."""
    pivots = []
    idx = 0
    for depth in depths:
        pivots.append(SwingPoint(index=idx, date=f"d{idx}", price=base_high, type="HIGH", is_higher=True))
        idx += 5
        low_price = base_high * (1 - depth / 100)
        pivots.append(SwingPoint(index=idx, date=f"d{idx}", price=low_price, type="LOW", is_higher=True))
        idx += 5
    return pivots


def _score_df(vdu_ratio: float, vol_baseline: float = 100_000.0, latest_close: float = 150.0) -> pd.DataFrame:
    """A df whose trailing-3-day volume average yields the given VDU ratio
    against an explicit Volume_SMA_20 baseline."""
    recent_vol = vol_baseline * (1 - vdu_ratio)
    n = 20
    closes = [100.0] * (n - 1) + [latest_close]
    volumes = [100_000] * (n - 3) + [recent_vol, recent_vol, recent_vol]
    sma = [vol_baseline] * n
    return pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=n, freq="D"),
        "Open": closes, "High": closes, "Low": closes, "Close": closes,
        "Volume": volumes, "Volume_SMA_20": sma,
    })


@pytest.fixture
def detector() -> VCPDetector:
    return VCPDetector()


class TestTrendContextGate:
    """#1: VCP requires an established uptrend (Minervini Stage 2)."""

    def test_valid_contraction_shape_in_uptrend_is_a_setup(
        self, detector, synthetic_vcp_uptrend_pivots, synthetic_vcp_uptrend_df
    ):
        result = detector.analyze_vcp(synthetic_vcp_uptrend_df, synthetic_vcp_uptrend_pivots, "UPTREND")
        assert result["is_vcp_setup"] == True
        assert result["contractions_count"] == 3
        assert result.get("invalidated_reason") is None

    def test_identical_shape_in_downtrend_is_rejected(
        self, detector, synthetic_vcp_downtrend_pivots, synthetic_vcp_uptrend_df
    ):
        result = detector.analyze_vcp(synthetic_vcp_uptrend_df, synthetic_vcp_downtrend_pivots, "DOWNTREND")
        assert result["is_vcp_setup"] == False
        assert result["invalidated_reason"] == "NOT_IN_UPTREND", (
            "A stock in DOWNTREND must never be flagged as a VCP setup, "
            "and must say why via invalidated_reason."
        )

    def test_identical_shape_in_choppy_is_rejected(
        self, detector, synthetic_vcp_downtrend_pivots, synthetic_vcp_uptrend_df
    ):
        result = detector.analyze_vcp(synthetic_vcp_uptrend_df, synthetic_vcp_downtrend_pivots, "CHOPPY")
        assert result["is_vcp_setup"] == False
        assert result["invalidated_reason"] == "NOT_IN_UPTREND"

    def test_gate_short_circuits_before_touching_df(self, detector, synthetic_vcp_uptrend_pivots):
        """The gate check must happen first -- a garbage/empty df should not
        cause a crash for a non-uptrend stock, since real code shouldn't even
        need to read it in that branch."""
        empty_df = pd.DataFrame({"Date": [], "Close": [], "Volume": []})
        result = detector.analyze_vcp(empty_df, synthetic_vcp_uptrend_pivots, "DOWNTREND")
        assert result["is_vcp_setup"] == False
        assert result["invalidated_reason"] == "NOT_IN_UPTREND"


class TestContractionShapeValidation:

    def test_widening_waves_rejected_regardless_of_trend(
        self, detector, synthetic_widening_waves_pivots, synthetic_widening_waves_df
    ):
        result = detector.analyze_vcp(synthetic_widening_waves_df, synthetic_widening_waves_pivots, "UPTREND")
        assert result["is_vcp_setup"] == False, (
            "Waves widening 8% -> 15% -> 25% are not a VCP even in an uptrend."
        )
        assert result.get("invalidated_reason") is not None

    def test_malformed_non_alternating_pivot_list_does_not_crash(self, detector):
        """SwingDetector's output isn't guaranteed to strictly alternate
        HIGH/LOW. vcp_detector must skip non HIGH->LOW adjacent pairs, not
        crash or silently miscount."""
        pivots = [
            SwingPoint(index=0, date="d0", price=100.0, type="HIGH", is_higher=True),
            SwingPoint(index=1, date="d1", price=105.0, type="HIGH", is_higher=True),  # consecutive HIGH
            SwingPoint(index=2, date="d2", price=90.0, type="LOW", is_higher=False),   # wave1: 105->90 = 14.29%
            SwingPoint(index=3, date="d3", price=110.0, type="HIGH", is_higher=True),  # LOW->HIGH, skip
            SwingPoint(index=4, date="d4", price=104.0, type="LOW", is_higher=False),  # wave2: 110->104 = 5.45%
        ]
        df = pd.DataFrame({
            "Date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "Open": [100] * 5, "High": [100] * 5, "Low": [100] * 5, "Close": [100, 100, 100, 100, 115],
            "Volume": [100_000] * 5,
        })
        result = detector.analyze_vcp(df, pivots, "UPTREND")
        assert result["contractions_count"] == 2, (
            "Only genuine HIGH->LOW adjacent pairs should count as contractions "
            "-- the HIGH,HIGH and LOW,HIGH pairs must be skipped, not crash or "
            "get miscounted."
        )


class TestEdgeCases:

    def test_too_few_pivots_returns_default_not_crash(self, detector):
        pivots = [
            SwingPoint(index=0, date="d0", price=100.0, type="HIGH", is_higher=True),
            SwingPoint(index=1, date="d1", price=90.0, type="LOW", is_higher=True),
        ]
        df = pd.DataFrame({"Date": [], "Close": [], "Volume": []})
        result = detector.analyze_vcp(df, pivots, "UPTREND")
        assert result["is_vcp_setup"] == False
        assert result["contractions_count"] == 0
        assert result.get("invalidated_reason") is not None

    def test_missing_volume_sma_20_column_falls_back_to_rolling_mean(
        self, detector, synthetic_breakout_pivots, synthetic_breakout_with_volume_df
    ):
        assert "Volume_SMA_20" not in synthetic_breakout_with_volume_df.columns
        result = detector.analyze_vcp(synthetic_breakout_with_volume_df, synthetic_breakout_pivots, "UPTREND")
        # Falls back to df["Volume"].rolling(20).mean() -- confirmed working,
        # not raising a KeyError, and producing a sane confirmed breakout.
        assert result["is_vcp_breakout"] == True

    def test_explicit_volume_sma_20_column_is_preferred_over_recompute(
        self, detector, synthetic_breakout_pivots, synthetic_breakout_explicit_volume_sma_df
    ):
        result = detector.analyze_vcp(
            synthetic_breakout_explicit_volume_sma_df, synthetic_breakout_pivots, "UPTREND"
        )
        assert result["breakout_volume_confirmed"] == True, (
            "A naive rolling(20).mean() recompute of Volume would NOT confirm "
            "here -- only reading the existing Volume_SMA_20 column does."
        )


class TestBreakoutVolumeConfirmation:
    """#2: is_vcp_breakout requires both a price cross AND volume expansion."""

    def test_price_cross_with_volume_expansion_confirms_breakout(
        self, detector, synthetic_breakout_pivots, synthetic_breakout_with_volume_df
    ):
        result = detector.analyze_vcp(synthetic_breakout_with_volume_df, synthetic_breakout_pivots, "UPTREND")
        assert result["price_crossed_pivot"] == True
        assert result["breakout_volume_confirmed"] == True
        assert result["is_vcp_breakout"] == True

    def test_price_cross_without_volume_expansion_does_not_confirm(
        self, detector, synthetic_breakout_pivots, synthetic_breakout_no_volume_df
    ):
        result = detector.analyze_vcp(synthetic_breakout_no_volume_df, synthetic_breakout_pivots, "UPTREND")
        assert result["price_crossed_pivot"] == True, (
            "Price genuinely crossed the resistance pivot in both fixtures -- "
            "only volume should differ."
        )
        assert result["breakout_volume_confirmed"] == False
        assert result["is_vcp_breakout"] == False, (
            "A price crossing with normal (non-expansion) volume must not "
            "count as a confirmed breakout."
        )


class TestContinuousScore:
    """#4a: vcp_score is a continuous 0-100 blend, not a 3-bucket value."""

    def test_tighter_final_wave_scores_higher(self, detector):
        loose = detector.analyze_vcp(_score_df(vdu_ratio=0.5), _pivots_from_depths([20, 10]), "UPTREND")
        tight = detector.analyze_vcp(_score_df(vdu_ratio=0.5), _pivots_from_depths([20, 4]), "UPTREND")
        assert loose["vcp_score"] == pytest.approx(50.0)
        assert tight["vcp_score"] == pytest.approx(62.0)
        assert tight["vcp_score"] > loose["vcp_score"], (
            "Identical wave count and VDU, but a tighter final wave (4% vs "
            "10% depth) must score higher -- proving the score is continuous, "
            "not one of 3 fixed buckets."
        )

    def test_more_confirmed_waves_scores_higher(self, detector):
        two_wave = detector.analyze_vcp(_score_df(vdu_ratio=0.5), _pivots_from_depths([20, 6]), "UPTREND")
        three_wave = detector.analyze_vcp(_score_df(vdu_ratio=0.5), _pivots_from_depths([20, 12, 6]), "UPTREND")
        assert two_wave["vcp_score"] == pytest.approx(58.0)
        assert three_wave["vcp_score"] == pytest.approx(65.5)
        assert three_wave["vcp_score"] > two_wave["vcp_score"], (
            "Identical tightness ratio (first=20%, last=6%) and VDU, but more "
            "confirmed waves (3 vs 2) must score higher."
        )

    def test_deeper_volume_dry_up_scores_higher(self, detector):
        mild_vdu = detector.analyze_vcp(_score_df(vdu_ratio=0.2), _pivots_from_depths([20, 10]), "UPTREND")
        deep_vdu = detector.analyze_vcp(_score_df(vdu_ratio=0.8), _pivots_from_depths([20, 10]), "UPTREND")
        assert mild_vdu["vcp_score"] == pytest.approx(41.0)
        assert deep_vdu["vcp_score"] == pytest.approx(59.0)
        assert deep_vdu["vcp_score"] > mild_vdu["vcp_score"], (
            "Identical wave count and tightness, but deeper volume dry-up "
            "(80% below baseline vs 20%) must score higher."
        )

    def test_score_is_never_one_of_the_old_three_fixed_buckets(self, detector):
        """Regression guard: the old implementation could only ever produce
        50.0, 75.0, or 100.0. A genuinely continuous formula should be able
        to land somewhere else entirely for an arbitrary shape."""
        result = detector.analyze_vcp(_score_df(vdu_ratio=0.37), _pivots_from_depths([18, 9]), "UPTREND")
        assert result["vcp_score"] not in (50.0, 75.0, 100.0)
