"""
Tests for technical_analysis/candidate_table_builder.py — extracted verbatim
from app.py's inline candidate-table assembly loop (Falcon spec).
"""
from __future__ import annotations

import pandas as pd
import pytest

import technical_analysis.candidate_table_builder as builder
from technical_analysis.candidate_table_builder import _derive_status, build_candidate_table


def _pattern_frame(**overrides) -> pd.DataFrame:
    row = {
        "Close": 1500.5,
        "Trend_State": "UPTREND",
        "VCP_Score": 90.5,
        "Is_VCP_Breakout": False,
        "Is_Liquidity_Sweep": False,
    }
    row.update(overrides)
    return pd.DataFrame([row])


@pytest.fixture
def pattern_dir(tmp_path, monkeypatch):
    """Points the module's pattern directory at a temp dir instead of data/patterns."""
    monkeypatch.setattr(builder, "PATTERN_DIR", str(tmp_path))
    return tmp_path


class TestStatusDerivation:

    def test_vcp_breakout_wins_over_liquidity_sweep(self):
        row = _pattern_frame(Is_VCP_Breakout=True, Is_Liquidity_Sweep=True).iloc[-1]
        assert _derive_status(row) == "Breakout"

    def test_liquidity_sweep_without_breakout_is_pullback(self):
        row = _pattern_frame(Is_Liquidity_Sweep=True).iloc[-1]
        assert _derive_status(row) == "Pullback"

    def test_neither_flag_is_strong_trend(self):
        row = _pattern_frame().iloc[-1]
        assert _derive_status(row) == "Strong Trend"


class TestRealDataPath:

    def test_assembles_expected_columns_and_values(self, pattern_dir):
        _pattern_frame(Close=1500.5, VCP_Score=90.5, Is_VCP_Breakout=True).to_parquet(
            pattern_dir / "DEMO.NS.parquet"
        )

        df = build_candidate_table(["DEMO.NS"])

        assert list(df.columns) == [
            "Symbol", "Price", "Trend_State", "VCP_Score", "Status",
            "ROCE", "YoY_Rev", "D_E", "Is_Mock_Row",
        ]
        row = df.iloc[0]
        assert row["Symbol"] == "DEMO.NS"
        assert row["Price"] == pytest.approx(1500.5)
        assert row["Trend_State"] == "UPTREND"
        assert row["VCP_Score"] == pytest.approx(90.5)
        assert row["Status"] == "Breakout"
        assert row["Is_Mock_Row"] == False

    def test_ticker_without_a_pattern_file_is_omitted_when_others_have_data(self, pattern_dir):
        _pattern_frame().to_parquet(pattern_dir / "HASDATA.NS.parquet")

        df = build_candidate_table(["HASDATA.NS", "NODATA.NS"])

        assert list(df["Symbol"]) == ["HASDATA.NS"]
        assert not df["Is_Mock_Row"].any()

    def test_empty_pattern_file_is_skipped(self, pattern_dir):
        pd.DataFrame().to_parquet(pattern_dir / "EMPTY.NS.parquet")

        df = build_candidate_table(["EMPTY.NS"])

        assert df.empty is False  # falls back to mock rows, not a crash
        assert df["Is_Mock_Row"].all()


class TestFallbackPath:

    def test_no_pattern_files_returns_flagged_mock_rows_not_an_exception(self, pattern_dir):
        df = build_candidate_table(["A.NS", "B.NS"])

        assert not df.empty
        assert df["Is_Mock_Row"].all()
        assert list(df["Symbol"]) == ["A.NS", "B.NS"]

    def test_mock_rows_capped_at_five(self, pattern_dir):
        universe = [f"T{i}.NS" for i in range(10)]

        df = build_candidate_table(universe)

        assert len(df) == 5
