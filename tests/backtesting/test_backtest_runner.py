"""
Test for backtesting/backtest_runner.py -- kept lean per spec: the one
that actually matters, the expectancy formula itself.
"""
from __future__ import annotations

import pytest

from backtesting.backtest_runner import compute_expectancy


class TestExpectancyFormula:

    def test_hand_computed_win_loss_produces_exact_expected_number(self):
        # win_rate=0.6, avg_win=+8.0%, loss_rate=0.4, avg_loss=-3.0%
        # Expectancy = (0.6 * 8.0) + (0.4 * -3.0) = 4.8 - 1.2 = 3.6
        expectancy = compute_expectancy(
            win_rate=0.6, avg_win_pct=8.0, loss_rate=0.4, avg_loss_pct=-3.0
        )

        assert expectancy == pytest.approx(3.6)
