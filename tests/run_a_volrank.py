"""
Falcon -- A10 ranked by return per unit of volatility, per docs/a_volrank_preregistration.md.

    PYTHONHASHSEED=0 python tests/run_a_volrank.py > data/a_volrank.log
"""
import sys
sys.path.insert(0, ".")

import gc
import os

import numpy as np
import pandas as pd

from backtesting.pit_strategies import equal_weight_universe, make_panel, run_momentum
from tests.half_a import load_half_a, report
from tests.run_a_exposure import REF, WINDOWS, ref_numbers
from tests.run_mean_reversion import _nifty

PREREG = "docs/a_volrank_preregistration.md"
VARIANTS = [("A10", "raw"), ("A10V", "vol"), ("A10Z", "z")]


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    nifty, src = _nifty()
    out = open("data/a_volrank_result.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; A10 with volatility-adjusted ranking. Blocks are CODE@SAMPLE (ALL / A / B)\n")
    for sample in ("ALL", "A", "B"):
        panel = (make_panel(pd.read_parquet("data/pit/prices_adjusted.parquet"), pd.read_parquet("data/pit/universe_monthly.parquet"))
                 if sample == "ALL" else load_half_a(sample))
        gc.collect()
        vol = panel.close.ffill(limit=5).pct_change(fill_method=None).rolling(252, min_periods=200).std() * np.sqrt(252)
        a10_targets = {}
        for code, sc in VARIANTS:
            for w, (a, b) in WINDOWS.items():
                a, b = pd.Timestamp(a), pd.Timestamp(b)
                st = {}
                eq, tr = run_momentum(panel, a, b, stop_pct=0.10, score=sc, stats=st)
                tg = st.pop("targets", {})
                st.pop("hold_vol", None)
                if code == "A10":
                    a10_targets[w] = tg
                hv = [float(vol.iloc[i][list(t)].mean()) for i, t in tg.items() if t]
                ov = [len(t & a10_targets[w][i]) / len(t) for i, t in tg.items() if t and i in a10_targets[w]]
                closed = tr[tr.exit_reason != "OPEN_AT_END"]
                extra = {"avg_252d_vol_of_holdings_pct": round(float(np.nanmean(hv)) * 100, 1),
                         "overlap_with_A10_pct": round(float(np.mean(ov)) * 100, 1)}
                rep = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, equal_weight_universe(panel, a, b), extra)
                print(f"    {extra} top3 {rep.get('top3_profit_share')}", flush=True)
                if code == "A10":
                    want = ref_numbers(*REF[sample], w)
                    got = (float(rep["cagr_pct"]), rep["max_drawdown_pct"])
                    ok = all(abs(x - y) <= 0.05 for x, y in zip(want, got))
                    print(f"  reference check {sample} {w}: file {want} run {got} -> {'MATCH' if ok else 'MISMATCH'}", flush=True)
                    if not ok:
                        raise SystemExit("Reference A10 does not reproduce the existing result file; stopping.")
        del panel, vol
        gc.collect()
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
