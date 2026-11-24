"""
Falcon -- weekly / monthly structure flip, per docs/structure_flip_preregistration.md.
Data: data/pit_v2, no ethical filter.

    PYTHONHASHSEED=0 python tests/run_structure_flip.py > data/structure_flip.log
"""
import sys
sys.path.insert(0, ".")

import gc
import os

import pandas as pd

from backtesting.pit_strategies import _cagr, equal_weight_universe, run_momentum
from backtesting.structure_flip import find_signals, run_flip, swing_lows
from tests.half_a import report
from tests.run_a_exposure import ref_numbers
from tests.run_ethical_filter_history import load
from tests.run_portfolio_combo import combine

PREREG = "docs/structure_flip_preregistration.md"
WINDOWS = {"H0": ("2001-01-01", "2006-12-31"), "W2": ("2008-01-01", "2017-12-31"), "W1": ("2019-01-01", "2026-10-30")}
REF_FILE = "data/buystop_mix_result.txt"
PRIMARIES = ("SF_W_a_STR", "SF_W_b_STR", "SF_M_a_STR", "SF_M_b_STR")
CODES = [f"SF_{tf}_{en}_{ex}" for tf in ("W", "M") for en in ("a", "b") for ex in ("STR", "R2", "R3")]


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    ix = pd.read_parquet("data/pit_sources/indices_2000_2026.parquet")
    ix["Date"] = pd.to_datetime(ix["Date"])
    nifty = ix[ix["Index"] == "NIFTY 50"].set_index("Date")["Close"].sort_index()
    out = open("data/structure_flip_result.txt", "w", encoding="utf-8")
    out.write("Benchmark: NSE NIFTY 50. Data data/pit_v2, no ethical filter. Blocks are CODE@SAMPLE.\n")
    res, nifty_cagr = {}, {}
    for sample in ("ALL", "A", "B"):
        panel = load(sample, None)
        sig = {tf: find_signals(panel, tf) for tf in ("W", "M")}
        lows = {tf: swing_lows(panel, tf) for tf in ("W", "M")}
        out.write(f"signals {sample}: weekly {len(sig['W'])}, monthly {len(sig['M'])} (all history)\n")
        for w, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            ew = equal_weight_universe(panel, a, b)
            am = run_momentum(panel, a, b, stop_pct=0.10)
            res[(sample, w, "A10")] = report(out, f"A10@{sample}", w, a, b, am[0], am[1], nifty, ew)
            if True:
                try:
                    want = ref_numbers(REF_FILE, f"A10@{sample}", w)
                    got = (float(res[(sample, w, "A10")]["cagr_pct"]), float(res[(sample, w, "A10")]["max_drawdown_pct"]))
                    ok = all(abs(x - y) <= 0.05 for x, y in zip(want, got))
                    line = f"  reference check A10@{sample} {w}: file {want} run {got} -> {'MATCH' if ok else 'MISMATCH'}"
                    print(line, flush=True)
                    out.write(line + "\n")
                    if not ok:
                        out.close()
                        raise SystemExit(f"Reference A10@{sample} {w} does not reproduce {REF_FILE}; stopping.")
                except AttributeError:
                    pass
            days = am[0].index
            nf = nifty.reindex(nifty.index.union(days)).ffill().reindex(days)
            nifty_cagr[w] = round(_cagr(nf), 2)
            runs = {}
            for code in CODES:
                _, tf, en, ex = code.split("_")
                st = {}
                eq, tr = run_flip(panel, a, b, tf, en, ex, sig[tf], lows[tf], stats=st)
                info = {k: v for k, v in st.items() if k != "risk_sum"}
                if st.get("entries"):
                    info["avg_risk_pct"] = round(100 * st["risk_sum"] / st["entries"], 2)
                res[(sample, w, code)] = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, ew, info)
                runs[code] = (eq, tr)
            for code in PRIMARIES:
                eq, tr = combine({"F": runs[code], "A": am}, "FA", True)
                res[(sample, w, "MIX_" + code)] = report(out, f"MIX_{code}@{sample}", w, a, b, eq, tr, nifty, ew)
            out.flush()
            print(sample, w, {c: res[(sample, w, c)]["cagr_pct"] for c in ("A10",) + PRIMARIES}, flush=True)
        del panel, sig, lows
        gc.collect()
    allc = ["A10"] + CODES + ["MIX_" + c for c in PRIMARIES]
    out.write(f"\n{'=' * 70}\nSUMMARY: CAGR % (max DD %, checks /6). Nifty 50 CAGR: {nifty_cagr}\n{'=' * 70}\n")
    for sample in ("ALL", "A", "B"):
        for code in allc:
            parts = [f"{w} {res[(sample, w, code)]['cagr_pct']:.2f} ({res[(sample, w, code)]['max_drawdown_pct']:.1f}, "
                     f"{sum(res[(sample, w, code)]['checks'].values())}/6)" for w in WINDOWS]
            out.write(f"  {code + '@' + sample:22s} " + " | ".join(parts) + "\n")
    g = lambda s, w, c: float(res[(s, w, c)]["cagr_pct"])
    out.write("\nVERDICT (each primary: ALL W1 & W2 CAGR >= Nifty + 3.0pp; half B W1 & W2 CAGR > Nifty; ALL H0 CAGR > Nifty):\n")
    passed = 0
    for code in PRIMARIES:
        conds = [(f"ALL {w} {g('ALL', w, code):.2f} vs Nifty {nifty_cagr[w]:.2f} + 3", g("ALL", w, code) >= nifty_cagr[w] + 3.0)
                 for w in ("W2", "W1")]
        conds += [(f"B {w} {g('B', w, code):.2f} vs Nifty {nifty_cagr[w]:.2f}", g("B", w, code) > nifty_cagr[w]) for w in ("W2", "W1")]
        conds.append((f"ALL H0 {g('ALL', 'H0', code):.2f} vs Nifty {nifty_cagr['H0']:.2f}", g("ALL", "H0", code) > nifty_cagr["H0"]))
        ok = all(x for _, x in conds)
        passed += ok
        out.write(f"  {code}: " + "; ".join(f"{t} {'PASS' if x else 'FAIL'}" for t, x in conds) + f" => {'PASSES' if ok else 'FAILS'}\n")
    out.write(f"  => {passed} of {len(PRIMARIES)} primaries passed (IA decides)\n")
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
