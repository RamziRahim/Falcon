"""Tests for backtesting/mtm_portfolio.py -- the daily mark-to-market ledger
added 2026-10-20 (see its module docstring)."""
from __future__ import annotations

import pandas as pd
import pytest

from backtesting.mtm_portfolio import CostModel, simulate_portfolio_mtm

FREE = CostModel(statutory=0.0, spread_tiers=((0, 0.0),), impact_coeff=0.0)


def _history(closes, start="2024-01-01", volume=1_000_000):
    dates = pd.bdate_range(start, periods=len(closes))
    return pd.DataFrame({"Date": dates, "Close": closes, "Volume": [volume] * len(closes)})


def _episode(ticker, start, end, gross, stop_pct=10.0):
    return {"ticker": ticker, "episode_start_date": pd.Timestamp(start), "episode_end_date": pd.Timestamp(end),
            "gross_return_pct": gross, "stop_pct": stop_pct, "category": "EXECUTE"}


def _full(_):
    return 1.0


class TestLedger:

    def test_single_winning_trade_moves_equity_by_weight_times_return(self):
        h = _history([100, 100, 105, 110, 110])
        ep = pd.DataFrame([_episode("A", "2024-01-01", "2024-01-04", 10.0, stop_pct=10.0)])  # 1% risk / 10% stop = 10% of equity

        r = simulate_portfolio_mtm(ep, _full, {"A": h}, cost_model=FREE)

        assert r.summary["total_return_pct"] == pytest.approx(1.0)       # 10% position x +10%
        assert r.trades["fraction_of_equity"].iloc[0] == pytest.approx(0.10)

    def test_intra_trade_dip_shows_as_drawdown_even_though_trade_wins(self):
        # Exit-only accounting would show no drawdown at all for this trade.
        h = _history([100, 100, 80, 80, 110])
        ep = pd.DataFrame([_episode("A", "2024-01-01", "2024-01-05", 10.0, stop_pct=5.0)])  # 20% of equity

        r = simulate_portfolio_mtm(ep, _full, {"A": h}, cost_model=FREE)

        assert r.summary["max_drawdown_pct"] == pytest.approx(-4.0)       # 20% position x -20%
        assert r.summary["total_return_pct"] == pytest.approx(2.0)


class TestExposureCap:

    def test_positions_are_scaled_to_fit_the_account(self):
        # Each wants 1% / 1% stop = 100% of equity; the second gets nothing left.
        h = _history([100] * 6)
        eps = pd.DataFrame([_episode("A", "2024-01-01", "2024-01-05", 0.0, stop_pct=1.0),
                            _episode("B", "2024-01-02", "2024-01-05", 0.0, stop_pct=1.0)])

        r = simulate_portfolio_mtm(eps, _full, {"A": h, "B": h}, cost_model=FREE)

        assert r.summary["max_gross_exposure_pct"] <= 100.0 + 1e-9
        assert r.summary["n_missed_exposure_cap"] == 1

    def test_partial_room_scales_the_position_down(self):
        h = _history([100] * 6)
        eps = pd.DataFrame([_episode("A", "2024-01-01", "2024-01-05", 0.0, stop_pct=1.5),   # wants 66.7%
                            _episode("B", "2024-01-02", "2024-01-05", 0.0, stop_pct=1.5)])  # wants 66.7%, room 33.3%

        r = simulate_portfolio_mtm(eps, _full, {"A": h, "B": h}, cost_model=FREE)

        assert r.trades["fraction_of_equity"].iloc[1] == pytest.approx(1 / 3, rel=1e-6)
        assert r.summary["n_scaled_down_by_cap"] == 1


class TestCosts:

    def test_illiquid_stock_costs_more_than_liquid_one(self):
        m = CostModel()
        liquid = m.per_side(100_000, 5_000_000_000)     # Rs 500 cr/day
        illiquid = m.per_side(100_000, 20_000_000)      # Rs 2 cr/day
        assert illiquid > liquid
        assert liquid == pytest.approx(m.statutory + 0.0003 + m.impact_coeff * (100_000 / 5_000_000_000) ** 0.5)

    def test_costs_reduce_a_flat_trade_below_zero(self):
        h = _history([100] * 6, volume=10_000)            # tiny traded value -> highest tier
        ep = pd.DataFrame([_episode("A", "2024-01-01", "2024-01-05", 0.0)])

        r = simulate_portfolio_mtm(ep, _full, {"A": h})

        assert r.summary["total_return_pct"] < 0
        assert r.trades["exit_cost"].iloc[0] > 0
