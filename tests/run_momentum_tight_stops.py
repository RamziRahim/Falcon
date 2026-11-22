"""
Falcon -- monthly momentum with tighter stops, larger targets, and half-at-1:1 exits with a
break-even or 5% step trailing stop, per docs/momentum_tight_stops_preregistration.md.
Data: data/pit_v2, no ethical filter.

    PYTHONHASHSEED=0 python tests/run_momentum_tight_stops.py > data/momentum_tight_stops.log
"""
import sys
sys.path.insert(0, ".")

import gc
import os

import pandas as pd

from backtesting.pit_strategies import equal_weight_universe, run_momentum
from tests.half_a import report
from tests.run_a_exposure import ref_numbers
from tests.run_ethical_filter_history import load
from tests.run_momentum_weekly_support import REF, WINDOWS
from tests.run_weekly_momentum import trade_stats

PREREG = "docs/momentum_tight_stops_preregistration.md"
VARIANTS = {
    "S6": {"stop_pct": 0.06}, "S5": {"stop_pct": 0.05}, "S7": {"stop_pct": 0.075},
    "S6_T3": {"stop_pct": 0.06, "target_r": 3.0}, "S6_T5": {"stop_pct": 0.06, "target_r": 5.0},
    "S5_T5": {"stop_pct": 0.05, "target_r": 5.0}, "S10_T5": {"stop_pct": 0.10, "target_r": 5.0},
    "S10_T8": {"stop_pct": 0.10, "target_r": 8.0},
    "S10_H1BE": {"stop_pct": 0.10, "half_at_r": 1.0, "half_be": True},
    "S10_H1": {"stop_pct": 0.10, "half_at_r": 1.0},
    "S6_H1BE": {"stop_pct": 0.06, "half_at_r": 1.0, "half_be": True},
    "S5_H1TR": {"stop_pct": 0.05, "half_at_r": 1.0, "half_be": True, "trail_step": 0.05},
    "S6_H1TR": {"stop_pct": 0.06, "half_at_r": 1.0, "half_be": True, "trail_step": 0.05},
    "S10_H1TR": {"stop_pct": 0.10, "half_at_r": 1.0, "half_be": True, "trail_step": 0.05},
}
JUDGED = ("S6", "S5_H1TR")


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    ix = pd.read_parquet("data/pit_sources/indices_2000_2026.parquet")
    ix["Date"] = pd.to_datetime(ix["Date"])
    nifty = ix[ix["Index"] == "NIFTY 50"].set_index("Date")["Close"].sort_index()
    out = open("data/momentum_tight_stops_result.txt", "w", encoding="utf-8")
    out.write("Benchmark: NSE NIFTY 50 (data/pit_sources/indices_2000_2026.parquet). Data data/pit_v2, no ethical filter.\n"
              f"Blocks are CODE@SAMPLE. Judged on ALL vs A10: {', '.join(JUDGED)}.\n")
    res = {}
    codes = ["A10", *VARIANTS]
    for sample in ("ALL", "A", "B"):
        panel = load(sample, None)
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
                st = {}
                eq, tr = run_momentum(panel, a, b, stats=st, **kw)
                ex = trade_stats(tr, a, b)
                if len(tr):
                    t = pd.DataFrame(tr)
                    ex["targets_per_year"] = round(float((t["exit_reason"] == "TARGET").sum()) / ((b - a).days / 365.25), 1)
                if st.get("half_exits"):
                    ex["half_exits_per_year"] = round(st["half_exits"] / ((b - a).days / 365.25), 1)
                res[(sample, w, code)] = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, ew, ex)
            print(sample, w, {c: (float(res[(sample, w, c)]["cagr_pct"]), res[(sample, w, c)]["max_drawdown_pct"]) for c in codes},
                  flush=True)
        del panel
        gc.collect()
    out.write(f"\n{'=' * 70}\nSUMMARY: CAGR % (max DD %, checks /6)\n{'=' * 70}\n")
    for sample in ("ALL", "A", "B"):
        for code in codes:
            parts = [f"{w} {res[(sample, w, code)]['cagr_pct']:.2f} ({res[(sample, w, code)]['max_drawdown_pct']:.1f}, "
                     f"{sum(res[(sample, w, code)]['checks'].values())}/6)" for w in WINDOWS]
            out.write(f"  {code + '@' + sample:14s} " + " | ".join(parts) + "\n")
    out.write("\nVERDICT (all stocks, W1 and W2 vs A10: CAGR >= A10 - 1pp AND DD no more than 1pp deeper AND "
              "(CAGR >= A10 + 1pp OR DD >= 3pp shallower) AND >= 4/6 checks):\n")
    for code in JUDGED:
        ok_all = True
        for w in ("W1", "W2"):
            p, r = res[("ALL", w, code)], res[("ALL", w, "A10")]
            cg = float(p["cagr_pct"] - r["cagr_pct"])
            dg = float(p["max_drawdown_pct"] - r["max_drawdown_pct"])
            k = sum(p["checks"].values())
            ok = cg >= -1.0 and dg >= -1.0 and (cg >= 1.0 or dg >= 3.0) and k >= 4
            ok_all &= ok
            out.write(f"  {code} {w}: CAGR {p['cagr_pct']:.2f} vs {r['cagr_pct']:.2f} ({cg:+.2f}pp); DD {p['max_drawdown_pct']:.2f} vs "
                      f"{r['max_drawdown_pct']:.2f} ({dg:+.2f}pp shallower); checks {k}/6 -> {'PASS' if ok else 'FAIL'}\n")
        out.write(f"  {code}: {'ADOPTED' if ok_all else 'FAILED ITS FROZEN BAR'}\n")
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
