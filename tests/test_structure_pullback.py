"""Tests for backtesting/structure_pullback.py.

    .venv/bin/python -m pytest -v tests/test_structure_pullback.py
"""
import sys

sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from backtesting import structure_pullback as SP
from technical_analysis.pattern_system_v3 import engine as E


def walk(n=900, seed=3):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0.0006, 0.018, n)))
    o = np.r_[c[0], c[:-1]] * (1 + rng.normal(0, 0.004, n))
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.008, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.008, n)))
    return o, h, l, c


def test_zigzag_matches_v3_engine():
    for seed in (1, 2, 3, 4):
        o, h, l, c = walk(seed=seed)
        df = E.prepare_indicators(pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c, "Volume": 1e6}))
        ref = [(p.idx, round(p.price, 8), 1 if p.kind == "HIGH" else -1) for p in E.detect_atr_zigzag(df) if p.confirmed]
        got = [(i, round(p, 8), k) for i, p, k, _ in SP.zigzag_confirmed(h, l, SP.wilder_atr(h, l, c))]
        assert got == ref
        assert all(ci >= i for i, _, _, ci in SP.zigzag_confirmed(h, l, SP.wilder_atr(h, l, c)))


def test_signals_use_no_later_data():
    o, h, l, c = walk(n=1200, seed=7)
    full, _ = SP.stock_signals(o, h, l, c)
    assert len(full) > 5
    for t in (500, 800, 1100):
        cut, _ = SP.stock_signals(o[:t + 1], h[:t + 1], l[:t + 1], c[:t + 1])
        a = [(x["r"], x["setup"], round(x["stop"], 8)) for x in full if x["r"] <= t]
        b = [(x["r"], x["setup"], round(x["stop"], 8)) for x in cut]
        assert a == b


def _tcr_series():
    """Rising 200-day trend, then a short downtrend 100 -> 92 (H1), 92 -> 84 (L1), lower high 90 (H2),
    lower low 82 (L2), break above 90, dip back to 90.2, turn up."""
    legs = [(0, 40.0), (260, 100.0), (272, 84.0), (282, 90.0), (292, 82.0), (300, 92.5), (305, 90.4), (306, 92.0)]
    idx, px = zip(*legs)
    c = np.interp(np.arange(idx[-1] + 1), idx, px)
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * 1.004
    l = np.minimum(o, c) * 0.996
    return o, h, l, c


def test_trend_change_retest_fires():
    """Rule 5 counts a touch on any session after the break, so here the entry comes two
    sessions after the break (the session after the break dips within 0.5 ATR of H2)."""
    o, h, l, c = _tcr_series()
    sig, cnt = SP.stock_signals(o, h, l, c)
    tcr = [x for x in sig if x["setup"] == "TCR"]
    assert cnt["tcr_breaks"] == 1
    assert len(tcr) == 1
    b = int(np.argmax(c[294:] > h[283])) + 294            # first close above H2 (swing high at 283)
    r = tcr[0]["r"]
    assert b < r <= b + SP.RETEST_WIN
    atr = SP.wilder_atr(h, l, c)
    assert abs(tcr[0]["stop"] - (l[b:r + 1].min() - 0.5 * atr[r])) < 1e-9
    assert c[r] > h[r - 1] and c[r] > h[283]
