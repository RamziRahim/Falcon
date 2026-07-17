"""
Tests for scoring/relative_volume.py
"""
from __future__ import annotations

import numpy as np
import pytest

from scoring.relative_volume import calculate


class TestRelativeVolumeBaseline:

    def test_steady_volume_gives_rvol_near_one(self, synthetic_ohlcv_steady_volume):
        result = calculate(synthetic_ohlcv_steady_volume, lookback=20)
        tail = result["Rel_Vol"].iloc[-5:]
        assert tail.notna().all()
        np.testing.assert_allclose(tail.values, 1.0, rtol=0.01)


class TestRelativeVolumeExcludesCurrentDay:

    def test_spike_day_does_not_dilute_its_own_average(self, synthetic_ohlcv_volume_spike):
        result = calculate(synthetic_ohlcv_volume_spike, lookback=20)
        spike_rvol = result["Rel_Vol"].iloc[-1]
        # 100_000 -> 1_000_000 (10x). If today is correctly excluded from its
        # own rolling average, RVOL should land close to 10.0. If today leaks
        # into its own average, it comes out noticeably diluted (~7-8x).
        assert spike_rvol > 9.0, (
            f"Expected RVOL ~10.0 on the spike day, got {spike_rvol:.2f}. "
            f"Check the .shift(1) in relative_volume.py's rolling average."
        )

    def test_day_before_spike_is_unaffected(self, synthetic_ohlcv_volume_spike):
        result = calculate(synthetic_ohlcv_volume_spike, lookback=20)
        day_before = result["Rel_Vol"].iloc[-2]
        assert 0.9 <= day_before <= 1.1


class TestRelativeVolumeEdgeCases:

    def test_missing_volume_column_raises_clear_error(self, synthetic_ohlcv_steady_volume):
        df_no_volume = synthetic_ohlcv_steady_volume.drop(columns=["Volume"])
        with pytest.raises(KeyError):
            calculate(df_no_volume, lookback=20)
