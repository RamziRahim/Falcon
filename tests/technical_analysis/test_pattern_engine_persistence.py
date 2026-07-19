"""
Plumbing check for pattern_engine.py's column-writing block: confirms the
20 newly persisted columns (2 breakout sub-fields + 1 pivot level + 1
structural low, x5 patterns) actually land on the output parquet with
correct values -- not new detection logic, just verifying the wiring.

Needed for WEAK_VOLUME_CONFIRMATION (can't be computed today without the
granular price_crossed_pivot/breakout_volume_confirmed columns) and for a
future backtest replay engine to reconstruct a historical decision from
parquet alone, without re-running the detectors.

The synthetic fixture below is a real zigzag (two higher-highs, two
higher-lows via genuine fractal swing detection with window=5) so
market_structure_engine actually classifies UPTREND, followed by a tight,
monotonically-rising ~7%-deep base and a confirmed breakout bar -- built
and verified empirically (not guessed) before writing this test, since a
naive flat/constant base creates spurious tied pivots that flip the
trend classification to DOWNTREND (a real footgun found while building
this fixture).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from technical_analysis.pattern_engine import PatternEngine


def _uptrend_flat_base_breakout_df(include_delivery_pct: bool = False) -> pd.DataFrame:
    wave1_down = np.linspace(90, 70, 10)
    wave1_up = np.linspace(71, 95, 10)
    wave2_down = np.linspace(94, 80, 10)
    wave2_up = np.linspace(81, 110, 10)
    base_down = np.linspace(109, 100.5, 6)
    base_rise = np.linspace(101, 108, 25)
    breakout = np.array([125.0])

    closes = np.concatenate([wave1_down, wave1_up, wave2_down, wave2_up, base_down, base_rise, breakout])
    n = len(closes)
    volumes = [100_000] * (n - 1) + [300_000]

    df = pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=n, freq="D"),
        "Open": closes, "High": closes * 1.001, "Low": closes * 0.999, "Close": closes,
        "Volume": volumes, "Volume_SMA_20": [100_000] * n,
    })

    if include_delivery_pct:
        # Deterministic ramp (0, 1, 2, ..., n-1) so the last row's trailing
        # 20-day mean is hand-computable: mean(n-20 .. n-1).
        df["Delivery_Pct"] = np.arange(n, dtype=float)

    return df


NEW_COLUMNS = [
    "VCP_Price_Crossed_Pivot", "VCP_Breakout_Volume_Confirmed",
    "Flat_Base_Price_Crossed_Pivot", "Flat_Base_Breakout_Volume_Confirmed",
    "Cup_Handle_Price_Crossed_Pivot", "Cup_Handle_Breakout_Volume_Confirmed",
    "Ascending_Triangle_Price_Crossed_Pivot", "Ascending_Triangle_Breakout_Volume_Confirmed",
    "Bull_Flag_Price_Crossed_Pivot", "Bull_Flag_Breakout_Volume_Confirmed",
    "VCP_Pivot_Level", "VCP_Structural_Low",
    "Flat_Base_Pivot_Level", "Flat_Base_Low",
    "Cup_Handle_Pivot_Level", "Cup_Handle_Low",
    "Ascending_Triangle_Pivot_Level", "Ascending_Triangle_Support",
    "Bull_Flag_Pivot_Level", "Bull_Flag_Low",
]


class TestPersistedGranularPatternColumns:

    def test_all_20_new_columns_exist_with_correct_values_for_confirmed_flat_base(self, tmp_path):
        src_dir = tmp_path / "technical"
        dest_dir = tmp_path / "patterns"
        src_dir.mkdir()

        df = _uptrend_flat_base_breakout_df()
        df.to_parquet(src_dir / "TESTCO.NS.parquet")

        engine = PatternEngine(src_dir=str(src_dir), dest_dir=str(dest_dir))
        engine.execute_pipeline()

        output = pd.read_parquet(dest_dir / "TESTCO.NS.parquet")
        last_row = output.iloc[-1]

        # All 20 columns present, with no accidental typo/omission.
        for column in NEW_COLUMNS:
            assert column in output.columns, f"missing persisted column: {column}"

        # Flat Base genuinely confirmed a breakout on this fixture --
        # its granular fields must reflect that, not just the combined
        # Is_Flat_Base_Breakout boolean.
        assert last_row["Is_Flat_Base_Breakout"] == True
        assert last_row["Flat_Base_Price_Crossed_Pivot"] == True
        assert last_row["Flat_Base_Breakout_Volume_Confirmed"] == True
        assert last_row["Flat_Base_Pivot_Level"] == pytest.approx(108.108, abs=0.01)
        assert last_row["Flat_Base_Low"] == pytest.approx(100.899, abs=0.01)

        # Cup-Handle never confirms a setup on this fixture (needs 325+
        # days of history) -- its columns should be None, not fabricated.
        assert last_row["Is_Cup_Handle_Setup"] == False
        assert pd.isna(last_row["Cup_Handle_Pivot_Level"])
        assert pd.isna(last_row["Cup_Handle_Low"])


class TestDeliveryPct20dAvg:

    def test_rolling_mean_matches_hand_computed_value(self, tmp_path):
        src_dir = tmp_path / "technical"
        dest_dir = tmp_path / "patterns"
        src_dir.mkdir()

        df = _uptrend_flat_base_breakout_df(include_delivery_pct=True)
        df.to_parquet(src_dir / "TESTCO.NS.parquet")

        engine = PatternEngine(src_dir=str(src_dir), dest_dir=str(dest_dir))
        engine.execute_pipeline()

        output = pd.read_parquet(dest_dir / "TESTCO.NS.parquet")
        last_row = output.iloc[-1]

        # Delivery_Pct is arange(72) = 0..71; the trailing 20-day window
        # at the last row is 52..71, mean = 61.5 -- hand-computed, not
        # asserted against pandas' own rolling() output.
        assert last_row["Delivery_Pct_20d_avg"] == pytest.approx(61.5)

    def test_none_not_crash_when_delivery_pct_column_absent(self, tmp_path):
        src_dir = tmp_path / "technical"
        dest_dir = tmp_path / "patterns"
        src_dir.mkdir()

        # No Delivery_Pct column at all -- e.g. NSE wasn't the active
        # data source for this fetch.
        df = _uptrend_flat_base_breakout_df(include_delivery_pct=False)
        assert "Delivery_Pct" not in df.columns
        df.to_parquet(src_dir / "TESTCO.NS.parquet")

        engine = PatternEngine(src_dir=str(src_dir), dest_dir=str(dest_dir))
        engine.execute_pipeline()  # must not raise

        output = pd.read_parquet(dest_dir / "TESTCO.NS.parquet")
        assert pd.isna(output.iloc[-1]["Delivery_Pct_20d_avg"])
