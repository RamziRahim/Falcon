"""
Tests for ui/flag_descriptions.py -- every real factor/risk-flag string
decision_engine/leadership_decision_engine.py can produce (enumerated
from that module directly, not from a sample scan), each getting an
accurate tooltip, with real numbers plugged in when the row has them and
an honest generic fallback when it doesn't.
"""
from __future__ import annotations

import math

import pytest

from ui.flag_descriptions import get_factor_tooltip, get_risk_flag_tooltip


class TestContributingFactorTooltips:

    def test_macd_momentum_aligned(self):
        tip = get_factor_tooltip("MACD_MOMENTUM_ALIGNED", {})
        assert "MACD" in tip and "momentum" in tip.lower()

    def test_liquidity_sweep_ssl_confirmed(self):
        tip = get_factor_tooltip("LIQUIDITY_SWEEP_SSL_CONFIRMED", {})
        assert "swing low" in tip.lower()

    def test_bullish_fvg_unfilled_plugs_in_real_fill_pct(self):
        tip = get_factor_tooltip("BULLISH_FVG_UNFILLED", {"fvg_filled_pct": 12.0})
        assert "12%" in tip

    def test_bullish_fvg_unfilled_falls_back_when_pct_missing(self):
        tip = get_factor_tooltip("BULLISH_FVG_UNFILLED", {})
        assert "Fair Value Gap" in tip
        assert "%" not in tip

    def test_unknown_factor_falls_back_to_readable_label_not_a_crash(self):
        tip = get_factor_tooltip("SOME_NEW_FACTOR", {})
        assert tip == "Some New Factor"


class TestRiskFlagTooltips:

    def test_low_delivery_conviction_plugs_in_real_numbers(self):
        row = {"Delivery_Pct": 55.91, "Delivery_Pct_20d_avg": 57.40}
        tip = get_risk_flag_tooltip("LOW_DELIVERY_CONVICTION", row)
        assert "55.91%" in tip
        assert "57.40%" in tip

    def test_low_delivery_conviction_falls_back_when_missing(self):
        tip = get_risk_flag_tooltip("LOW_DELIVERY_CONVICTION", {})
        assert "20-day average" in tip
        assert "%" not in tip

    def test_low_delivery_conviction_falls_back_when_nan(self):
        row = {"Delivery_Pct": float("nan"), "Delivery_Pct_20d_avg": 57.40}
        tip = get_risk_flag_tooltip("LOW_DELIVERY_CONVICTION", row)
        assert "%" not in tip

    def test_isolated_move_plugs_in_pct_and_sector(self):
        row = {"Pct_Uptrend": 22.0, "Sector": "IT"}
        tip = get_risk_flag_tooltip("ISOLATED_MOVE_NO_SECTOR_TAILWIND", row)
        assert "22%" in tip
        assert "IT" in tip

    def test_isolated_move_falls_back_without_sector(self):
        row = {"Pct_Uptrend": 22.0}
        tip = get_risk_flag_tooltip("ISOLATED_MOVE_NO_SECTOR_TAILWIND", row)
        assert "22%" in tip
        assert "sector peers" in tip

    def test_isolated_move_falls_back_fully_when_missing(self):
        tip = get_risk_flag_tooltip("ISOLATED_MOVE_NO_SECTOR_TAILWIND", {})
        assert "30%" in tip

    def test_technically_overextended_plugs_in_real_rsi(self):
        tip = get_risk_flag_tooltip("TECHNICALLY_OVEREXTENDED", {"RSI_14": 78.3})
        assert "78.3" in tip

    def test_technically_overextended_falls_back_when_missing(self):
        tip = get_risk_flag_tooltip("TECHNICALLY_OVEREXTENDED", {})
        assert "70" in tip

    def test_macd_bearish_divergence(self):
        tip = get_risk_flag_tooltip("MACD_BEARISH_DIVERGENCE", {})
        assert "momentum" in tip.lower()

    def test_margin_quality_concern(self):
        tip = get_risk_flag_tooltip("MARGIN_QUALITY_CONCERN", {})
        assert "CONTRACTING" in tip

    def test_promoter_stake_declining(self):
        tip = get_risk_flag_tooltip("PROMOTER_STAKE_DECLINING", {})
        assert "DECREASING" in tip

    def test_pattern_on_probation_uses_human_pattern_label(self):
        tip = get_risk_flag_tooltip("PATTERN_ON_PROBATION:is_cup_handle_breakout", {})
        assert "Cup & Handle" in tip
        assert "probation" in tip.lower()

    def test_pattern_on_probation_falls_back_for_unmapped_pattern_field(self):
        tip = get_risk_flag_tooltip("PATTERN_ON_PROBATION:is_some_new_breakout", {})
        assert "Is Some New Breakout" in tip

    def test_unknown_flag_falls_back_to_readable_label_not_a_crash(self):
        tip = get_risk_flag_tooltip("SOME_NEW_RISK_FLAG", {})
        assert tip == "Some New Risk Flag"
