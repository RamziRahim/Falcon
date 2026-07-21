"""
Test for backtesting/regime_threshold_calibration.py -- kept lean per
spec: this is a data-analysis function, not decision logic, so it doesn't
need the cascade's depth of coverage, just confirmation the math is right.

Uses a hand-constructed fixture with a KNOWN relationship (VIX rising
linearly, daily price drift made an explicit linear function of that
day's VIX) so the correct decile output is provable, not just plausible --
confirms analyze_vix_vs_forward_returns() actually surfaces a real
monotonic relationship when one exists, rather than only checking it runs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.regime_threshold_calibration import analyze_vix_vs_forward_returns


class TestAnalyzeVixVsForwardReturns:

    def test_known_monotonic_relationship_is_surfaced_by_decile(self):
        n = 300
        forward_days = 20
        dates = pd.date_range("2020-01-01", periods=n, freq="D")

        # VIX ramps smoothly 10 -> 30 across the whole series -- gives 10
        # cleanly distinct deciles, unlike a bimodal low/high split.
        vix = np.linspace(10, 30, n)

        # Each day's drift is an explicit linear function of that day's
        # VIX -- higher VIX means a more negative daily return, by
        # construction, not by chance. Forward return over the next 20
        # days is approximately the sum of 20 such drifts, so it must
        # come out worse for days where VIX (and therefore every nearby
        # day's VIX) is higher.
        daily_return = -0.002 * vix
        close = 100 * np.exp(np.cumsum(daily_return))

        benchmark_history = pd.DataFrame({"Date": dates, "Close": close, "Volume": [100_000] * n})
        vix_history = pd.DataFrame({"Date": dates, "VIX_Level": vix})

        result = analyze_vix_vs_forward_returns(benchmark_history, vix_history, forward_days=forward_days)

        assert len(result) == 10
        assert result["avg_forward_return"].is_monotonic_decreasing
        # Sanity: the lowest-VIX decile should show a clearly positive-
        # relative (i.e. least negative) forward return vs. the highest.
        assert result["avg_forward_return"].iloc[0] > result["avg_forward_return"].iloc[-1]
