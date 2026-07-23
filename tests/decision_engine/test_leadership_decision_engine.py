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

from config import MAX_HOLDING_TRADING_DAYS
from decision_engine.leadership_decision_engine import (
    categorize,
    compute_score,
    get_best_pattern_points,
    get_entry_target_stop,
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


class TestCupHandleProbation:
    """2.6b: Cup & Handle's weight was set to 0 (data/gate1_report.md's
    G1-e, confirmed on the tuning split alone) -- detection stays on, but
    it must never win pattern-selection priority over a real
    higher-weighted pattern, and its use must be visibly flagged."""

    def test_cup_handle_alone_contributes_zero_points(self):
        candidate = _candidate(is_cup_handle_breakout=True)

        points, field = get_best_pattern_points(candidate)

        assert points == 0
        assert field == "is_cup_handle_breakout"

    def test_ascending_triangle_wins_selection_over_cup_handle_when_both_fire(self):
        # Guards against the exact bug probation could silently
        # reintroduce: PATTERN_WEIGHTS list order IS selection priority
        # (get_best_pattern_points doesn't re-sort by weight) -- Cup &
        # Handle must sit AFTER every real-weighted pattern in that list,
        # not just carry a 0 weight while still appearing early.
        candidate = _candidate(is_cup_handle_breakout=True, is_ascending_triangle_breakout=True)

        points, field = get_best_pattern_points(candidate)

        assert field == "is_ascending_triangle_breakout"
        assert points == 20

    def test_pattern_on_probation_flag_set_when_cup_handle_is_the_only_pattern(self):
        candidate = _candidate(is_cup_handle_breakout=True, RS_Rating=80.0)
        sector_row = _sector_row()

        result = categorize(candidate, sector_row, market_verdict="FAVORABLE")

        assert "PATTERN_ON_PROBATION:is_cup_handle_breakout" in result["fakeout_risk_flags"]

    def test_pattern_on_probation_flag_absent_when_a_different_pattern_wins(self):
        candidate = _candidate(is_vcp_breakout=True, RS_Rating=80.0)
        sector_row = _sector_row()

        result = categorize(candidate, sector_row, market_verdict="FAVORABLE")

        assert not any(f.startswith("PATTERN_ON_PROBATION") for f in result["fakeout_risk_flags"])


class TestTimeStopTradePlanField:
    """2.1: max_holding_days is part of the trade plan (alongside
    entry/stop_loss/target), a single MAX_HOLDING_TRADING_DAYS config
    value -- not something a caller has to separately know to apply."""

    def test_get_entry_target_stop_includes_max_holding_days(self):
        candidate = _candidate(is_vcp_breakout=True)

        result = get_entry_target_stop(candidate, "is_vcp_breakout", {"pivot_level": 100.0})

        assert result["max_holding_days"] == MAX_HOLDING_TRADING_DAYS

    def test_categorize_passes_max_holding_days_through_for_a_real_trade(self):
        candidate = _candidate(is_vcp_breakout=True, RS_Rating=80.0)
        sector_row = _sector_row()

        result = categorize(candidate, sector_row, market_verdict="FAVORABLE")

        assert result["category"] != "AVOID"
        assert result["max_holding_days"] == MAX_HOLDING_TRADING_DAYS

    def test_categorize_max_holding_days_is_none_for_disqualifier_avoid(self):
        candidate = _candidate(Trend_State="DOWNTREND")
        sector_row = _sector_row()

        result = categorize(candidate, sector_row, market_verdict="FAVORABLE")

        assert result["category"] == "AVOID"
        assert result["max_holding_days"] is None

    def test_categorize_max_holding_days_is_none_for_score_based_avoid(self):
        # No pattern, no fundamentals, middling everything -- scores well
        # under 40 with the default fixture.
        candidate = _candidate()
        sector_row = _sector_row()

        result = categorize(candidate, sector_row, market_verdict="FAVORABLE")

        assert result["category"] == "AVOID"
        assert result["max_holding_days"] is None


class TestStructuralExitsAndRRFloor:
    """2.2 (I-6): get_entry_target_stop() prices off the pattern's own
    structural low, clamped to an ATR floor/ceiling, with a measured-move
    target independent of that clamp; categorize() downgrades EXECUTE to
    ALERT_WATCHLIST (RR_BELOW_FLOOR) when the resulting reward:risk falls
    short of MIN_REWARD_RISK."""

    def test_structural_stop_used_when_within_atr_bounds(self):
        candidate = _candidate(ATR_14=5.0)
        # entry=100 (pivot), structural_low=90 -> raw distance 10, well
        # within [1x, 3x] ATR = [5, 15].
        best_result = {"pivot_level": 100.0, "structural_low": 90.0}

        result = get_entry_target_stop(candidate, "is_vcp_breakout", best_result)

        assert result["stop_loss"] == pytest.approx(90.0)
        assert result["target"] == pytest.approx(110.0)  # measured move: 100 + 10
        assert result["stop_provenance"] == "STRUCTURAL"
        assert result["target_provenance"] == "MEASURED_MOVE"

    def test_structural_stop_clamped_to_atr_floor_when_too_tight(self):
        candidate = _candidate(ATR_14=5.0)
        # raw distance 2 (100 -> 98) is tighter than the 1x-ATR floor (5).
        best_result = {"pivot_level": 100.0, "structural_low": 98.0}

        result = get_entry_target_stop(candidate, "is_vcp_breakout", best_result)

        assert result["stop_loss"] == pytest.approx(95.0)  # 100 - 5 (floor), not 100 - 2
        assert result["target"] == pytest.approx(102.0)    # measured move uses the RAW distance (2), unclamped
        assert result["stop_provenance"] == "STRUCTURAL_CLAMPED_TO_ATR_FLOOR"

    def test_structural_stop_clamped_to_atr_ceiling_when_too_wide(self):
        candidate = _candidate(ATR_14=5.0)
        # raw distance 30 (100 -> 70) is wider than the 3x-ATR ceiling (15).
        best_result = {"pivot_level": 100.0, "structural_low": 70.0}

        result = get_entry_target_stop(candidate, "is_vcp_breakout", best_result)

        assert result["stop_loss"] == pytest.approx(85.0)   # 100 - 15 (ceiling), not 100 - 30
        assert result["target"] == pytest.approx(130.0)     # measured move uses the RAW distance (30)
        assert result["stop_provenance"] == "STRUCTURAL_CLAMPED_TO_ATR_CEILING"

    def test_missing_structural_low_falls_back_to_atr(self):
        candidate = _candidate(ATR_14=5.0)
        best_result = {"pivot_level": 100.0, "structural_low": None}

        result = get_entry_target_stop(candidate, "is_vcp_breakout", best_result)

        assert result["stop_loss"] == pytest.approx(90.0)   # 100 - 2*5
        assert result["target"] == pytest.approx(112.5)     # 100 + 2.5*5
        assert result["stop_provenance"] == "ATR_FALLBACK_NO_STRUCTURAL_LOW"
        assert result["target_provenance"] == "ATR_FALLBACK_NO_STRUCTURAL_LOW"

    def test_structural_low_at_or_above_entry_falls_back_to_atr(self):
        # A mis-detected pivot -- structural_low can't legitimately sit at
        # or above the entry price.
        candidate = _candidate(ATR_14=5.0)
        best_result = {"pivot_level": 100.0, "structural_low": 100.0}

        result = get_entry_target_stop(candidate, "is_vcp_breakout", best_result)

        assert result["stop_provenance"] == "ATR_FALLBACK_NO_STRUCTURAL_LOW"

    def test_no_pattern_at_all_uses_the_no_pattern_provenance(self):
        candidate = _candidate(ATR_14=5.0)

        result = get_entry_target_stop(candidate, None, None)

        assert result["stop_provenance"] == "ATR_FALLBACK_NO_PATTERN"
        assert result["target_provenance"] == "ATR_FALLBACK_NO_PATTERN"

    def _execute_grade_candidate_with_pattern(self):
        # VCP(30) + RS_Rating 100 (+20) + active FVG (+15) + liquidity
        # sweep (+15) + top-half sector (+10) + institutional sponsorship
        # (+10) + buy activity (+10) = 110, clamped to 100 -- comfortably
        # EXECUTE-grade (>=65), with a real pattern (not MONITOR-eligible).
        candidate = _candidate(
            is_vcp_breakout=True, RS_Rating=100.0, has_active_fvg=True, has_liquidity_sweep=True,
            institutional_sponsorship_pct=25.0, has_buy_activity=True, ATR_14=5.0,
        )
        sector_row = _sector_row(Rank=2, Total_Sectors=10)
        return candidate, sector_row

    def test_execute_downgraded_to_alert_watchlist_when_rr_below_floor(self):
        candidate, sector_row = self._execute_grade_candidate_with_pattern()
        # structural_low=98 -> clamped stop distance 5, raw target distance
        # 2 -> RR = 2/5 = 0.4, well under the 1.25 floor.
        pattern_details = {"is_vcp_breakout": {"pivot_level": 100.0, "structural_low": 98.0}}

        score = compute_score(candidate, sector_row)
        assert score >= 65, "fixture must be EXECUTE-grade by score for this test to mean anything"

        result = categorize(candidate, sector_row, market_verdict="FAVORABLE", pattern_details=pattern_details)

        assert result["category"] == "ALERT_WATCHLIST"
        assert "RR_BELOW_FLOOR" in result["caps_applied"]

    def test_execute_stays_execute_when_rr_clears_the_floor(self):
        candidate, sector_row = self._execute_grade_candidate_with_pattern()
        # structural_low=70 -> clamped stop distance 15 (ceiling), raw
        # target distance 30 -> RR = 30/15 = 2.0, clears the 1.25 floor.
        pattern_details = {"is_vcp_breakout": {"pivot_level": 100.0, "structural_low": 70.0}}

        result = categorize(candidate, sector_row, market_verdict="FAVORABLE", pattern_details=pattern_details)

        assert result["category"] == "EXECUTE"
        assert "RR_BELOW_FLOOR" not in result["caps_applied"]

    def test_min_reward_risk_is_overridable_per_call(self):
        candidate, sector_row = self._execute_grade_candidate_with_pattern()
        # RR=2.0 (see test above) clears 1.25 but not an experimentally
        # stricter 2.5 floor passed explicitly.
        pattern_details = {"is_vcp_breakout": {"pivot_level": 100.0, "structural_low": 70.0}}

        result = categorize(
            candidate, sector_row, market_verdict="FAVORABLE",
            pattern_details=pattern_details, min_reward_risk=2.5,
        )

        assert result["category"] == "ALERT_WATCHLIST"
        assert "RR_BELOW_FLOOR" in result["caps_applied"]

    def test_categorize_surfaces_provenance_and_reward_risk(self):
        candidate, sector_row = self._execute_grade_candidate_with_pattern()
        pattern_details = {"is_vcp_breakout": {"pivot_level": 100.0, "structural_low": 70.0}}

        result = categorize(candidate, sector_row, market_verdict="FAVORABLE", pattern_details=pattern_details)

        assert result["stop_provenance"] == "STRUCTURAL_CLAMPED_TO_ATR_CEILING"
        assert result["target_provenance"] == "MEASURED_MOVE"
        assert result["reward_risk"] == pytest.approx(2.0)

    def test_categorize_provenance_and_reward_risk_none_for_avoid(self):
        candidate = _candidate(Trend_State="DOWNTREND")
        sector_row = _sector_row()

        result = categorize(candidate, sector_row, market_verdict="FAVORABLE")

        assert result["category"] == "AVOID"
        assert result["stop_provenance"] is None
        assert result["target_provenance"] is None
        assert result["reward_risk"] is None


class TestBreakoutRecencySurfacedOnCategorizeOutput:
    """A-5: categorize() surfaces bars_since_breakout/
    breakout_within_last_k_bars for the SELECTED pattern, not just buried
    in pattern_details -- so a consumer (funnel diagnostics, a live
    dashboard) doesn't have to dig for it."""

    def test_surfaces_selected_patterns_recency_fields(self):
        candidate = _candidate(is_vcp_breakout=True, RS_Rating=80.0)
        sector_row = _sector_row()
        pattern_details = {"is_vcp_breakout": {"pivot_level": 100.0, "bars_since_breakout": 3,
                                                "breakout_within_last_k_bars": True}}

        result = categorize(candidate, sector_row, market_verdict="FAVORABLE", pattern_details=pattern_details)

        assert result["bars_since_breakout"] == 3
        assert result["breakout_within_last_k_bars"] is True

    def test_none_and_false_when_no_pattern_fired(self):
        candidate = _candidate(RS_Rating=80.0)  # no pattern flags set
        sector_row = _sector_row()

        result = categorize(candidate, sector_row, market_verdict="FAVORABLE")

        assert result["bars_since_breakout"] is None
        assert result["breakout_within_last_k_bars"] is False

    def test_none_and_false_for_disqualifier_avoid(self):
        candidate = _candidate(Trend_State="DOWNTREND", is_vcp_breakout=True)
        sector_row = _sector_row()

        result = categorize(candidate, sector_row, market_verdict="FAVORABLE")

        assert result["category"] == "AVOID"
        assert result["bars_since_breakout"] is None
        assert result["breakout_within_last_k_bars"] is False


class TestNoPatternMonitorTier:
    """2.6c (B-8, Gate 1 decision #4): pattern presence required for
    ALERT_WATCHLIST and above -- a no-pattern candidate that scored well
    enough on everything else is demoted to MONITOR, never surfaced as a
    real ALERT_WATCHLIST/EXECUTE signal, regardless of how favorable the
    market/sector ceiling is."""

    def test_alert_watchlist_grade_no_pattern_becomes_monitor(self):
        # RS_Rating=100 (+20) + active FVG (+15) + liquidity sweep (+15) +
        # top-half sector (+10) = 60 -- ALERT_WATCHLIST-grade (40-64) by
        # score alone, with zero pattern fields set.
        candidate = _candidate(RS_Rating=100.0, has_active_fvg=True, has_liquidity_sweep=True)
        sector_row = _sector_row(Rank=2, Total_Sectors=10)  # top half

        result = categorize(candidate, sector_row, market_verdict="FAVORABLE")

        assert result["category"] == "MONITOR"

    def test_execute_grade_no_pattern_becomes_monitor_not_execute(self):
        # Same as above plus institutional sponsorship + buy activity to
        # push comfortably past 65 -- score alone says EXECUTE, but there
        # is still no confirmed pattern anywhere.
        candidate = _candidate(
            RS_Rating=100.0, has_active_fvg=True, has_liquidity_sweep=True,
            institutional_sponsorship_pct=25.0, has_buy_activity=True,
        )
        sector_row = _sector_row(Rank=2, Total_Sectors=10)

        score = compute_score(candidate, sector_row)
        assert score >= 65, "fixture must be EXECUTE-grade by score alone for this test to mean anything"

        result = categorize(candidate, sector_row, market_verdict="FAVORABLE")

        assert result["category"] == "MONITOR"

    def test_favorable_market_does_not_rescue_a_no_pattern_candidate(self):
        # Ceiling is EXECUTE under FAVORABLE (no cap at all) -- MONITOR
        # must still win, since the gate is the pattern, not the regime.
        candidate = _candidate(RS_Rating=100.0, has_active_fvg=True, has_liquidity_sweep=True)
        sector_row = _sector_row(Rank=2, Total_Sectors=10)

        result = categorize(candidate, sector_row, market_verdict="FAVORABLE")

        assert result["category"] == "MONITOR"

    def test_pattern_confirmed_candidate_is_unaffected(self):
        candidate = _candidate(is_vcp_breakout=True, RS_Rating=80.0)
        sector_row = _sector_row()

        result = categorize(candidate, sector_row, market_verdict="FAVORABLE")

        assert result["category"] in ("ALERT_WATCHLIST", "EXECUTE")

    def test_monitor_still_gets_a_real_priced_trade_plan_not_none(self):
        # Unlike AVOID, MONITOR is a real (if unconfirmed) setup -- it
        # still gets entry/stop/target pricing (ATR fallback, no pattern
        # to price off), just never surfaced as an actionable signal.
        candidate = _candidate(RS_Rating=100.0, has_active_fvg=True, has_liquidity_sweep=True)
        sector_row = _sector_row(Rank=2, Total_Sectors=10)

        result = categorize(candidate, sector_row, market_verdict="FAVORABLE")

        assert result["category"] == "MONITOR"
        assert result["entry"] is not None
        assert result["stop_loss"] is not None
        assert result["target"] is not None

    def test_category_rank_orders_monitor_between_avoid_and_alert_watchlist(self):
        from decision_engine.leadership_decision_engine import CATEGORY_RANK

        assert CATEGORY_RANK["AVOID"] < CATEGORY_RANK["MONITOR"] < CATEGORY_RANK["ALERT_WATCHLIST"] \
            < CATEGORY_RANK["EXECUTE"]


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
