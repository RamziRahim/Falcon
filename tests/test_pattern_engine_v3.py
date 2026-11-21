"""
Unit tests for technical_analysis/pattern_system_v3/engine.py, on synthetic daily OHLCV.

Acceptance list from PATTERN_ENGINE_SPEC.md (1-5) plus a no-future-data test (6).
Every fixture is a deterministic path of closes built from straight-line legs, with a
fixed daily range, so pivots and depths are known exactly.

    .venv/bin/python -m pytest -v tests/test_pattern_engine_v3.py
"""
import sys

sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from technical_analysis.pattern_system_v3 import engine as E

UPTREND = [(0, 50.0), (240, 100.0)]            # 240 sessions from 50 to 100: Stage 2 by the scan day
RUNUP = [(0, 50.0), (200, 78.0), (240, 100.0)]  # same, with a +28% run in the last 40 sessions


def build(legs, rng_pct=0.008, vol=1_000_000.0, vol_legs=None, last_bar=None):
    """legs: [(session_index, close)] waypoints, linearly joined. vol_legs: [(start, end, multiple)]
    sets Volume = vol * multiple on sessions start..end-1. last_bar: dict overriding the final row."""
    idx, px = zip(*legs)
    n = idx[-1] + 1
    close = np.interp(np.arange(n), idx, px)
    openp = np.r_[close[0], close[:-1]]
    half = close * rng_pct / 2
    high = np.maximum(openp, close) + half
    low = np.minimum(openp, close) - half
    volume = np.full(n, vol)
    for a, b, m in vol_legs or []:
        volume[a:b] = vol * m
    df = pd.DataFrame({"Open": openp, "High": high, "Low": low, "Close": close, "Volume": volume})
    if last_bar:
        for k, v in last_bar.items():
            df.loc[n - 1, k] = v
    return df


def shift(legs, start):
    return [(start + i, p) for i, p in legs]


# --- fixtures -----------------------------------------------------------------------------

def vcp_df(**kw):
    """Uptrend to 100, then three contractions -18% -> -9% -> -4% under a flat 100 ceiling,
    finishing at 98.5 on quiet volume."""
    base = shift([(0, 100.0), (14, 82.0), (28, 100.0), (38, 91.0), (48, 100.0), (54, 96.0), (60, 98.5)], 240)
    return build(UPTREND + base[1:], vol_legs=[(288, 301, 0.6)], **kw)


def triangle_df():
    """Three touches of 100 with rising lows 85 -> 91 -> 95, finishing at 98.5."""
    base = shift([(0, 100.0), (12, 85.0), (24, 100.0), (34, 91.0), (44, 100.0), (51, 95.0), (58, 98.5)], 240)
    return build(UPTREND + base[1:], vol_legs=[(286, 299, 0.6)])


def bull_flag_df():
    """Uptrend to 100, 10-session pole to 120 on 2x volume, 8-session flag down to 114.5 on
    light volume, finishing at 117."""
    legs = UPTREND + [(250, 120.0), (256, 114.5), (258, 117.0)]
    return build(legs, vol_legs=[(241, 251, 2.0), (251, 259, 0.5)])


def cup_df():
    """Rounded 14% cup from a 100 lip (left lip in the first 20 sessions of the window),
    right lip 99, 10-session handle down to 95, finishing at 97.5. A steep 30-to-100 run
    keeps the 50-day average above the 150-day through the cup (a 20% cup over 70
    sessions fails the spec's Stage 2 stack; see docs/falcon_pattern_audit.md)."""
    t0 = 240
    n_cup = 70
    x = np.linspace(-1, 1, 51)
    bowl = 86 + 14 * x ** 2                                  # U shape from 100 down to 86 and back
    legs = [(0, 30.0), (t0, 100.0)] + [(t0 + 2, 100.0)] + [(t0 + 12 + i, float(bowl[i])) for i in range(51)]
    legs += [(t0 + n_cup - 1, 99.0), (t0 + n_cup + 5, 95.0), (t0 + n_cup + 9, 97.5)]
    return build(legs, vol_legs=[(t0 + n_cup, t0 + n_cup + 10, 0.6)])


def v_cup_df():
    """Same lips and depth as cup_df but a sharp V: the price holds near the lip, plunges to 86
    and snaps back within 12 sessions, so under 35% of the cup's closes are in its lower half."""
    t0 = 240
    legs = [(0, 30.0), (t0, 100.0), (t0 + 2, 100.0), (t0 + 30, 98.0), (t0 + 36, 86.0), (t0 + 42, 97.0),
            (t0 + 69, 99.0), (t0 + 75, 95.0), (t0 + 79, 97.5)]
    return build(legs, vol_legs=[(t0 + 70, t0 + 80, 0.6)])


def flat_base_df(box_low=94.0, rng_pct=0.008):
    """Uptrend to 100, then a 25-session box between 100 and box_low with two equal swings,
    finishing at 98.5."""
    base = shift([(0, 100.0), (5, box_low), (10, 99.5), (15, box_low), (20, 98.0), (24, 98.5)], 240)
    return build(RUNUP + base[1:], rng_pct=rng_pct, vol_legs=[(255, 265, 0.6)])


def stage4_df():
    """Downtrend from 100 to 60 below a falling 200-day average, ending in a tight triangle."""
    legs = [(0, 100.0), (240, 60.0), (250, 63.0), (256, 59.0), (262, 63.0), (267, 60.5), (272, 63.0), (276, 61.5)]
    return build(legs)


# --- 1. Stage 1 / Stage 4 rejection ---------------------------------------------------------

def test_stage4_downtrend_rejected_even_with_tight_triangle():
    sig = E.classify_nse_stock(stage4_df())
    assert sig.verdict == "NOT_A_PATTERN"
    assert sig.pattern_type == "NONE"
    assert any("MA stack" in n or "200-day" in n for n in sig.notes)


# --- 2. Positive patterns -------------------------------------------------------------------

def _real(df, pattern, pivot, stop_from_low):
    sig = E.classify_nse_stock(df)
    assert sig.verdict == "REAL_PATTERN", (sig.verdict, sig.pattern_type, sig.notes)
    assert sig.pattern_type == pattern, (sig.pattern_type, sig.notes)
    d = E.prepare_indicators(df)
    atr = float(d["ATR_14"].iloc[-1])
    assert abs(sig.breakout_level - pivot) <= 0.01 * pivot
    assert abs(sig.stop_loss - (stop_from_low - 0.5 * atr)) <= 0.01 * stop_from_low
    return sig


def test_vcp_real():
    df = vcp_df()
    lows = df["Low"]
    _real(df, "VCP", 100.0, float(lows.iloc[288:301].min()))


def test_ascending_triangle_real():
    df = triangle_df()
    _real(df, "ASCENDING_TRIANGLE", 100.0, float(df["Low"].iloc[286:299].min()))


def test_bull_flag_real():
    df = bull_flag_df()
    _real(df, "BULL_FLAG", float(df["High"].iloc[241:251].max()), float(df["Low"].iloc[-8:].min()))


def test_cup_with_handle_real():
    df = cup_df()
    _real(df, "CUP_WITH_HANDLE", float(df["High"].iloc[-80:-60].max()), float(df["Low"].iloc[-10:].min()))


def test_flat_base_real():
    df = flat_base_df()
    _real(df, "FLAT_BASE", float(df["High"].iloc[-25:].max()), float(df["Low"].iloc[-25:].min()))


# --- 3. Anti-V-bottom cup ---------------------------------------------------------------------

def test_v_bottom_cup_rejected():
    d = E.prepare_indicators(v_cup_df())
    assert E._detect_cup_with_handle(d) is None
    assert E._detect_cup_with_handle(E.prepare_indicators(cup_df())) is not None


# --- 4. Right-edge rejection bar --------------------------------------------------------------

def test_heavy_red_rejection_bar_downgraded_to_unsure():
    df = vcp_df(last_bar={"Open": 98.0, "High": 99.8, "Low": 97.4, "Close": 97.6, "Volume": 2_500_000.0})
    sig = E.classify_nse_stock(df)
    assert sig.pattern_type == "VCP", sig.notes
    assert sig.verdict == "UNSURE", sig.notes


# --- 5. Wide stop -----------------------------------------------------------------------------

def wide_base_df():
    """A volatile base (3% daily range) under a 100 ceiling with lows 80 -> 88 -> 92: valid
    geometry, but the structural low plus half an ATR is more than 11.5% below the pivot."""
    base = shift([(0, 100.0), (14, 80.0), (28, 100.0), (38, 88.0), (48, 100.0), (54, 92.0), (60, 97.5)], 240)
    return build(UPTREND + base[1:], rng_pct=0.03, vol_legs=[(288, 301, 0.6)])


def test_wide_stop_rejected():
    sig = E.classify_nse_stock(wide_base_df())
    assert sig.pattern_type != "NONE", sig.notes
    assert sig.risk_pct > 11.5, (sig.risk_pct, sig.notes)
    assert sig.verdict == "NOT_A_PATTERN"
    assert E.detect_pattern(wide_base_df()).risk_ok is False


# --- 6. No future data ------------------------------------------------------------------------

def test_detection_ignores_later_rows():
    df = vcp_df()
    t = len(df) - 1
    rng = np.random.default_rng(0)
    later = build(UPTREND + [(240, 100.0)])[:40].copy()
    later[["Open", "High", "Low", "Close"]] *= rng.uniform(0.5, 1.6, size=(40, 1))
    extended = pd.concat([df, later], ignore_index=True)
    a, b = E.detect_at(df, t), E.detect_at(extended, t)
    assert (a.pattern_type, round(a.breakout_level, 6), round(a.stop_loss, 6)) == \
           (b.pattern_type, round(b.breakout_level, 6), round(b.stop_loss, 6))
    assert a.pattern_type == "VCP"
