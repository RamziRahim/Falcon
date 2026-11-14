"""
Falcon -- FM clean close: risk per trade and market gauge, per docs/fm_risk_gauge_preregistration.md.

    PYTHONHASHSEED=0 python tests/run_fm_risk_gauge.py > data/fm_risk_gauge.log
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
from tests.run_mean_reversion import _nifty

PREREG = "docs/fm_risk_gauge_preregistration.md"
VARIANTS = [("FM_C3", 0.01, 0.005, False), ("FM_C3_R15", 0.015, 0.0075, False), ("FM_C3_R20", 0.02, 0.01, False),
            ("FM_C3_EW", 0.01, 0.005, True), ("FM_C3_EW_R15", 0.015, 0.0075, True)]
REF = {"A": ("data/close_entry_result.txt", "FM_C3"), "B": ("data/halfB_confirmation_result.txt", "FM_C3")}


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    nifty, src = _nifty()
    ix = pd.read_parquet("data/pit_sources/indices.parquet")
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    out = open("data/fm_risk_gauge_result.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; FM clean close, risk per trade and gauge. Blocks are CODE@SAMPLE (ALL / A / B)\n")
    for sample in ("A", "B", "ALL"):
        panel = (make_panel(pd.read_parquet("data/pit/prices_adjusted.parquet"), pd.read_parquet("data/pit/universe_monthly.parquet"))
                 if sample == "ALL" else load_half_a(sample))
        gc.collect()
        s = panel.sessions
        ew = (1 + equal_weight_universe(panel, s[0], s[-1])).cumprod()
        for code, r_on, r_soft, use_ew in VARIANTS:
            for w, (a, b) in WINDOWS.items():
                a, b = pd.Timestamp(a), pd.Timestamp(b)
                eq, tr, st = run_fm_entries(panel, a, b, nifty, indices, "closebuy", r_mult=3.0,
                                            risk_on=r_on, risk_soft=r_soft, gauge=ew if use_ew else None)
                st["avg_gross_exposure_pct"] = round(float(eq["gross_exposure"].mean()) * 100, 1)
                rep = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, equal_weight_universe(panel, a, b), st)
                print(f"    expo {st['avg_gross_exposure_pct']}% cap_binds {st.get('cap_binds', 0)} of {st['filled']} fills; "
                      f"slots_full_skips {st.get('slots_full_skips', 0)}; weeks blocked {st.get('weeks_blocked', 0)}/{st.get('weeks', 0)}", flush=True)
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
