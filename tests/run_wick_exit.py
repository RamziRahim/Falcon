"""
Falcon -- wick exit for buy-stop entries + FM_C3/A10 pair, half A, per docs/wick_exit_preregistration.md.

    python tests/run_wick_exit.py [W1 ...] > data/wick_exit.log
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES
from backtesting.falcon_momentum_entries import run_fm_entries
from backtesting.falcon_salvage import run_setups
from backtesting.fixed_bracket import entries_s, entries_s_range
from backtesting.pit_strategies import equal_weight_universe, run_momentum
from backtesting.s_plus import run_s_plus
from tests.half_a import load_half_a, report
from tests.run_mean_reversion import _nifty
from tests.run_portfolio_combo import combine

PREREG = "docs/wick_exit_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31")}
ONLY = sys.argv[1:]


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    panel = load_half_a()
    nifty, src = _nifty()
    ix = pd.read_parquet("data/pit_sources/indices.parquet")
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    fn, fn_rb = entries_s(panel, nifty), entries_s_range(panel, nifty)
    su = pd.read_parquet("data/falcon_salvage_setups_halfA.parquet")
    out = open("data/wick_exit_result.txt" if not ONLY else "data/wick_exit_smoke.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; half A; wick exit + pair\n")
    for w, (a, b) in WINDOWS.items():
        if ONLY and w not in ONLY:
            continue
        a, b = pd.Timestamp(a), pd.Timestamp(b)
        ew = equal_weight_universe(panel, a, b)
        for code, wx, cd in (("S3_REF3", False, 0), ("S3_WX", True, 0), ("S3_WXC", True, 20)):
            eq, tr, st = run_s_plus(panel, a, b, fn, nifty, r_multiple=3.0, market_filter=True, wick_exit=wx, cooldown=cd)
            report(out, code, w, a, b, eq, tr, nifty, ew, st)
        for code, wx, cd in (("FM_H3", False, 0), ("FM_WX", True, 0), ("FM_WXC", True, 20)):
            eq, tr, st = run_fm_entries(panel, a, b, nifty, indices, "high20", r_mult=3.0, wick_exit=wx, cooldown=cd)
            report(out, code, w, a, b, eq, tr, nifty, ew, st)
        if w != "Y2018":
            for code, mom, wx in (("F_REF", False, False), ("F_REF_WX", False, True),
                                  ("F_MOM", True, False), ("F_MOM_WX", True, True)):
                s_ = su[su.mom_rank >= 0.80] if mom else su
                eq, tr, st = run_setups(panel, s_, a, b, "pivot_stop", "falcon", "falcon", wick_exit=wx)
                report(out, code, w, a, b, eq, tr, nifty, ew, st)
        sleeves = {}
        eq, tr, st = run_fm_entries(panel, a, b, nifty, indices, "closebuy", r_mult=3.0)
        report(out, "FM_C3", w, a, b, eq, tr, nifty, ew, st)
        sleeves["F"] = (eq, tr)
        eq, tr = run_momentum(panel, a, b, stop_pct=0.10)
        report(out, "A10", w, a, b, eq, tr, nifty, ew)
        sleeves["A"] = (eq, tr)
        eq, tr, st = run_s_plus(panel, a, b, fn_rb, nifty, r_multiple=3.0, market_filter=True,
                                close_vol=1.5, clean_close=False, risk=0.02)
        report(out, "RB3_R20", w, a, b, eq, tr, nifty, ew, st)
        sleeves["R"] = (eq, tr)
        for code, codes in (("C_F_A", "FA"), ("C_F_A_R", "FAR")):
            eq, tr = combine(sleeves, codes, True)
            report(out, code, w, a, b, eq, tr, nifty, ew)
    out.close()


if __name__ == "__main__":
    main()
