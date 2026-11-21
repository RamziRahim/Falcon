"""Tests for backtesting/wyckoff_swing.py.

    .venv/bin/python -m pytest -v tests/test_wyckoff_swing.py
"""
import sys

sys.path.insert(0, ".")

import numpy as np

from backtesting import wyckoff_swing as W


def walk(n=1500, seed=5, drift=0.0007):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(drift, 0.017, n)))
    o = np.r_[c[0], c[:-1]] * (1 + rng.normal(0, 0.004, n))
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.008, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.008, n)))
    return o, h, l, c


def test_break_of_structure_on_a_simple_zigzag():
    # up 100 -> 110, pull back to 104, close above 110: one continuation break up, protected low 104
    c = np.array([100, 102, 104, 106, 108, 110, 108, 106, 104, 106, 108, 111, 112], float)
    h, l = c + 0.2, c - 0.2
    ev, mode, slv, _ = W.swing_machine(h, l, c)
    ups = [e for e in ev if e["kind"] == "up"]
    assert len(ups) == 1 and ups[0]["t"] == 11
    assert abs(ups[0]["broken"] - 110.2) < 1e-9 and abs(ups[0]["prot"] - 103.8) < 1e-9
    assert mode[-1] == 1 and abs(slv[-1] - 103.8) < 1e-9


def test_no_later_data_used():
    o, h, l, c = walk()
    atr = W.wilder_atr(h, l, c)
    ev, _, _, _ = W.swing_machine(h, l, c)
    full = W.stock_candidates(o, h, l, c, ev, atr)
    assert sum(1 for x in full if x["kind"] == "WY") >= 3
    for cut in (600, 900, 1300):
        o2, h2, l2, c2 = o[:cut + 1], h[:cut + 1], l[:cut + 1], c[:cut + 1]
        ev2, _, _, _ = W.swing_machine(h2, l2, c2)
        part = W.stock_candidates(o2, h2, l2, c2, ev2, W.wilder_atr(h2, l2, c2))
        key = lambda x: (x["kind"], x["bos_t"], x["t"], round(x["fill"], 8), round(x["stop"], 8), round(x["t1"], 8))
        assert sorted(map(key, (x for x in full if x["t"] <= cut))) == sorted(map(key, part))


def test_candidate_levels_follow_the_rules():
    o, h, l, c = walk(seed=9)
    atr = W.wilder_atr(h, l, c)
    ev, _, _, _ = W.swing_machine(h, l, c)
    for x in W.stock_candidates(o, h, l, c, ev, atr):
        assert x["stop"] < x["fill"] and (x["fill"] - x["stop"]) / x["fill"] <= W.MAX_STOP + 1e-12
        assert x["t1"] >= x["fill"] + W.T1_R * (x["fill"] - x["stop"]) - 1e-9
        if x["kind"] == "WY":
            assert x["t"] > x["bos_t"] + 2
            assert l[x["t"]] - 1e-9 <= x["fill"] <= h[x["t"]] + 1e-9      # a buy-stop fills inside the bar
