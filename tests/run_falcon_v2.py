"""
Falcon -- pattern engine v2, per docs/falcon_v2_preregistration.md.

    PYTHONHASHSEED=0 python tests/run_falcon_v2.py > data/falcon_v2.log
"""
import sys
sys.path.insert(0, ".")

import gc
import os

import numpy as np
import pandas as pd

from backtesting.falcon_salvage import run_setups, run_setups_v2
from backtesting.pit_strategies import equal_weight_universe, make_panel
from tests.half_a import load_half_a, report
from tests.run_a_exposure import WINDOWS, ref_numbers
from tests.run_mean_reversion import _nifty

PREREG = "docs/falcon_v2_preregistration.md"
SPANS = ["2008-01-01_2017-12-31", "2018-01-01_2018-12-31", "2019-01-01_2026-10-30"]
SMOKE = sys.argv[1:]


def prep(panel, setups):
    c = panel.close
    cols = {e: j for j, e in enumerate(c.columns)}
    pos = {d: k for k, d in enumerate(panel.sessions)}
    su = setups[setups.entity_id.isin(cols)].copy()
    su["t"] = su.scan_date.map(lambda d: pos.get(pd.Timestamp(d)))
    su = su.dropna(subset=["t"])
    su["t"] = su.t.astype(int)
    C = c.to_numpy(float)
    S50 = c.rolling(50, min_periods=50).mean().to_numpy(float)
    S200 = c.rolling(200, min_periods=200).mean().to_numpy(float)
    HI52 = panel.high.rolling(252, min_periods=200).max().to_numpy(float)
    MOM = (c / c.shift(126) - 1).to_numpy(float)
    ranks = {}
    for t in su.t.unique():
        mem = [cols[e] for e in panel.universe_on(panel.sessions[t]) if e in cols]
        ranks[t] = pd.Series(MOM[t, mem], index=[c.columns[j] for j in mem]).dropna().rank(pct=True)
    su["mom_rank"] = [ranks[t].get(e, np.nan) for t, e in zip(su.t, su.entity_id)]
    j = su.entity_id.map(cols).to_numpy()
    t = su.t.to_numpy()
    t20 = np.maximum(t - 20, 0)
    with np.errstate(invalid="ignore"):
        su["f_trend"] = (C[t, j] > S200[t, j]) & (S50[t, j] > S200[t, j]) & (S200[t, j] > S200[t20, j])
        su["f_high"] = C[t, j] >= 0.85 * HI52[t, j]
    su["sort_key"] = su.priority * 10 + su.distance
    return su


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    nifty, src = _nifty()
    orig = pd.concat([pd.read_parquet(f"data/pit/falcon_setups_{sp}.parquet") for sp in SPANS])
    v2 = pd.concat([pd.read_parquet(f"data/pit/falcon_setups_v2_{sp}.parquet") for sp in SPANS]) if not SMOKE else orig
    out = open("data/falcon_v2_result.txt" if not SMOKE else "data/falcon_v2_smoke.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; Falcon pattern engine v2. Blocks are CODE@SAMPLE (ALL / A / B)\n")
    for sample in (("A",) if SMOKE else ("A", "B", "ALL")):
        panel = (make_panel(pd.read_parquet("data/pit/prices_adjusted.parquet"), pd.read_parquet("data/pit/universe_monthly.parquet"))
                 if sample == "ALL" else load_half_a(sample))
        gc.collect()
        s = panel.sessions
        nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
        nifty_ok = (nf > nf.rolling(50, min_periods=50).mean()).to_numpy()
        so, sv = prep(panel, orig), prep(panel, v2)
        print(f"{sample}: detections original {len(so)}, v2 {len(sv)}; pass rules 4-5: original "
              f"{int((so.f_trend & so.f_high).sum())}, v2 {int((sv.f_trend & sv.f_high).sum())}", flush=True)
        versions = [("F_REF", None), ("FV2", sv[sv.f_trend & sv.f_high]), ("FV2A", so[so.f_trend & so.f_high]),
                    ("FV2M", sv[sv.f_trend & sv.f_high & (sv.mom_rank >= 0.80)])]
        for code, su in versions:
            for w, (a, b) in WINDOWS.items():
                if SMOKE and w not in SMOKE:
                    continue
                a, b = pd.Timestamp(a), pd.Timestamp(b)
                if code == "F_REF":
                    eq, tr, st = run_setups(panel, so, a, b, "pivot_stop", "falcon", "falcon")
                else:
                    eq, tr, st = run_setups_v2(panel, su, a, b, nifty_ok)
                    st["touch_rejected_pct"] = round(100 * st["touch_rejected"] / max(st["pivot_touches"], 1), 1)
                years = (b - a).days / 365.25
                st["trades_per_year"] = round(len(tr[tr.exit_reason != "OPEN_AT_END"]) / years, 1)
                rep = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, equal_weight_universe(panel, a, b), st)
                if code == "F_REF" and sample == "A" and w in ("W1", "W2"):
                    want = ref_numbers("data/falcon_salvage_result.txt", "F_REF", w)
                    got = (float(rep["cagr_pct"]), rep["max_drawdown_pct"])
                    ok = all(abs(x - y) <= 0.05 for x, y in zip(want, got))
                    print(f"  reference check A {w}: file {want} run {got} -> {'MATCH' if ok else 'MISMATCH'}", flush=True)
                    if not ok:
                        raise SystemExit("Reference F_REF does not reproduce the existing result file; stopping.")
        del panel
        gc.collect()
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
