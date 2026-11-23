"""
Falcon -- FM conviction sizing, per docs/fm_conviction_sizing_preregistration.md.
Data: data/pit_v2, no ethical filter.

    PYTHONHASHSEED=0 python tests/run_fm_conviction_sizing.py > data/fm_conviction_sizing.log
"""
import sys
sys.path.insert(0, ".")

import gc
import os

import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES
from backtesting.falcon_momentum_entries import run_fm_entries
from backtesting.pit_strategies import equal_weight_universe, run_momentum
from tests.half_a import report
from tests.run_a_exposure import ref_numbers
from tests.run_ethical_filter_history import load
from tests.run_portfolio_combo import combine

PREREG = "docs/fm_conviction_sizing_preregistration.md"
WINDOWS = {"H0": ("2001-01-01", "2006-12-31"), "W2": ("2008-01-01", "2017-12-31"), "W1": ("2019-01-01", "2026-10-30")}
REF_FILE = "data/buystop_mix_result.txt"
PRIMARY = "FM_C3_CONV"


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    ix = pd.read_parquet("data/pit_sources/indices_2000_2026.parquet")
    ix["Date"] = pd.to_datetime(ix["Date"])
    nifty = ix[ix["Index"] == "NIFTY 50"].set_index("Date")["Close"].sort_index()
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    out = open("data/fm_conviction_sizing_result.txt", "w", encoding="utf-8")
    out.write("Benchmark: NSE NIFTY 50. Data data/pit_v2, no ethical filter. Blocks are CODE@SAMPLE. Judged: FM_C3_CONV vs FM_C3.\n")
    res = {}
    for sample in ("ALL", "A", "B"):
        panel = load(sample, None)
        for w, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            ew = equal_weight_universe(panel, a, b)
            runs = {}
            for code, conv in (("FM_C3", None), ("FM_C3_CONV", "full"), ("FM_C3_MKT", "mkt")):
                eq, tr, st = run_fm_entries(panel, a, b, nifty, indices, "closebuy", r_mult=3.0, conviction=conv)[:3]
                info = {k: v for k, v in st.items() if k.startswith("conv_") or k in ("filled", "cap_binds")}
                res[(sample, w, code)] = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, ew, info)
                runs[code] = (eq, tr)
            am = run_momentum(panel, a, b, stop_pct=0.10)
            for code, f in (("C_F_A", "FM_C3"), ("C_F_A_CONV", "FM_C3_CONV")):
                eq, tr = combine({"F": runs[f], "A": am}, "FA", True)
                res[(sample, w, code)] = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, ew)
            for code in ("FM_C3", "C_F_A"):
                try:
                    want = ref_numbers(REF_FILE, f"{code}@{sample}", w)
                except AttributeError:
                    continue
                got = (float(res[(sample, w, code)]["cagr_pct"]), float(res[(sample, w, code)]["max_drawdown_pct"]))
                ok = all(abs(x - y) <= 0.05 for x, y in zip(want, got))
                line = f"  reference check {code}@{sample} {w}: file {want} run {got} -> {'MATCH' if ok else 'MISMATCH'}"
                print(line, flush=True)
                out.write(line + "\n")
                if not ok:
                    out.close()
                    raise SystemExit(f"Reference {code}@{sample} {w} does not reproduce {REF_FILE}; stopping.")
            out.flush()
        del panel
        gc.collect()
    codes = ("FM_C3", "FM_C3_CONV", "FM_C3_MKT", "C_F_A", "C_F_A_CONV")
    out.write(f"\n{'=' * 70}\nSUMMARY: CAGR % (max DD %, checks /6)\n{'=' * 70}\n")
    for sample in ("ALL", "A", "B"):
        for code in codes:
            parts = [f"{w} {res[(sample, w, code)]['cagr_pct']:.2f} ({res[(sample, w, code)]['max_drawdown_pct']:.1f}, "
                     f"{sum(res[(sample, w, code)]['checks'].values())}/6)" for w in WINDOWS]
            out.write(f"  {code + '@' + sample:16s} " + " | ".join(parts) + "\n")
    g = lambda s, w, c: float(res[(s, w, c)]["cagr_pct"])
    d = lambda s, w, c: float(res[(s, w, c)]["max_drawdown_pct"])
    conds = []
    for w in ("W2", "W1"):
        gain = round(g("ALL", w, PRIMARY) - g("ALL", w, "FM_C3"), 2)
        conds.append((f"1. All stocks {w}: CAGR gain {gain:+.2f}pp (need >= +1.00)", gain >= 1.0))
    for w in ("W2", "W1"):
        worse = round(d("ALL", w, "FM_C3") - d("ALL", w, PRIMARY), 2)
        conds.append((f"2. All stocks {w}: drawdown deeper by {worse:+.2f} points (need <= 2.00)", worse <= 2.0))
    for w in ("W2", "W1"):
        gain = round(g("B", w, PRIMARY) - g("B", w, "FM_C3"), 2)
        conds.append((f"3. Half B {w}: CAGR gain {gain:+.2f}pp (need >= 0)", gain >= 0))
    gain = round(g("ALL", "H0", PRIMARY) - g("ALL", "H0", "FM_C3"), 2)
    conds.append((f"4. All stocks H0: CAGR gain {gain:+.2f}pp (need >= 0)", gain >= 0))
    out.write(f"\nVERDICT ({PRIMARY} vs FM_C3):\n")
    for txt, ok in conds:
        out.write(f"  {txt} -> {'PASS' if ok else 'FAIL'}\n")
    out.write(f"  => {'ADOPTED (IA decides)' if all(ok for _, ok in conds) else 'NOT ADOPTED (IA decides)'}\n")
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
