"""
Falcon -- monthly momentum with a confluence stop, 1:3 target and risk-based sizing, per
docs/momentum_risk_sizing_preregistration.md. Data: data/pit_v2, no ethical filter.

    PYTHONHASHSEED=0 python tests/run_momentum_risk_sizing.py > data/momentum_risk_sizing.log
"""
import sys
sys.path.insert(0, ".")

import gc
import os

import pandas as pd

from backtesting.dynamic_stops import conf_candidates
from backtesting.pit_strategies import equal_weight_universe, run_momentum
from tests.half_a import report
from tests.run_a_exposure import ref_numbers
from tests.run_ethical_filter_history import load

PREREG = "docs/momentum_risk_sizing_preregistration.md"
WINDOWS = {"H0": ("2001-01-01", "2006-12-31"), "W2": ("2008-01-01", "2017-12-31"), "W1": ("2019-01-01", "2026-10-30")}
JUDGED_WINDOWS = ("W2", "W1")
REF_FILE = "data/buystop_mix_result.txt"
VARIANTS = {"A10": {},
            "RS_CONF_T3": {"stop_mode": "conf", "target_r": 3.0, "risk_frac": 0.005},
            "RS_CONF": {"stop_mode": "conf", "risk_frac": 0.005},
            "EQ_CONF_T3": {"stop_mode": "conf", "target_r": 3.0},
            "EQ_CONF": {"stop_mode": "conf"}}
PRIMARY = "RS_CONF_T3"


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    ix = pd.read_parquet("data/pit_sources/indices_2000_2026.parquet")
    ix["Date"] = pd.to_datetime(ix["Date"])
    nifty = ix[ix["Index"] == "NIFTY 50"].set_index("Date")["Close"].sort_index()
    out = open("data/momentum_risk_sizing_result.txt", "w", encoding="utf-8")
    out.write("Benchmark: NSE NIFTY 50. Data data/pit_v2, no ethical filter. Blocks are CODE@SAMPLE. Judged: RS_CONF_T3 on ALL vs A10.\n")
    res = {}
    for sample in ("ALL", "A", "B"):
        panel = load(sample, None)
        conf = conf_candidates(panel)
        for w, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            ew = equal_weight_universe(panel, a, b)
            for code, kw in VARIANTS.items():
                st = {}
                extra = {"conf_levels": conf} if kw.get("stop_mode") == "conf" else {}
                eq, tr = run_momentum(panel, a, b, stop_pct=0.10, stats=st, **kw, **extra)
                n = sum(st.get(k, 0) for k in ("branch_cluster", "branch_atr", "branch_pct"))
                info = {k: st[k] for k in ("branch_cluster", "branch_atr", "branch_pct") if k in st}
                if n:
                    info["avg_stop_dist_pct"] = round(100 * st["stop_dist_sum"] / n, 2)
                res[(sample, w, code)] = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, ew, info or None)
            if sample == "ALL":
                want = ref_numbers(REF_FILE, "A10@ALL", w)
                got = (float(res[(sample, w, "A10")]["cagr_pct"]), float(res[(sample, w, "A10")]["max_drawdown_pct"]))
                ok = all(abs(x - y) <= 0.05 for x, y in zip(want, got))
                line = f"  reference check A10@ALL {w}: file {want} run {got} -> {'MATCH' if ok else 'MISMATCH'}"
                print(line, flush=True)
                out.write(line + "\n")
                if not ok:
                    out.close()
                    raise SystemExit(f"Reference A10 {w} does not reproduce {REF_FILE}; stopping.")
        del panel, conf
        gc.collect()
    out.write(f"\n{'=' * 70}\nSUMMARY: CAGR % (max DD %, checks /6)\n{'=' * 70}\n")
    for sample in ("ALL", "A", "B"):
        for code in VARIANTS:
            parts = [f"{w} {res[(sample, w, code)]['cagr_pct']:.2f} ({res[(sample, w, code)]['max_drawdown_pct']:.1f}, "
                     f"{sum(res[(sample, w, code)]['checks'].values())}/6)" for w in WINDOWS]
            out.write(f"  {code + '@' + sample:16s} " + " | ".join(parts) + "\n")
    out.write(f"\nVERDICT ({PRIMARY} vs A10, all stocks, W1 and W2: CAGR >= A10 + 1.0pp AND max DD no more than 2.0 points deeper):\n")
    ok_all = True
    for w in JUDGED_WINDOWS:
        d, e = res[("ALL", w, PRIMARY)], res[("ALL", w, "A10")]
        gain = round(float(d["cagr_pct"] - e["cagr_pct"]), 2)
        worse = round(float(e["max_drawdown_pct"] - d["max_drawdown_pct"]), 2)
        ok = gain >= 1.0 and worse <= 2.0
        ok_all &= ok
        out.write(f"  {w}: CAGR gain {gain:+.2f}pp; drawdown deeper by {worse:+.2f} points -> {'PASS' if ok else 'FAIL'}\n")
    out.write(f"  => {'BETTER THAN A10' if ok_all else 'NOT BETTER THAN A10 (IA decides)'}\n")
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
