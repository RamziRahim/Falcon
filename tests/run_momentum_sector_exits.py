"""
Falcon -- monthly / weekly momentum, with and without sector strength, under six stop/target
rules, per docs/momentum_sector_exits_preregistration.md. Data: data/pit_v2, no ethical filter.

    PYTHONHASHSEED=0 python tests/run_momentum_sector_exits.py > data/momentum_sector_exits.log
"""
import sys
sys.path.insert(0, ".")

import gc
import os
import time

import numpy as np
import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES
from backtesting.pit_strategies import equal_weight_universe, run_momentum
from backtesting.sector_strength import sector_strong
from backtesting.weekly_support import _weekly
from tests.half_a import report
from tests.run_a_exposure import ref_numbers
from tests.run_ethical_filter_history import load
from tests.run_momentum_weekly_support import REF, WINDOWS
from tests.run_weekly_momentum import trade_stats

PREREG = "docs/momentum_sector_exits_preregistration.md"
BASES = {"M": {"review": "month"}, "M_SEC": {"review": "month", "sec": True},
         "W": {"review": "week"}, "W_SEC": {"review": "week", "sec": True}}
EXITS = {"X10": {}, "X10_T2": {"target_r": 2.0}, "X10_T3": {"target_r": 3.0},
         "XPWL": {"stop_mode": "pwl"}, "XPWL_T2": {"stop_mode": "pwl", "target_r": 2.0},
         "XPWL_T3": {"stop_mode": "pwl", "target_r": 3.0}}
JUDGED = {"M_SEC_X10": "M_X10", "W_SEC_X10": "W_X10"}


def prev_week_low(panel) -> pd.DataFrame:
    wk, _, L, _ = _weekly(panel)
    pos = pd.Series(np.arange(len(L.index)), index=L.index)
    prev = pos.reindex(wk).to_numpy() - 1
    arr = np.full((len(panel.sessions), L.shape[1]), np.nan)
    ok = prev >= 0
    arr[ok] = L.to_numpy(float)[prev[ok]]
    return pd.DataFrame(arr, index=panel.sessions, columns=L.columns)


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    ix = pd.read_parquet("data/pit_sources/indices_2000_2026.parquet")
    ix["Date"] = pd.to_datetime(ix["Date"])
    nifty = ix[ix["Index"] == "NIFTY 50"].set_index("Date")["Close"].sort_index()
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    out = open("data/momentum_sector_exits_result.txt", "w", encoding="utf-8")
    out.write("Benchmark: NSE NIFTY 50 (data/pit_sources/indices_2000_2026.parquet). Data data/pit_v2, no ethical filter.\n"
              "Blocks are BASE_EXIT@SAMPLE. Judged on ALL: M_SEC_X10 vs M_X10, W_SEC_X10 vs W_X10.\n")
    res = {}
    codes = [f"{b}_{x}" for b in BASES for x in EXITS]
    for sample in ("ALL", "A", "B"):
        panel = load(sample, None)
        t0 = time.time()
        allowed = sector_strong(panel, indices, nifty)
        pwl = prev_week_low(panel)
        print(f"{sample}: sector frame + previous-week lows in {time.time() - t0:.0f}s", flush=True)
        for w, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            ew = equal_weight_universe(panel, a, b)
            for bc, bk in BASES.items():
                for xc, xk in EXITS.items():
                    code = f"{bc}_{xc}"
                    st = {}
                    eq, tr = run_momentum(panel, a, b, stop_pct=0.10, review=bk["review"], stats=st,
                                          allowed=allowed if bk.get("sec") else None, pwl=pwl, **xk)
                    ex = trade_stats(tr, a, b)
                    if len(tr):
                        t = pd.DataFrame(tr)
                        yrs = (b - a).days / 365.25
                        ex["targets_per_year"] = round(float((t["exit_reason"] == "TARGET").sum()) / yrs, 1)
                    if bk.get("sec") and st.get("top_candidates"):
                        ex["pct_top20_rejected_by_sector"] = round(100 * st["top_rejected_by_sector"] / st["top_candidates"], 1)
                    if xk.get("stop_mode") == "pwl":
                        ex["pwl_fallback_to_10pct"] = st.get("pwl_fallback", 0)
                    res[(sample, w, code)] = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, ew, ex)
            if sample == "ALL":
                for code, (path, block) in (("M_X10", REF[w]), ("W_X10", ("data/weekly_momentum_result.txt", "WM12@ALL"))):
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
            print(sample, w, {c: (float(res[(sample, w, c)]["cagr_pct"]), res[(sample, w, c)]["max_drawdown_pct"]) for c in codes},
                  flush=True)
        del panel, allowed, pwl
        gc.collect()
    out.write(f"\n{'=' * 70}\nSUMMARY: CAGR % (max DD %, checks /6)\n{'=' * 70}\n")
    for sample in ("ALL", "A", "B"):
        for code in codes:
            parts = [f"{w} {res[(sample, w, code)]['cagr_pct']:.2f} ({res[(sample, w, code)]['max_drawdown_pct']:.1f}, "
                     f"{sum(res[(sample, w, code)]['checks'].values())}/6)" for w in WINDOWS]
            out.write(f"  {code + '@' + sample:18s} " + " | ".join(parts) + "\n")
    out.write("\nVERDICT (all stocks, W1 and W2: CAGR >= base - 1pp AND DD no more than 1pp deeper AND "
              "(CAGR >= base + 1pp OR DD >= 3pp shallower) AND >= 4/6 checks):\n")
    for code, base in JUDGED.items():
        ok_all = True
        for w in ("W1", "W2"):
            p, r = res[("ALL", w, code)], res[("ALL", w, base)]
            cg = float(p["cagr_pct"] - r["cagr_pct"])
            dg = float(p["max_drawdown_pct"] - r["max_drawdown_pct"])
            k = sum(p["checks"].values())
            ok = cg >= -1.0 and dg >= -1.0 and (cg >= 1.0 or dg >= 3.0) and k >= 4
            ok_all &= ok
            out.write(f"  {code} {w}: CAGR {p['cagr_pct']:.2f} vs {r['cagr_pct']:.2f} ({cg:+.2f}pp); DD {p['max_drawdown_pct']:.2f} vs "
                      f"{r['max_drawdown_pct']:.2f} ({dg:+.2f}pp shallower); checks {k}/6 -> {'PASS' if ok else 'FAIL'}\n")
        out.write(f"  {code}: {'PASSES (sector strength helps)' if ok_all else 'FAILS ITS FROZEN BAR'}\n")
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
