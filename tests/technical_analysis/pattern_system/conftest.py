"""
Shared fixtures for technical_analysis/pattern_system/ tests — hand-built,
known-shape synthetic data (no real market data), mirroring the scoring/
test pattern. Every numeric fixture here was verified against the actual
detector output before being locked in as a "known answer" (see the
individual test docstrings for what each fixture is meant to prove).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from technical_analysis.pattern_system.models import SwingPoint, VCPContraction


def _ohlcv_df(closes, volumes=None, dates=None, volume_sma_20=None) -> pd.DataFrame:
    """Minimal OHLCV frame: Open=High=Low=Close (only Close/Volume/Date matter
    to the detectors that consume whole dataframes rather than pivot lists)."""
    n = len(closes)
    df = pd.DataFrame({
        "Date": dates if dates is not None else pd.date_range("2024-01-01", periods=n, freq="D"),
        "Open": closes,
        "High": closes,
        "Low": closes,
        "Close": closes,
        "Volume": volumes if volumes is not None else [100_000] * n,
    })
    if volume_sma_20 is not None:
        df["Volume_SMA_20"] = volume_sma_20
    return df


def zigzag_df(pivots, bars_between=6) -> pd.DataFrame:
    """
    Builds a real OHLC dataframe from a list of zigzag turning-point prices,
    linearly interpolating `bars_between` bars between each pair. With
    bars_between >= window + 1 on both approach and departure legs, fractal
    detection finds a pivot at exactly each turning-point bar for both the
    window=2 (micro) and window=5 (macro) detectors — verified empirically,
    not just asserted.
    """
    closes = []
    for i in range(len(pivots) - 1):
        a, b = pivots[i], pivots[i + 1]
        seg = list(np.linspace(a, b, bars_between + 1))
        if i > 0:
            seg = seg[1:]
        closes.extend(seg)

    closes = np.array(closes)
    n = len(closes)
    return pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=n, freq="D"),
        "Open": closes,
        "High": closes * 1.001,
        "Low": closes * 0.999,
        "Close": closes,
        "Volume": [100_000] * n,
    })


# --------------------------------------------------------------------------- #
# VCP detector fixtures
# --------------------------------------------------------------------------- #
# analyze_vcp(df, micro_pivots, trend_state) takes the pivot list directly,
# so these hand-build exact SwingPoints (precise, deterministic depths)
# rather than fighting fractal auto-detection for exact percentages.

@pytest.fixture
def synthetic_vcp_uptrend_pivots() -> list[SwingPoint]:
    """3 tightening waves: 20% -> 12% -> 6% depth. The 'everything should
    fire' shape (paired with trend_state='UPTREND' in the test)."""
    return [
        SwingPoint(index=0, date="d0", price=100.0, type="HIGH", is_higher=True),
        SwingPoint(index=5, date="d5", price=80.0, type="LOW", is_higher=True),    # depth 20%
        SwingPoint(index=10, date="d10", price=95.0, type="HIGH", is_higher=True),
        SwingPoint(index=15, date="d15", price=83.6, type="LOW", is_higher=True),  # depth 12%
        SwingPoint(index=20, date="d20", price=90.0, type="HIGH", is_higher=True),
        SwingPoint(index=25, date="d25", price=84.6, type="LOW", is_higher=True),  # depth 6%
    ]


@pytest.fixture
def synthetic_vcp_uptrend_df() -> pd.DataFrame:
    """Companion df for synthetic_vcp_uptrend_pivots. 22 bars: a stable
    volume baseline (100,000), then two very quiet days (20,000 each) right
    before the breakout bar (200,000, a volume spike). This is deliberate:
    VDU looks at the trailing 3-day average (which *includes* the breakout
    day), while breakout confirmation looks at that same day's volume in
    isolation -- the two quiet days keep the 3-day average low enough to
    still confirm VDU (80,000 < 97,000 baseline) even though the breakout
    day itself spikes far above the 1.5x threshold (200,000 >= 145,500)."""
    closes = [90.0] * 21 + [96.0]
    volumes = [100_000] * 19 + [20_000, 20_000, 200_000]
    return _ohlcv_df(closes, volumes)


@pytest.fixture
def synthetic_vcp_downtrend_pivots(synthetic_vcp_uptrend_pivots) -> list[SwingPoint]:
    """Identical contraction shape to the uptrend fixture -- only trend_state
    (passed separately in the test) differs. Regression fixture for #1."""
    return synthetic_vcp_uptrend_pivots


@pytest.fixture
def synthetic_widening_waves_pivots() -> list[SwingPoint]:
    """Waves getting wider each time: 8% -> 15% -> 25%. Not a VCP at all,
    regardless of trend."""
    return [
        SwingPoint(index=0, date="d0", price=100.0, type="HIGH", is_higher=True),
        SwingPoint(index=5, date="d5", price=92.0, type="LOW", is_higher=True),    # depth 8%
        SwingPoint(index=10, date="d10", price=98.0, type="HIGH", is_higher=True),
        SwingPoint(index=15, date="d15", price=83.3, type="LOW", is_higher=True),  # depth 15%
        SwingPoint(index=20, date="d20", price=96.0, type="HIGH", is_higher=True),
        SwingPoint(index=25, date="d25", price=72.0, type="LOW", is_higher=True),  # depth 25%
    ]


@pytest.fixture
def synthetic_widening_waves_df() -> pd.DataFrame:
    closes = [90.0] * 20 + [96.0]
    return _ohlcv_df(closes)


@pytest.fixture
def synthetic_breakout_pivots() -> list[SwingPoint]:
    """2 contracting waves (20% -> 10%), resistance pivot at 95.0."""
    return [
        SwingPoint(index=0, date="d0", price=100.0, type="HIGH", is_higher=True),
        SwingPoint(index=5, date="d5", price=80.0, type="LOW", is_higher=True),   # depth 20%
        SwingPoint(index=10, date="d10", price=95.0, type="HIGH", is_higher=True),
        SwingPoint(index=15, date="d15", price=85.5, type="LOW", is_higher=True),  # depth 10%
    ]


@pytest.fixture
def synthetic_breakout_with_volume_df() -> pd.DataFrame:
    """Close breaks above the 95.0 resistance pivot with volume >= 1.5x the
    20-bar baseline (no explicit Volume_SMA_20 column -> exercises the
    rolling(20).mean() fallback). Baseline works out to 105,000, so 200,000
    clears the 1.5x (157,500) threshold."""
    closes = [90.0] * 24 + [100.0]
    volumes = [100_000] * 24 + [200_000]
    return _ohlcv_df(closes, volumes)


@pytest.fixture
def synthetic_breakout_no_volume_df() -> pd.DataFrame:
    """Same price breakout above 95.0, but normal (non-expansion) volume.
    Baseline works out to 100,500; 110,000 falls short of the 1.5x
    (150,750) threshold."""
    closes = [90.0] * 24 + [100.0]
    volumes = [100_000] * 24 + [110_000]
    return _ohlcv_df(closes, volumes)


@pytest.fixture
def synthetic_breakout_explicit_volume_sma_df() -> pd.DataFrame:
    """Same breakout price action, but supplies an explicit Volume_SMA_20
    column deliberately DIFFERENT from what a naive rolling(20).mean() of
    Volume would produce -- proves the code reads the existing column
    rather than silently recomputing it. A naive recompute of the last 20
    Volume values here would NOT confirm (baseline 102,000, threshold
    153,000 > 140,000 latest volume); the explicit column (60,000) does
    confirm (threshold 90,000 < 140,000)."""
    closes = [90.0] * 24 + [100.0]
    volumes = [100_000] * 24 + [140_000]
    sma = [100_000.0] * 24 + [60_000.0]
    return _ohlcv_df(closes, volumes, volume_sma_20=sma)


# --------------------------------------------------------------------------- #
# FVG detector fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def synthetic_fvg_gap_up_df() -> pd.DataFrame:
    """Candle1(idx0).High=100 < Candle3(idx2).Low=105 -> gap [100, 105].
    Built so no other 3-candle window in the frame incidentally forms a
    second gap (verified against the real detector)."""
    rows = [
        {"High": 100, "Low": 95, "Close": 98},
        {"High": 102, "Low": 99, "Close": 101},
        {"High": 108, "Low": 105, "Close": 107},
        {"High": 110, "Low": 101, "Close": 109},
        {"High": 112, "Low": 106, "Close": 111},
    ]
    df = pd.DataFrame(rows)
    df["Date"] = pd.date_range("2024-01-01", periods=len(df), freq="D")
    df["Open"] = df["Close"]
    df["Volume"] = 100_000
    return df


@pytest.fixture
def synthetic_fvg_mitigated_df(synthetic_fvg_gap_up_df) -> pd.DataFrame:
    """Same gap as synthetic_fvg_gap_up_df, plus a later candle whose Low
    (98) dips back into the [100, 105] gap zone, mitigating it."""
    df = synthetic_fvg_gap_up_df.copy()
    extra = pd.DataFrame([{
        "Date": df["Date"].iloc[-1] + pd.Timedelta(days=1),
        "Open": 99, "High": 100, "Low": 98, "Close": 99, "Volume": 100_000,
    }])
    return pd.concat([df, extra], ignore_index=True)


# --------------------------------------------------------------------------- #
# Swing detector fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def synthetic_swing_points_df() -> pd.DataFrame:
    """Zigzag 100 -> 80 -> 95 -> 70 -> 110, bars_between=3 (>= window+1 for
    window=2). Verified pivots (window=2): LOW@3 (79.92), HIGH@6 (95.095),
    LOW@9 (69.93)."""
    return zigzag_df([100, 80, 95, 70, 110], bars_between=3)


@pytest.fixture
def synthetic_tied_high_df() -> pd.DataFrame:
    """Two adjacent bars tied at the peak (100, 100) -- regression fixture
    for the asymmetric >=/<= vs >/< boundary bug."""
    closes = [80, 85, 90, 95, 100, 100, 95, 90, 85, 80]
    return _ohlcv_df(closes)


@pytest.fixture
def synthetic_too_short_df() -> pd.DataFrame:
    """3 bars -- shorter than window*2+1 for window=2 (needs 5). No crash,
    empty/default results expected from every detector."""
    return _ohlcv_df([100.0, 101.0, 99.0])


# --------------------------------------------------------------------------- #
# Market structure fixtures
# --------------------------------------------------------------------------- #
# analyze_structure(df, macro_pivots) takes the pivot list directly, so
# trend-classification fixtures hand-build the (only two) pivots that
# matter -- the last HIGH and last LOW and their is_higher flags.

@pytest.fixture
def synthetic_uptrend_structure_pivots() -> list[SwingPoint]:
    return [
        SwingPoint(index=0, date="d0", price=90.0, type="HIGH", is_higher=False),
        SwingPoint(index=1, date="d1", price=70.0, type="LOW", is_higher=False),
        SwingPoint(index=2, date="d2", price=120.0, type="HIGH", is_higher=True),   # HH
        SwingPoint(index=3, date="d3", price=90.0, type="LOW", is_higher=True),     # HL
    ]


@pytest.fixture
def synthetic_downtrend_structure_pivots() -> list[SwingPoint]:
    return [
        SwingPoint(index=0, date="d0", price=120.0, type="HIGH", is_higher=True),
        SwingPoint(index=1, date="d1", price=90.0, type="LOW", is_higher=True),
        SwingPoint(index=2, date="d2", price=100.0, type="HIGH", is_higher=False),  # LH
        SwingPoint(index=3, date="d3", price=70.0, type="LOW", is_higher=False),    # LL
    ]


@pytest.fixture
def synthetic_choppy_structure_pivots() -> list[SwingPoint]:
    return [
        SwingPoint(index=0, date="d0", price=90.0, type="HIGH", is_higher=False),
        SwingPoint(index=1, date="d1", price=70.0, type="LOW", is_higher=False),
        SwingPoint(index=2, date="d2", price=120.0, type="HIGH", is_higher=True),   # HH
        SwingPoint(index=3, date="d3", price=60.0, type="LOW", is_higher=False),    # LL (mixed)
    ]


@pytest.fixture
def synthetic_structure_support_df() -> pd.DataFrame:
    """Boring 15-bar df (no sweep, no BOS) for isolating trend classification."""
    return _ohlcv_df([100.0] * 15, volume_sma_20=[100_000.0] * 15)


@pytest.fixture
def synthetic_liquidity_sweep_sellside_df() -> pd.DataFrame:
    """15 bars; bar 12 dips Low=85 below the macro low (90), closes back
    above it (95), on 2x volume -- SELLSIDE sweep."""
    df = _ohlcv_df([100.0] * 15, volume_sma_20=[100_000.0] * 15)
    df.loc[12, "Low"] = 85.0
    df.loc[12, "Close"] = 95.0
    df.loc[12, "Volume"] = 200_000
    return df


@pytest.fixture
def synthetic_liquidity_sweep_buyside_df() -> pd.DataFrame:
    """15 bars; bar 12 pokes High=125 above the macro high (120), closes
    back below it (110), on 2x volume -- BUYSIDE sweep."""
    df = _ohlcv_df([100.0] * 15, volume_sma_20=[100_000.0] * 15)
    df.loc[12, "High"] = 125.0
    df.loc[12, "Close"] = 110.0
    df.loc[12, "Volume"] = 200_000
    return df


@pytest.fixture
def synthetic_sweep_macro_pivots() -> list[SwingPoint]:
    """Shared macro context for the two sweep fixtures: support=90, resistance=120."""
    return [
        SwingPoint(index=0, date="d0", price=90.0, type="LOW", is_higher=True),
        SwingPoint(index=1, date="d1", price=120.0, type="HIGH", is_higher=True),
    ]
