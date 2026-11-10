"""
Falcon -- A10 with exposure scaled by a trend gauge, per docs/a_exposure_preregistration.md.

    python tests/run_a_exposure.py > data/a_exposure.log
"""
import sys
sys.path.insert(0, ".")

import gc
import re

import numpy as np
import pandas as pd

from backtesting.pit_strategies import equal_weight_universe, make_panel, run_momentum
from tests.half_a import load_half_a, report
from tests.run_mean_reversion import _nifty

PREREG = "docs/a_exposure_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31")}
VARIANTS = [("A10", None, 1.0), ("A10_E50", "EW", 0.5), ("A10_E0", "EW", 0.0), ("A10_N50", "NIFTY", 0.5)]
# existing result files the reference must reproduce: sample -> (file, block header prefix)
REF = {"ALL": ("data/a_stop_result.txt", "A10"), "A": ("data/wick_exit_result.txt", "A10"),
       "B": ("data/halfB_confirmation_result.txt", "A10")}


def ref_numbers(path, code, w):
    txt = open(path, encoding="utf-8").read()
    m = re.search(rf"\n{re.escape(code)}  {w} .*?\n=+\n(.*?)(?=\n=+\n|\Z)", txt, re.S)
    blk = m.group(1)
    g = lambda k: float(re.search(rf"^\s+{k}\s+(-?[\d.]+)", blk, re.M).group(1))
    return g("cagr_pct"), g("max_drawdown_pct")


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    nifty, src = _nifty()
    out = open("data/a_exposure_result.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; A10 with exposure scaled by a trend gauge. Blocks are CODE@SAMPLE (ALL / A / B)\n")
    for sample in ("ALL", "A", "B"):
        if sample == "ALL":
            panel = make_panel(pd.read_parquet("data/pit/prices_adjusted.parquet"), pd.read_parquet("data/pit/universe_monthly.parquet"))
        else:
            panel = load_half_a(sample)
        gc.collect()
        s = panel.sessions
        ew = (1 + equal_weight_universe(panel, s[0], s[-1])).cumprod().reindex(s).ffill()
        g_ew = ~(ew <= ew.rolling(200, min_periods=200).mean()).to_numpy()            # NaN average -> up
        nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
        g_nf = ~(nf <= nf.rolling(200, min_periods=200).mean()).to_numpy()
        gauges = {"EW": g_ew, "NIFTY": g_nf, None: None}
        for code, gname, lvl in VARIANTS:
            for w, (a, b) in WINDOWS.items():
                a, b = pd.Timestamp(a), pd.Timestamp(b)
                st = {}
                eq, tr = run_momentum(panel, a, b, stop_pct=0.10, gauge_up=gauges[gname], down_level=lvl, stats=st)
                rep = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, equal_weight_universe(panel, a, b), st)
                if code == "A10":
                    want = ref_numbers(*REF[sample], w)
                    got = (rep["cagr_pct"], rep["max_drawdown_pct"])
                    ok = all(abs(x - y) < 0.006 for x, y in zip(want, got))
                    print(f"  reference check {sample} {w}: file {want} run {got} -> {'MATCH' if ok else 'MISMATCH'}", flush=True)
                    if not ok:
                        raise SystemExit("Reference A10 does not reproduce the existing result file; stopping before any variant.")
        del panel
        gc.collect()
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
