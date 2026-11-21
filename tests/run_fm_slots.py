"""
Falcon -- FM clean close with more slots, per docs/fm_slots_preregistration.md.

    PYTHONHASHSEED=0 python tests/run_fm_slots.py > data/fm_slots.log
"""
import sys
sys.path.insert(0, ".")

import gc
import os

import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES
from backtesting.falcon_momentum_entries import run_fm_entries
from backtesting.pit_strategies import equal_weight_universe, make_panel
from tests.half_a import load_half_a, report
from tests.run_a_exposure import WINDOWS, ref_numbers
from tests.run_fm_risk_gauge import REF
from tests.run_mean_reversion import _nifty

PREREG = "docs/fm_slots_preregistration.md"
VARIANTS = [("FM_C3", 10), ("FM_C3_S15", 15), ("FM_C3_S20", 20)]


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    nifty, src = _nifty()
    ix = pd.read_parquet("data/pit_sources/indices.parquet")
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    out = open("data/fm_slots_result.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; FM clean close, number of slots. Blocks are CODE@SAMPLE (ALL / A / B)\n")
    for sample in ("A", "B", "ALL"):
        panel = (make_panel(pd.read_parquet("data/pit/prices_adjusted.parquet"), pd.read_parquet("data/pit/universe_monthly.parquet"))
                 if sample == "ALL" else load_half_a(sample))
        gc.collect()
        for code, n in VARIANTS:
            for w, (a, b) in WINDOWS.items():
                a, b = pd.Timestamp(a), pd.Timestamp(b)
                eq, tr, st = run_fm_entries(panel, a, b, nifty, indices, "closebuy", r_mult=3.0, slots=n)
                st["avg_gross_exposure_pct"] = round(float(eq["gross_exposure"].mean()) * 100, 1)
                rep = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, equal_weight_universe(panel, a, b), st)
                print(f"    expo {st['avg_gross_exposure_pct']}% slots_full_skips {st.get('slots_full_skips', 0)} cap_binds {st.get('cap_binds', 0)}", flush=True)
                if code == "FM_C3" and sample in REF:
                    want = ref_numbers(*REF[sample], w)
                    got = (float(rep["cagr_pct"]), rep["max_drawdown_pct"])
                    ok = all(abs(x - y) <= 0.05 for x, y in zip(want, got))
                    print(f"  reference check {sample} {w}: file {want} run {got} -> {'MATCH' if ok else 'MISMATCH'}", flush=True)
                    if not ok:
                        raise SystemExit("Reference FM_C3 does not reproduce the existing result file; stopping.")
        del panel
        gc.collect()
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
