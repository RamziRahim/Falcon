"""
Falcon -- range breakout at higher risk, and combined with A10 / FM_C3, half A,
per docs/rb_risk_combo_preregistration.md.

    python tests/run_rb_risk_combo.py [W1 ...] > data/rb_risk_combo.log
"""
import sys
sys.path.insert(0, ".")

import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES
from backtesting.falcon_momentum_entries import run_fm_entries
from backtesting.fixed_bracket import entries_s_range
from backtesting.pit_strategies import equal_weight_universe, run_momentum
from backtesting.s_plus import run_s_plus
from tests.half_a import load_half_a, report
from tests.run_mean_reversion import _nifty
from tests.run_portfolio_combo import combine

PREREG = "docs/rb_risk_combo_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31")}
ONLY = sys.argv[1:]


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    panel = load_half_a()
    nifty, src = _nifty()
    ix = pd.read_parquet("data/pit_sources/indices.parquet")
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    fn = entries_s_range(panel, nifty)
    out = open("data/rb_risk_combo_result.txt" if not ONLY else "data/rb_risk_combo_smoke.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; half A only; range breakout risk + combinations\n")
    for w, (a, b) in WINDOWS.items():
        if ONLY and w not in ONLY:
            continue
        a, b = pd.Timestamp(a), pd.Timestamp(b)
        ew = equal_weight_universe(panel, a, b)
        sleeves = {}
        for code, rk in (("RB3_R10", 0.01), ("RB3_R15", 0.015), ("RB3_R20", 0.02)):
            eq, tr, st = run_s_plus(panel, a, b, fn, nifty, r_multiple=3.0, market_filter=True,
                                    close_vol=1.5, clean_close=False, risk=rk)
            report(out, code, w, a, b, eq, tr, nifty, ew, st)
            if code == "RB3_R10":
                sleeves["R"] = (eq, tr)
        eq, tr = run_momentum(panel, a, b, stop_pct=0.10)
        report(out, "A10", w, a, b, eq, tr, nifty, ew)
        sleeves["A"] = (eq, tr)
        eq, tr, st = run_fm_entries(panel, a, b, nifty, indices, "closebuy", r_mult=3.0)
        report(out, "FM_C3", w, a, b, eq, tr, nifty, ew, st)
        sleeves["F"] = (eq, tr)
        for code, codes in (("C_RB_A", "RA"), ("C_RB_F", "RF")):
            eq, tr = combine(sleeves, codes, True)
            report(out, code, w, a, b, eq, tr, nifty, ew)
    out.close()


if __name__ == "__main__":
    main()
