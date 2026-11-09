"""
Falcon -- the one-time half-B confirmation, per docs/halfB_confirmation_preregistration.md.

    python tests/run_halfB_confirmation.py > data/halfB_confirmation.log
"""
import sys
sys.path.insert(0, ".")

import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES, run_fm
from backtesting.falcon_momentum_entries import run_fm_entries
from backtesting.fixed_bracket import entries_s, entries_s_range
from backtesting.pit_strategies import equal_weight_universe, run_momentum
from backtesting.s_plus import run_s_plus
from tests.half_a import load_half_a, report
from tests.run_mean_reversion import _nifty
from tests.run_portfolio_combo import combine

PREREG = "docs/halfB_confirmation_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31")}


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    panel = load_half_a("B")
    print(f"half B: {panel.close.shape[1]} stocks", flush=True)
    nifty, src = _nifty()
    ix = pd.read_parquet("data/pit_sources/indices.parquet")
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    fn, fn_rb = entries_s(panel, nifty), entries_s_range(panel, nifty)
    out = open("data/halfB_confirmation_result.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; HALF B (one-time confirmation)\n")
    for w, (a, b) in WINDOWS.items():
        a, b = pd.Timestamp(a), pd.Timestamp(b)
        ew = equal_weight_universe(panel, a, b)
        sleeves = {}
        eq, tr, st = run_fm_entries(panel, a, b, nifty, indices, "closebuy", r_mult=3.0)
        report(out, "FM_C3", w, a, b, eq, tr, nifty, ew, st)
        sleeves["F"] = (eq, tr)
        eq, tr = run_momentum(panel, a, b, stop_pct=0.10)
        report(out, "A10", w, a, b, eq, tr, nifty, ew)
        sleeves["A"] = (eq, tr)
        eq, tr = combine(sleeves, "FA", True)
        report(out, "C_F_A", w, a, b, eq, tr, nifty, ew)
        eq, tr, st = run_fm(panel, a, b, nifty, indices, 40, r_mult=3.0)
        report(out, "FM_REF3", w, a, b, eq, tr, nifty, ew, st)
        eq, tr, st = run_s_plus(panel, a, b, fn, nifty, r_multiple=3.0, market_filter=True)
        report(out, "S3_REF3", w, a, b, eq, tr, nifty, ew, st)
        eq, tr, st = run_s_plus(panel, a, b, fn_rb, nifty, r_multiple=3.0, market_filter=True,
                                close_vol=1.5, clean_close=False, risk=0.02)
        report(out, "RB3_R20", w, a, b, eq, tr, nifty, ew, st)
    out.close()


if __name__ == "__main__":
    main()
