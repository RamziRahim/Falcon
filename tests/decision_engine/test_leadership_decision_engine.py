"""
Tests for decision_engine/leadership_decision_engine.py -- kept
deliberately small per spec, five tests that actually matter:

1. Pattern selection takes the single best-weighted confirmed pattern,
   never sums multiple simultaneously-confirmed patterns.
2. The market/sector cascade caps an otherwise score-EXECUTE candidate
   when the broader market regime is UNFAVORABLE.
3. The days_to_earnings independent cap limits an otherwise score-EXECUTE
   candidate to ALERT_WATCHLIST.
4. LOW_DELIVERY_CONVICTION fires on low delivery % even when a breakout
   pattern is otherwise confirmed.
5. promoter_trend=None is skip-if-absent: no score effect, no
   PROMOTER_STAKE_DECLINING flag.
"""
from __future__ import annotations

import pytest

from decision_engine.leadership_decision_engine import (
    categorize,
    compute_score,
    get_best_pattern_points,
    get_fakeout_risk_flags,
)


def _candidate(**overrides) -> dict:
    base = {
        "symbol": "TEST",
        "Trend_State": "UPTREND",
        "Close": 100.0,
        "Rel_Vol": 1.0,
        "D_E": 0.2,
        "ROCE": 15.0,
        "RS_Rating": 50.0,
        "RSI_14": 50.0,
        "ATR_14": 5.0,
        "Delivery_Pct": 40.0,
        "Delivery_Pct_20d_avg": 40.0,
        "margin_trend_yoy": "FLAT",
        "days_to_earnings": 30,
        "institutional_sponsorship_pct": 10.0,
        "has_buy_activity": False,
        "has_active_fvg": False,
        "has_liquidity_sweep": False,
        "fii_trend": None, "dii_trend": None, "promoter_trend": None,
        "is_vcp_breakout": False, "is_flat_base_breakout": False,
        "is_cup_handle_breakout": False, "is_ascending_triangle_breakout": False,
        "is_bull_flag_breakout": False,
        "Multiple_Patterns_Confirmed": False,
    }
    base.update(overrides)
    return base


def _sector_row(**overrides) -> dict:
    # Rank=8/Total=10 -> NOT top half, avoids an incidental +10 that
    # would muddy the score-arithmetic assertions below.
    base = {"Avg_RS_Rating": 50.0, "Pct_Uptrend": 50.0, "Rank": 8, "Total_Sectors": 10}
    base.update(overrides)
    return base


class TestPatternSelectionNoDoubleCounting:

    def test_two_simultaneously_confirmed_patterns_score_only_the_best_one(self):
        # VCP (+30) and Flat Base (+18) both confirmed on the same
        # candidate -- their shape definitions genuinely overlap (a VCP's
        # final, tightest contraction wave can also qualify as a flat
        # base), so summing would double-count one observation as two.
        candidate = _candidate(is_vcp_breakout=True, is_flat_base_breakout=True)
        sector_row = _sector_row()

        points, field = get_best_pattern_points(candidate)
        assert points == 30
        assert field == "is_vcp_breakout"

        score = compute_score(candidate, sector_row)
        # 30 (VCP only) + 10 (RS_Rating 50/100*20) = 40, NOT 30+18+10=58.
        assert score == pytest.approx(40.0)


class TestMarketRegimeCascadeCap:

    def test_unfavorable_market_caps_an_otherwise_execute_score(self):
        # Comfortably >=65 on points alone: VCP breakout (+30), active FVG
        # (+15), liquidity sweep (+15), full RS_Rating (+20), strong
        # institutional sponsorship (+10) = 90.
        candidate = _candidate(
            is_vcp_breakout=True, has_active_fvg=True, has_liquidity_sweep=True,
            RS_Rating=100.0, institutional_sponsorship_pct=25.0,
        )
        sector_row = _sector_row(Avg_RS_Rating=70.0, Pct_Uptrend=70.0)  # STRONG sector

        score = compute_score(candidate, sector_row)
        assert score >= 65.0  # sanity: would be EXECUTE on points alone

        result = categorize(candidate, sector_row, market_verdict="UNFAVORABLE")

        assert result["category"] == "ALERT_WATCHLIST"
        assert result["market_regime_verdict"] == "UNFAVORABLE"


class TestEarningsProximityIndependentCap:

    def test_upcoming_earnings_caps_an_otherwise_execute_candidate(self):
        candidate = _candidate(
            is_vcp_breakout=True, has_active_fvg=True, has_liquidity_sweep=True,
            RS_Rating=100.0, institutional_sponsorship_pct=25.0,
            days_to_earnings=5,
        )
        sector_row = _sector_row(Avg_RS_Rating=70.0, Pct_Uptrend=70.0)

        result = categorize(candidate, sector_row, market_verdict="FAVORABLE")

        assert result["caps_applied"] == ["EARNINGS_PROXIMITY"]
        assert result["category"] == "ALERT_WATCHLIST"


class TestLowDeliveryConviction:

    def test_low_delivery_pct_flags_fakeout_risk_despite_confirmed_breakout(self):
        # A confirmed breakout (is_vcp_breakout=True, implying its own
        # volume-confirmation check already passed) can still be a
        # fakeout if the volume behind it was mostly intraday churn
        # rather than real delivery-based buying -- that's what this
        # flag catches, independent of the breakout's own volume gate.
        candidate = _candidate(is_vcp_breakout=True, Delivery_Pct=20.0, Delivery_Pct_20d_avg=40.0)
        sector_row = _sector_row()

        flags = get_fakeout_risk_flags(candidate, sector_row)

        assert "LOW_DELIVERY_CONVICTION" in flags


class TestPromoterTrendSkipIfAbsent:

    def test_promoter_trend_none_neither_scores_nor_flags(self):
        with_none = _candidate(promoter_trend=None)
        without_field = _candidate()
        del without_field["promoter_trend"]
        sector_row = _sector_row()

        score_with_none = compute_score(with_none, sector_row)
        score_without_field = compute_score(without_field, sector_row)

        # Same as a candidate with no promoter signal at all -- no bonus,
        # no penalty either way.
        assert score_with_none == pytest.approx(score_without_field)

        flags = get_fakeout_risk_flags(with_none, sector_row)
        assert "PROMOTER_STAKE_DECLINING" not in flags


class TestMicrostructureSignalsAreFeatureFlagged:
    """Liquidity sweep / FVG must be fully opt-in: with
    enable_microstructure_signals=False (the default), categorize()'s
    output must be byte-for-byte identical whether or not the new fields
    are even present on `candidate` -- these two signals must never
    silently change existing behavior."""

    def test_flag_off_output_is_identical_with_or_without_the_new_fields_present(self):
        base_candidate = _candidate(is_vcp_breakout=True, RS_Rating=80.0)
        candidate_with_signals = _candidate(
            is_vcp_breakout=True, RS_Rating=80.0,
            liquidity_sweep_direction="SSL", fvg_direction="bullish", fvg_filled_pct=0.0,
        )
        sector_row = _sector_row()

        result_without = categorize(base_candidate, sector_row, market_verdict="FAVORABLE")
        result_with = categorize(candidate_with_signals, sector_row, market_verdict="FAVORABLE")

        # supporting_data legitimately differs (it's just the input
        # candidate passed through) -- everything DECISION-relevant must
        # be identical.
        for key in result_without:
            if key == "supporting_data":
                continue
            assert result_with[key] == result_without[key], f"{key} differed with flag off: {result_with[key]!r} vs {result_without[key]!r}"

    def test_flag_on_applies_the_sweep_and_fvg_bonuses(self):
        candidate_plain = _candidate(is_vcp_breakout=True, RS_Rating=50.0)
        candidate_with_signals = _candidate(
            is_vcp_breakout=True, RS_Rating=50.0,
            liquidity_sweep_direction="SSL", fvg_direction="bullish", fvg_filled_pct=0.0,
        )
        sector_row = _sector_row()

        score_plain = compute_score(candidate_plain, sector_row, enable_microstructure_signals=True)
        score_with_signals = compute_score(candidate_with_signals, sector_row, enable_microstructure_signals=True)

        assert score_with_signals > score_plain
        assert score_with_signals - score_plain == pytest.approx(12.0)  # 6 (sweep) + 6 (FVG)

        result = categorize(
            candidate_with_signals, sector_row, market_verdict="FAVORABLE",
            enable_microstructure_signals=True,
        )
        assert "LIQUIDITY_SWEEP_SSL_CONFIRMED" in result["contributing_factors"]
        assert "BULLISH_FVG_UNFILLED" in result["contributing_factors"]

    def test_flag_on_but_no_signals_present_matches_flag_off(self):
        # Turning the flag on with neither signal actually present must
        # not change anything -- the flag alone isn't a bonus.
        candidate = _candidate(is_vcp_breakout=True, RS_Rating=50.0)
        sector_row = _sector_row()

        score_flag_off = compute_score(candidate, sector_row, enable_microstructure_signals=False)
        score_flag_on = compute_score(candidate, sector_row, enable_microstructure_signals=True)

        assert score_flag_off == pytest.approx(score_flag_on)
