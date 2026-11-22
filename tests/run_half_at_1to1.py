"""
Falcon -- S10_H1 (half sold at 1:1, rest keeps the 10% stop) vs A10_70 (A10 at 70% slot size),
per docs/half_at_1to1_preregistration.md. Data: data/pit_v2, no ethical filter.

    PYTHONHASHSEED=0 python tests/run_half_at_1to1.py > data/half_at_1to1.log
"""
import sys
sys.path.insert(0, ".")

import gc
import os

import numpy as np
import pandas as pd

from backtesting.pit_strategies import equal_weight_universe, run_momentum
from tests.half_a import report
from tests.run_a_exposure import ref_numbers
from tests.run_ethical_filter_history import load
from tests.run_momentum_weekly_support import REF, WINDOWS
from tests.run_weekly_momentum import trade_stats

PREREG = "docs/half_at_1to1_preregistration.md"
CODES = ("A10", "S10_H1", "A10_70")


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    ix = pd.read_parquet("data/pit_sources/indices_2000_2026.parquet")
    ix["Date"] = pd.to_datetime(ix["Date"])
    nifty = ix[ix["Index"] == "NIFTY 50"].set_index("Date")["Close"].sort_index()
    out = open("data/half_at_1to1_result.txt", "w", encoding="utf-8")
    out.write("Benchmark: NSE NIFTY 50 (data/pit_sources/indices_2000_2026.parquet). Data data/pit_v2, no ethical filter.\n"
              "Blocks are CODE@SAMPLE. Judged on ALL: S10_H1 vs A10_70.\n")
    res = {}
    for sample in ("ALL", "A", "B"):
        panel = load(sample, None)
        gauge = np.zeros(len(panel.sessions), dtype=bool)
        for w, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            ew = equal_weight_universe(panel, a, b)
            runs = {"A10": {}, "S10_H1": {"half_at_r": 1.0}, "A10_70": {"gauge_up": gauge, "down_level": 0.7}}
            for code, kw in runs.items():
                st = {}
                eq, tr = run_momentum(panel, a, b, stop_pct=0.10, stats=st, track_invested=True, **kw)
                ex = trade_stats(tr, a, b)
                ex["avg_invested_pct"] = round(100 * st["inv_sum"] / st["inv_n"], 1)
                r = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, ew, ex)
                r["avg_invested_pct"] = ex["avg_invested_pct"]
                res[(sample, w, code)] = r
            if sample == "ALL":
                checks = [("A10", REF[w]), ("S10_H1", ("data/momentum_tight_stops_result.txt", "S10_H1@ALL"))]
                for code, (path, block) in checks:
                    want = ref_numbers(path, block, w)
                    r = res[(sample, w, code)]
                    got = (float(r["cagr_pct"]), float(r["max_drawdown_pct"]))
                    ok = all(abs(x - y) <= 0.05 for x, y in zip(want, got))
                    line = f"  reference check {code}@ALL {w}: file {want} run {got} -> {'MATCH' if ok else 'MISMATCH'}"
                    print(line, flush=True)
                    out.write(line + "\n")
                    if not ok:
                        out.close()
                        raise SystemExit(f"Reference {code} does not reproduce; stopping.")
            print(sample, w, {c: (float(res[(sample, w, c)]["cagr_pct"]), res[(sample, w, c)]["max_drawdown_pct"],
                                  res[(sample, w, c)]["avg_invested_pct"]) for c in CODES}, flush=True)
        del panel
        gc.collect()
    out.write(f"\n{'=' * 70}\nSUMMARY: CAGR % (max DD %, checks /6, avg invested %, CAGR/|DD|)\n{'=' * 70}\n")
    for sample in ("ALL", "A", "B"):
        for code in CODES:
            parts = []
            for w in WINDOWS:
                r = res[(sample, w, code)]
                mar = r["cagr_pct"] / abs(r["max_drawdown_pct"]) if r["max_drawdown_pct"] else float("nan")
                parts.append(f"{w} {r['cagr_pct']:.2f} ({r['max_drawdown_pct']:.1f}, {sum(r['checks'].values())}/6, "
                             f"inv {r['avg_invested_pct']:.0f}%, {mar:.2f})")
            out.write(f"  {code + '@' + sample:12s} " + " | ".join(parts) + "\n")
    out.write("\nVERDICT (S10_H1 vs A10_70, all stocks, W1 and W2: CAGR >= A10_70 AND DD no more than 1pp deeper AND "
              "(CAGR >= +1pp OR DD >= 3pp shallower) AND >= 4/6 checks):\n")
    ok_all = True
    for w in ("W1", "W2"):
        p, r = res[("ALL", w, "S10_H1")], res[("ALL", w, "A10_70")]
        cg = float(p["cagr_pct"] - r["cagr_pct"])
        dg = float(p["max_drawdown_pct"] - r["max_drawdown_pct"])
        k = sum(p["checks"].values())
        ok = cg >= 0.0 and dg >= -1.0 and (cg >= 1.0 or dg >= 3.0) and k >= 4
        ok_all &= ok
        out.write(f"  {w}: CAGR {p['cagr_pct']:.2f} vs {r['cagr_pct']:.2f} ({cg:+.2f}pp); DD {p['max_drawdown_pct']:.2f} vs "
                  f"{r['max_drawdown_pct']:.2f} ({dg:+.2f}pp shallower); checks {k}/6 -> {'PASS' if ok else 'FAIL'}\n")
    out.write(f"  S10_H1: {'BETTER THAN HOLDING LESS' if ok_all else 'NOT BETTER THAN HOLDING LESS (fails its frozen bar)'}\n")
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
