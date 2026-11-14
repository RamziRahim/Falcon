"""
Falcon -- v3 patterns with monthly momentum, per docs/momentum_patterns_preregistration.md.

    PYTHONHASHSEED=0 python tests/run_momentum_patterns.py > data/momentum_patterns.log
"""
import sys
sys.path.insert(0, ".")

import gc
import os

import numpy as np
import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES
from backtesting.falcon_momentum_entries import run_fm_entries
from backtesting.falcon_salvage import run_setups_v2
from backtesting.momentum_timing import run_momentum_timing
from backtesting.pit_strategies import equal_weight_universe, make_panel, run_momentum
from tests.half_a import load_half_a, report
from tests.run_a_exposure import WINDOWS, ref_numbers
from tests.run_falcon_v2 import SPANS
from tests.run_falcon_v3_patterns import prep3
from tests.run_mean_reversion import _nifty
from tests.run_portfolio_combo import combine

PREREG = "docs/momentum_patterns_preregistration.md"
REF = {"A": {"A10": ("data/wick_exit_result.txt", "A10"), "C_F_A": ("data/wick_exit_result.txt", "C_F_A")},
       "B": {"A10": ("data/halfB_confirmation_result.txt", "A10"), "C_F_A": ("data/halfB_confirmation_result.txt", "C_F_A")},
       "ALL": {"A10": ("data/a_stop_result.txt", "A10")}}


def monthly_corr(x, y):
    a = x["equity"].resample("ME").last().pct_change().dropna()
    b = y["equity"].resample("ME").last().pct_change().dropna()
    j = a.index.intersection(b.index)
    return round(float(np.corrcoef(a[j], b[j])[0, 1]), 2) if len(j) > 3 else None


def check(sample, code, w, rep, path, block):
    want = ref_numbers(path, block, w)
    got = (float(rep["cagr_pct"]), rep["max_drawdown_pct"])
    ok = all(abs(x - y) <= 0.05 for x, y in zip(want, got))
    print(f"  reference check {code}@{sample} {w}: file {want} run {got} -> {'MATCH' if ok else 'MISMATCH'}", flush=True)
    if not ok:
        raise SystemExit(f"Reference {code}@{sample} {w} does not reproduce {path}; stopping.")


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    nifty, src = _nifty()
    ix = pd.read_parquet("data/pit_sources/indices.parquet")
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    v3 = pd.concat([pd.read_parquet(f"data/pit/falcon_setups_v3_{sp}.parquet") for sp in SPANS])
    out = open("data/momentum_patterns_result.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; v3 patterns with monthly momentum. Blocks are CODE@SAMPLE (ALL / A / B)\n")
    for sample in ("A", "B", "ALL"):
        panel = (make_panel(pd.read_parquet("data/pit/prices_adjusted.parquet"), pd.read_parquet("data/pit/universe_monthly.parquet"))
                 if sample == "ALL" else load_half_a(sample))
        gc.collect()
        s = panel.sessions
        nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
        nifty_ok = (nf > nf.rolling(50, min_periods=50).mean()).to_numpy()
        s3 = prep3(panel, v3)
        real = s3[s3.verdict == "REAL_PATTERN"]
        for w, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            ew = equal_weight_universe(panel, a, b)
            sl, rep = {}, {}
            mst = {}
            eq, tr = run_momentum(panel, a, b, stop_pct=0.10, stats=mst)
            sl["A"] = (eq, tr)
            rep["A10"] = report(out, f"A10@{sample}", w, a, b, eq, tr, nifty, ew)
            eq, tr, st = run_fm_entries(panel, a, b, nifty, indices, "closebuy", r_mult=3.0)
            sl["F"] = (eq, tr)
            rep["FM_C3"] = report(out, f"FM_C3@{sample}", w, a, b, eq, tr, nifty, ew, st)
            eq, tr, st = run_setups_v2(panel, real, a, b, nifty_ok, stop_rule="setup")
            sl["P"] = (eq, tr)
            rep["P3"] = report(out, f"P3@{sample}", w, a, b, eq, tr, nifty, ew, st)
            eq, tr = combine(sl, "FA", True)
            rep["C_F_A"] = report(out, f"C_F_A@{sample}", w, a, b, eq, tr, nifty, ew)
            extra = {"corr_monthly_A10_P3": monthly_corr(sl["A"][0], sl["P"][0]),
                     "corr_monthly_A10_FM_C3": monthly_corr(sl["A"][0], sl["F"][0])}
            eq, tr = combine(sl, "AP", True)
            rep["C_A_P3"] = report(out, f"C_A_P3@{sample}", w, a, b, eq, tr, nifty, ew, extra)
            eq, tr = combine(sl, "FAP", True)
            rep["C_F_A_P3"] = report(out, f"C_F_A_P3@{sample}", w, a, b, eq, tr, nifty, ew, extra)
            eq, tr, st = run_momentum_timing(panel, a, b, mst.get("targets", {}), real, nifty_ok)
            rep["A10T"] = report(out, f"A10T@{sample}", w, a, b, eq, tr, nifty, ew, st)
            if w in ("W1", "W2"):
                for code, (path, block) in REF[sample].items():
                    check(sample, code, w, rep[code], path, block)
                check(sample, "P3", w, rep["P3"], "data/falcon_v3_patterns_result.txt", f"P3@{sample}")
        del panel
        gc.collect()
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
