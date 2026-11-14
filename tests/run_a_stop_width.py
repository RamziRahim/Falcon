"""
Falcon -- A10 stop width and re-entry, per docs/a_stop_width_preregistration.md.

    PYTHONHASHSEED=0 python tests/run_a_stop_width.py > data/a_stop_width.log
"""
import sys
sys.path.insert(0, ".")

import gc
import os

import pandas as pd

from backtesting.pit_strategies import equal_weight_universe, make_panel, run_momentum
from tests.half_a import load_half_a, report
from tests.run_a_exposure import WINDOWS, ref_numbers
from tests.run_mean_reversion import _nifty

PREREG = "docs/a_stop_width_preregistration.md"
VARIANTS = [("A10", 0.10, False), ("A", None, False), ("A15", 0.15, False), ("A20", 0.20, False), ("A10C", 0.10, True)]
REF = {("A10", "ALL"): ("data/a_stop_result.txt", "A10"), ("A10", "A"): ("data/wick_exit_result.txt", "A10"),
       ("A10", "B"): ("data/halfB_confirmation_result.txt", "A10"), ("A", "ALL"): ("data/a_stop_result.txt", "A")}


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    nifty, src = _nifty()
    out = open("data/a_stop_width_result.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; A10 stop width and re-entry. Blocks are CODE@SAMPLE (ALL / A / B). "
              "Here A15 / A20 = 15% / 20% stop (not top 15 / top 20)\n")
    for sample in ("ALL", "A", "B"):
        panel = (make_panel(pd.read_parquet("data/pit/prices_adjusted.parquet"), pd.read_parquet("data/pit/universe_monthly.parquet"))
                 if sample == "ALL" else load_half_a(sample))
        gc.collect()
        for code, sp, skip in VARIANTS:
            for w, (a, b) in WINDOWS.items():
                a, b = pd.Timestamp(a), pd.Timestamp(b)
                eq, tr = run_momentum(panel, a, b, stop_pct=sp, skip_after_stop=skip)
                yr = eq["equity"].resample("YE").last()
                years = {int(y.year): round(v, 1) for y, v in (yr.pct_change().dropna() * 100).items()}
                years[int(yr.index[0].year)] = round(yr.iloc[0] / eq["equity"].iloc[0] * 100 - 100, 1)
                rep = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, equal_weight_universe(panel, a, b),
                             {"calendar_years_pct": dict(sorted(years.items()))})
                if (code, sample) in REF:
                    want = ref_numbers(*REF[(code, sample)], w)
                    got = (float(rep["cagr_pct"]), rep["max_drawdown_pct"])
                    ok = all(abs(x - y) <= 0.05 for x, y in zip(want, got))
                    print(f"  reference check {code} {sample} {w}: file {want} run {got} -> {'MATCH' if ok else 'MISMATCH'}", flush=True)
                    if not ok:
                        raise SystemExit("A reference does not reproduce the existing result file; stopping.")
        del panel
        gc.collect()
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
