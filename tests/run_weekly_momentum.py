"""
Falcon -- A10 reviewed weekly (and the reported variants), per
docs/weekly_momentum_preregistration.md. Data: data/pit_v2, no ethical filter.

    PYTHONHASHSEED=0 python tests/run_weekly_momentum.py > data/weekly_momentum.log
"""
import sys
sys.path.insert(0, ".")

import gc
import os

import numpy as np
import pandas as pd

from backtesting.pit_strategies import equal_weight_universe, run_momentum
from backtesting.weekly_support import weekly_support_levels
from tests.half_a import report
from tests.run_a_exposure import ref_numbers
from tests.run_ethical_filter_history import load
from tests.run_momentum_weekly_support import REF, WINDOWS

PREREG = "docs/weekly_momentum_preregistration.md"
VARIANTS = {"WM12": {}, "WM12_B40": {"buffer": 40}, "WM6": {"lookback": 126, "skip": 5}, "WM3": {"lookback": 68, "skip": 5},
            "WM12P": {"add_frac": 0.5, "level": "S1"}, "WM12S": {"support_fallback": "BA", "level": "S4"}}
PRIMARY = "WM12"


def trade_stats(tr, a, b):
    years = (b - a).days / 365.25
    if tr is None or len(tr) == 0:
        return {}
    t = pd.DataFrame(tr)
    costs = (t["proceeds"] - t["cost_basis"] - t["pnl"]).sum()
    hold = (pd.to_datetime(t["exit_date"]) - pd.to_datetime(t["entry_date"])).dt.days
    return {"trades_per_year": round(len(t) / years, 1), "avg_hold_days": round(float(hold.mean()), 1),
            "costs_rs_lakh_total": round(costs / 1e5, 2),
            "stops_per_year": round(float((t["exit_reason"] == "STOP").sum()) / years, 1)}


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    ix = pd.read_parquet("data/pit_sources/indices_2000_2026.parquet")
    ix["Date"] = pd.to_datetime(ix["Date"])
    nifty = ix[ix["Index"] == "NIFTY 50"].set_index("Date")["Close"].sort_index()
    out = open("data/weekly_momentum_result.txt", "w", encoding="utf-8")
    out.write("Benchmark: NSE NIFTY 50 (data/pit_sources/indices_2000_2026.parquet). Data data/pit_v2, no ethical filter.\n"
              f"Blocks are CODE@SAMPLE. Judged: {PRIMARY} on ALL vs A10. Costs are on a starting capital of Rs 10 lakh.\n")
    res = {}
    for sample in ("ALL", "A", "B"):
        panel = load(sample, None)
        lv = weekly_support_levels(panel, ("S1", "S4"))
        for w, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            ew = equal_weight_universe(panel, a, b)
            eq, tr = run_momentum(panel, a, b, stop_pct=0.10)
            res[(sample, w, "A10")] = report(out, f"A10@{sample}", w, a, b, eq, tr, nifty, ew, trade_stats(tr, a, b))
            if sample == "ALL":
                path, block = REF[w]
                want = ref_numbers(path, block, w)
                r = res[(sample, w, "A10")]
                got = (float(r["cagr_pct"]), float(r["max_drawdown_pct"]))
                ok = all(abs(x - y) <= 0.05 for x, y in zip(want, got))
                line = f"  reference check A10@ALL {w}: file {want} run {got} -> {'MATCH' if ok else 'MISMATCH'}"
                print(line, flush=True)
                out.write(line + "\n")
                if not ok:
                    out.close()
                    raise SystemExit("Reference A10 does not reproduce; stopping before variants.")
            for code, kw in VARIANTS.items():
                kw = dict(kw)
                level = kw.pop("level", None)
                if level and "add_frac" in kw:
                    kw["add_level"] = lv[level]
                elif level:
                    kw["support"] = lv[level]
                st = {}
                eq, tr = run_momentum(panel, a, b, stop_pct=0.10, review="week", stats=st, **kw)
                ex = trade_stats(tr, a, b)
                if "add_vs_first" in st:
                    ex.update({"adds": st["adds_total"], "added_at_support": st["adds_support"], "added_by_fallback": st["adds_fallback"],
                               "adds_cancelled": st["adds_cancelled"],
                               "avg_cash_pct": round(100 * st["cash_share_sum"] / max(st["cash_share_n"], 1), 1)})
                if "filled_support" in st:
                    ex.update({"orders": st["orders"], "filled_at_support": st["filled_support"], "fallback_buys": st["fallback_buys"],
                               "cancelled": st["cancelled"],
                               "avg_cash_pct": round(100 * st["cash_share_sum"] / max(st["cash_share_n"], 1), 1)})
                res[(sample, w, code)] = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, ew, ex)
            print(sample, w, {c: (float(res[(sample, w, c)]["cagr_pct"]), res[(sample, w, c)]["max_drawdown_pct"])
                              for c in ["A10", *VARIANTS]}, flush=True)
        del panel, lv
        gc.collect()
    codes = ["A10", *VARIANTS]
    out.write(f"\n{'=' * 70}\nSUMMARY: CAGR % (max DD %, checks /6)\n{'=' * 70}\n")
    for sample in ("ALL", "A", "B"):
        for code in codes:
            parts = [f"{w} {res[(sample, w, code)]['cagr_pct']:.2f} ({res[(sample, w, code)]['max_drawdown_pct']:.1f}, "
                     f"{sum(res[(sample, w, code)]['checks'].values())}/6)" for w in WINDOWS]
            out.write(f"  {code + '@' + sample:14s} " + " | ".join(parts) + "\n")
    out.write(f"\nVERDICT ({PRIMARY}, all stocks, W1 and W2: CAGR >= A10 - 1pp AND DD no more than 1pp deeper AND "
              "(CAGR >= A10 + 1pp OR DD >= 3pp shallower) AND >= 4/6 checks):\n")
    ok_all = True
    for w in ("W1", "W2"):
        p, r = res[("ALL", w, PRIMARY)], res[("ALL", w, "A10")]
        cg = float(p["cagr_pct"] - r["cagr_pct"])
        dg = float(p["max_drawdown_pct"] - r["max_drawdown_pct"])
        k = sum(p["checks"].values())
        ok = cg >= -1.0 and dg >= -1.0 and (cg >= 1.0 or dg >= 3.0) and k >= 4
        ok_all &= ok
        out.write(f"  {w}: CAGR {p['cagr_pct']:.2f} vs {r['cagr_pct']:.2f} ({cg:+.2f}pp); DD {p['max_drawdown_pct']:.2f} vs "
                  f"{r['max_drawdown_pct']:.2f} ({dg:+.2f}pp shallower); checks {k}/6 -> {'PASS' if ok else 'FAIL'}\n")
    out.write(f"  {PRIMARY}: {'ADOPTED' if ok_all else 'FAILED ITS FROZEN BAR'}\n")
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
