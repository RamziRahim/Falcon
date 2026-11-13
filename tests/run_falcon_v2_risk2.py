"""
Falcon -- v2 patterns at 2% risk, per docs/falcon_v2_risk2_preregistration.md.

    PYTHONHASHSEED=0 python tests/run_falcon_v2_risk2.py > data/falcon_v2_risk2.log
"""
import sys
sys.path.insert(0, ".")

import gc
import os

import pandas as pd

from backtesting.falcon_salvage import run_setups_v2
from backtesting.pit_strategies import equal_weight_universe, make_panel
from tests.half_a import load_half_a, report
from tests.run_a_exposure import WINDOWS, ref_numbers
from tests.run_falcon_v2 import SPANS, prep
from tests.run_mean_reversion import _nifty

PREREG = "docs/falcon_v2_risk2_preregistration.md"
VERSIONS = [("FV2", 0.01), ("FV2_R2", 0.02), ("FV2_R15", 0.015)]
SMOKE = sys.argv[1:]


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    nifty, src = _nifty()
    v2 = pd.concat([pd.read_parquet(f"data/pit/falcon_setups_v2_{sp}.parquet") for sp in SPANS])
    out = open("data/falcon_v2_risk2_result.txt" if not SMOKE else "data/falcon_v2_risk2_smoke.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; Falcon v2 patterns, 2% risk test. Blocks are CODE@SAMPLE (ALL / A / B)\n")
    for sample in (("A",) if SMOKE else ("A", "B", "ALL")):
        panel = (make_panel(pd.read_parquet("data/pit/prices_adjusted.parquet"), pd.read_parquet("data/pit/universe_monthly.parquet"))
                 if sample == "ALL" else load_half_a(sample))
        gc.collect()
        s = panel.sessions
        nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
        nifty_ok = (nf > nf.rolling(50, min_periods=50).mean()).to_numpy()
        sv = prep(panel, v2)
        su = sv[sv.f_trend & sv.f_high]
        print(f"{sample}: v2 setups passing rules 4-5: {len(su)}", flush=True)
        for code, risk in VERSIONS:
            for w, (a, b) in WINDOWS.items():
                if SMOKE and w not in SMOKE:
                    continue
                a, b = pd.Timestamp(a), pd.Timestamp(b)
                eq, tr, st = run_setups_v2(panel, su, a, b, nifty_ok, risk=risk)
                st["touch_rejected_pct"] = round(100 * st["touch_rejected"] / max(st["pivot_touches"], 1), 1)
                if False:
                    st["retest_fill_rate_pct"] = round(100 * st["retest_filled"] / max(st["breakouts"], 1), 1)
                closed = tr[tr.exit_reason != "OPEN_AT_END"]
                st["stop_share_pct"] = round(100 * float((closed.exit_reason == "STOP").mean()), 1) if len(closed) else None
                years = (b - a).days / 365.25
                st["trades_per_year"] = round(len(closed) / years, 1)
                rep = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, equal_weight_universe(panel, a, b), st)
                if code == "FV2" and w in ("W1", "W2") and not SMOKE:
                    want = ref_numbers("data/falcon_v2_result.txt", f"FV2@{sample}", w)
                    got = (float(rep["cagr_pct"]), rep["max_drawdown_pct"])
                    ok = all(abs(x - y) <= 0.05 for x, y in zip(want, got))
                    print(f"  reference check {sample} {w}: file {want} run {got} -> {'MATCH' if ok else 'MISMATCH'}", flush=True)
                    if not ok:
                        raise SystemExit("Reference FV2 does not reproduce the existing result file; stopping.")
        del panel
        gc.collect()
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
