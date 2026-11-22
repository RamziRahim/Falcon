"""
Falcon -- monthly momentum (A10) with new names bought at a weekly support level, per
docs/momentum_weekly_support_preregistration.md. Data: data/pit_v2, no ethical filter.

    PYTHONHASHSEED=0 python tests/run_momentum_weekly_support.py > data/momentum_weekly_support.log
"""
import sys
sys.path.insert(0, ".")

import gc
import os
import time

import numpy as np
import pandas as pd

from backtesting.pit_strategies import equal_weight_universe, run_momentum
from backtesting.weekly_support import weekly_support_levels
from tests.half_a import report
from tests.run_a_exposure import ref_numbers
from tests.run_ethical_filter_history import load

PREREG = "docs/momentum_weekly_support_preregistration.md"
WINDOWS = {"H0": ("2001-01-01", "2006-12-31"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31"),
           "W1": ("2019-01-01", "2026-10-30")}
REF = {"H0": ("data/history_2001_2006_result.txt", "A10@ALL"), "W2": ("data/a_stop_result.txt", "A10"),
       "Y2018": ("data/a_stop_result.txt", "A10"), "W1": ("data/a_stop_result.txt", "A10")}
VARIANTS = [(f"MWS_{k}_{fb}", k, fb) for fb in ("BA", "CASH") for k in ("S4", "S1", "S2", "S3")]
PRIMARY = "MWS_S4_BA"


def summarise(st):
    n_orders = st.get("orders", 0)
    mean = lambda x: round(100 * float(np.mean(x)), 2) if x else None
    return {"orders": n_orders, "filled_at_support": st.get("filled_support", 0), "fallback_buys": st.get("fallback_buys", 0),
            "cancelled_never_bought": st.get("cancelled", 0),
            "pct_filled_at_support": round(100 * st.get("filled_support", 0) / n_orders, 1) if n_orders else None,
            "avg_days_to_fill": round(float(np.mean(st["days_to_fill"])), 1) if st.get("days_to_fill") else None,
            "support_fill_vs_A10_open_pct": mean(st.get("entry_vs_open0")),
            "fallback_vs_A10_open_pct": mean(st.get("fallback_vs_open0")),
            "avg_cash_pct": round(100 * st["cash_share_sum"] / st["cash_share_n"], 1) if st.get("cash_share_n") else None}


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    ix = pd.read_parquet("data/pit_sources/indices_2000_2026.parquet")
    ix["Date"] = pd.to_datetime(ix["Date"])
    nifty = ix[ix["Index"] == "NIFTY 50"].set_index("Date")["Close"].sort_index()
    out = open("data/momentum_weekly_support_result.txt", "w", encoding="utf-8")
    out.write("Benchmark: NSE NIFTY 50 (data/pit_sources/indices_2000_2026.parquet). Data data/pit_v2, no ethical filter.\n"
              f"Blocks are CODE@SAMPLE. Judged: {PRIMARY} on ALL vs A10.\n")
    res = {}
    for sample in ("ALL", "A", "B"):
        panel = load(sample, None)
        t0 = time.time()
        levels = weekly_support_levels(panel)
        print(f"{sample}: weekly levels in {time.time() - t0:.0f}s", flush=True)
        for w, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            ew = equal_weight_universe(panel, a, b)
            eq, tr = run_momentum(panel, a, b, stop_pct=0.10)
            r = report(out, f"A10@{sample}", w, a, b, eq, tr, nifty, ew)
            res[(sample, w, "A10")] = r
            if sample == "ALL":
                path, block = REF[w]
                want = ref_numbers(path, block, w)
                got = (float(r["cagr_pct"]), float(r["max_drawdown_pct"]))
                ok = all(abs(x - y) <= 0.05 for x, y in zip(want, got))
                line = f"  reference check A10@ALL {w}: file {want} run {got} -> {'MATCH' if ok else 'MISMATCH'}"
                print(line, flush=True)
                out.write(line + "\n")
                if not ok:
                    out.close()
                    raise SystemExit("Reference A10 does not reproduce; stopping before variants.")
            for code, k, fb in VARIANTS:
                st = {}
                eq, tr = run_momentum(panel, a, b, stop_pct=0.10, support=levels[k], support_fallback=fb, stats=st)
                res[(sample, w, code)] = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, ew, summarise(st))
            print(sample, w, {c: (float(res[(sample, w, c)]["cagr_pct"]), res[(sample, w, c)]["max_drawdown_pct"])
                              for c in ["A10"] + [v[0] for v in VARIANTS]}, flush=True)
        del panel, levels
        gc.collect()
    codes = ["A10"] + [v[0] for v in VARIANTS]
    out.write(f"\n{'=' * 70}\nSUMMARY: CAGR % (max DD %, checks /6)\n{'=' * 70}\n")
    for sample in ("ALL", "A", "B"):
        for code in codes:
            parts = [f"{w} {res[(sample, w, code)]['cagr_pct']:.2f} ({res[(sample, w, code)]['max_drawdown_pct']:.1f}, "
                     f"{sum(res[(sample, w, code)]['checks'].values())}/6)" for w in WINDOWS]
            out.write(f"  {code + '@' + sample:18s} " + " | ".join(parts) + "\n")
    out.write(f"\nVERDICT ({PRIMARY}, all stocks, W1 and W2: DD >= 5pp shallower than A10, CAGR >= A10 - 2pp, >= 4/6 checks):\n")
    ok_all = True
    for w in ("W1", "W2"):
        p, r = res[("ALL", w, PRIMARY)], res[("ALL", w, "A10")]
        dd_gain = float(p["max_drawdown_pct"] - r["max_drawdown_pct"])
        cg = float(p["cagr_pct"] - r["cagr_pct"])
        k = sum(p["checks"].values())
        ok = dd_gain >= 5.0 and cg >= -2.0 and k >= 4
        ok_all &= ok
        out.write(f"  {w}: DD {p['max_drawdown_pct']:.2f} vs {r['max_drawdown_pct']:.2f} (shallower by {dd_gain:+.2f}pp); "
                  f"CAGR {p['cagr_pct']:.2f} vs {r['cagr_pct']:.2f} ({cg:+.2f}pp); checks {k}/6 -> {'PASS' if ok else 'FAIL'}\n")
    out.write(f"  {PRIMARY}: {'ADOPTED' if ok_all else 'FAILED ITS FROZEN BAR'}\n")
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
