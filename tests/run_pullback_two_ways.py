"""
Falcon -- LMR (large-cap mean reversion) and A10P (momentum, half at the open + half added on a
weekly pullback), per docs/pullback_two_ways_preregistration.md. Data: data/pit_v2, no ethical filter.

    PYTHONHASHSEED=0 python tests/run_pullback_two_ways.py > data/pullback_two_ways.log
"""
import sys
sys.path.insert(0, ".")

import gc
import os

import numpy as np
import pandas as pd

from backtesting.large_cap_reversion import run_lmr
from backtesting.pit_strategies import equal_weight_universe, run_momentum
from backtesting.weekly_support import weekly_support_levels
from tests.half_a import report
from tests.run_a_exposure import ref_numbers
from tests.run_ethical_filter_history import load
from tests.run_momentum_weekly_support import REF, WINDOWS

PREREG = "docs/pullback_two_ways_preregistration.md"
LMR_V = {"LMR": {}, "LMR_O": {"fill": "open"}, "LMR_S8": {"stop_pct": 0.08}, "LMR_N": {"nifty": True}}
A10P_V = {"A10P": {"add_frac": 0.5}, "A10P_67": {"add_frac": 2 / 3}, "A10P_NF": {"add_frac": 0.5, "add_fallback": False}}


def mean_pct(x):
    return round(100 * float(np.mean(x)), 2) if x else None


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    ix = pd.read_parquet("data/pit_sources/indices_2000_2026.parquet")
    ix["Date"] = pd.to_datetime(ix["Date"])
    nifty = ix[ix["Index"] == "NIFTY 50"].set_index("Date")["Close"].sort_index()
    uni = pd.read_parquet("data/pit_v2/universe_monthly.parquet")
    uni["month_end"] = pd.to_datetime(uni["month_end"])
    top_global = {m: set(g.loc[g["rank"] <= 100, "entity_id"]) for m, g in uni.groupby("month_end")}
    out = open("data/pullback_two_ways_result.txt", "w", encoding="utf-8")
    out.write("Benchmark: NSE NIFTY 50 (data/pit_sources/indices_2000_2026.parquet). Data data/pit_v2, no ethical filter.\n"
              "Blocks are CODE@SAMPLE. Judged on ALL: LMR (vs Nifty) and A10P (vs A10).\n")
    res = {}
    for sample in ("ALL", "A", "B"):
        panel = load(sample, None)
        top100 = {m: top_global.get(m, set()) & members for m, members in panel.universe.items()}
        s = panel.sessions
        nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
        nifty_200 = (nf > nf.rolling(200, min_periods=200).mean()).to_numpy()
        s1 = weekly_support_levels(panel, ("S1",))["S1"]
        for w, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            ew = equal_weight_universe(panel, a, b)

            def rec(code, eq, tr, extra=None):
                res[(sample, w, code)] = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, ew, extra)

            eq, tr = run_momentum(panel, a, b, stop_pct=0.10)
            rec("A10", eq, tr)
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
            for code, kw in A10P_V.items():
                st = {}
                eq, tr = run_momentum(panel, a, b, stop_pct=0.10, add_level=s1, stats=st, **kw)
                rec(code, eq, tr, {"adds": st["adds_total"], "added_at_support": st["adds_support"],
                                   "added_by_fallback": st["adds_fallback"], "adds_cancelled": st["adds_cancelled"],
                                   "add_price_vs_first_fill_pct": mean_pct(st["add_vs_first"]),
                                   "avg_cash_pct": round(100 * st["cash_share_sum"] / max(st["cash_share_n"], 1), 1)})
            for code, kw in LMR_V.items():
                st = {}
                eq, tr = run_lmr(panel, top100, a, b, fill=kw.get("fill", "close"), stop_pct=kw.get("stop_pct"),
                                 nifty_ok=nifty_200 if kw.get("nifty") else None, stats=st)
                rec(code, eq, tr, {"signals": st["signals"], "entries": st["entries"], "exit_bounce": st["exit_bounce"],
                                   "exit_time": st["exit_time"], "exit_stop": st["exit_stop"],
                                   "avg_hold_sessions": round(float(np.mean(st["hold_days"])), 1) if st["hold_days"] else None,
                                   "avg_invested_pct": mean_pct(st["invested_share"])})
            print(sample, w, {c: (float(res[(sample, w, c)]["cagr_pct"]), res[(sample, w, c)]["max_drawdown_pct"])
                              for c in ["A10", *A10P_V, *LMR_V]}, flush=True)
        del panel, s1
        gc.collect()
    codes = ["A10", *A10P_V, *LMR_V]
    out.write(f"\n{'=' * 70}\nSUMMARY: CAGR % (max DD %, checks /6)\n{'=' * 70}\n")
    for sample in ("ALL", "A", "B"):
        for code in codes:
            parts = [f"{w} {res[(sample, w, code)]['cagr_pct']:.2f} ({res[(sample, w, code)]['max_drawdown_pct']:.1f}, "
                     f"{sum(res[(sample, w, code)]['checks'].values())}/6)" for w in WINDOWS]
            out.write(f"  {code + '@' + sample:14s} " + " | ".join(parts) + "\n")
    out.write("\nVERDICT LMR (all stocks, W1 and W2: CAGR >= Nifty + 2pp, max DD shallower than -25%, >= 4/6 checks):\n")
    ok_l = True
    for w in ("W1", "W2"):
        r = res[("ALL", w, "LMR")]
        k = sum(r["checks"].values())
        ok = r["cagr_pct"] >= r["nifty_cagr_pct"] + 2.0 and r["max_drawdown_pct"] > -25.0 and k >= 4
        ok_l &= bool(ok)
        out.write(f"  {w}: CAGR {r['cagr_pct']:.2f} vs Nifty {r['nifty_cagr_pct']:.2f}; DD {r['max_drawdown_pct']:.2f}; "
                  f"checks {k}/6 -> {'PASS' if ok else 'FAIL'}\n")
    out.write(f"  LMR: {'ADOPTED' if ok_l else 'FAILED ITS FROZEN BAR'}\n")
    out.write("\nVERDICT A10P (all stocks, W1 and W2: CAGR >= A10 - 1pp, max DD >= 3pp shallower, >= 4/6 checks):\n")
    ok_p = True
    for w in ("W1", "W2"):
        p, r = res[("ALL", w, "A10P")], res[("ALL", w, "A10")]
        k = sum(p["checks"].values())
        cg, dg = float(p["cagr_pct"] - r["cagr_pct"]), float(p["max_drawdown_pct"] - r["max_drawdown_pct"])
        ok = cg >= -1.0 and dg >= 3.0 and k >= 4
        ok_p &= ok
        out.write(f"  {w}: CAGR {p['cagr_pct']:.2f} vs {r['cagr_pct']:.2f} ({cg:+.2f}pp); DD {p['max_drawdown_pct']:.2f} vs "
                  f"{r['max_drawdown_pct']:.2f} (shallower by {dg:+.2f}pp); checks {k}/6 -> {'PASS' if ok else 'FAIL'}\n")
    out.write(f"  A10P: {'ADOPTED' if ok_p else 'FAILED ITS FROZEN BAR'}\n")
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
