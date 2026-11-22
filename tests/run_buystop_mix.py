"""
Falcon -- the current mix with Falcon Momentum on a resting buy-stop at the 20-day high (C_F_A_H),
per docs/buystop_mix_preregistration.md. Data: data/pit_v2.

    PYTHONHASHSEED=0 python tests/run_buystop_mix.py > data/buystop_mix.log
"""
import sys
sys.path.insert(0, ".")

import gc
import os

import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES
from backtesting.falcon_momentum_entries import run_fm_entries
from backtesting.falcon_salvage import run_setups_v2
from backtesting.pit_strategies import equal_weight_universe, run_momentum
from tests.half_a import report
from tests.run_a_exposure import ref_numbers
from tests.run_ethical_filter_history import SETUPS, load
from tests.run_falcon_v3_patterns import prep3
from tests.run_portfolio_combo import combine

PREREG = "docs/buystop_mix_preregistration.md"
WINDOWS = {"H0": ("2001-01-01", "2006-12-31"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31"),
           "W1": ("2019-01-01", "2026-10-30")}
REF_FILE = "data/entry_realism_result.txt"
REF_CODES = ("FM_C3", "C_F_A", "C_F_A_O")
JUDGED = {"C_F_A_H": "C_F_A"}


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    ix = pd.read_parquet("data/pit_sources/indices_2000_2026.parquet")
    ix["Date"] = pd.to_datetime(ix["Date"])
    nifty = ix[ix["Index"] == "NIFTY 50"].set_index("Date")["Close"].sort_index()
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    setups = {w: pd.concat([pd.read_parquet(f) for f in SETUPS[w]]) for w in WINDOWS}
    out = open("data/buystop_mix_result.txt", "w", encoding="utf-8")
    out.write("Benchmark: NSE NIFTY 50 (data/pit_sources/indices_2000_2026.parquet). Data data/pit_v2, no ethical filter.\n"
              "Blocks are CODE@SAMPLE. *H = FM on a resting buy-stop at the 20-day high. Judged: C_F_A_H on ALL.\n")
    res = {}
    for sample in ("ALL", "A", "B"):
        panel = load(sample, None)
        s = panel.sessions
        nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
        nifty_ok = (nf > nf.rolling(50, min_periods=50).mean()).to_numpy()
        for w, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            s3 = prep3(panel, setups[w])
            real = s3[s3.verdict == "REAL_PATTERN"]
            ew = equal_weight_universe(panel, a, b)
            sl, rep = {}, {}

            def rec(code, eq, tr, extra=None):
                if extra and extra.get("gap_n"):
                    extra = dict(extra, avg_gap_pct=round(100 * extra["gap_sum"] / extra["gap_n"], 2))
                rep[code] = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, ew, extra)
                res[(sample, w, code)] = rep[code]

            sl["A"] = run_momentum(panel, a, b, stop_pct=0.10)
            rec("A10", *sl["A"])
            eq, tr, st = run_fm_entries(panel, a, b, nifty, indices, "closebuy", r_mult=3.0)
            sl["F"] = (eq, tr)
            rec("FM_C3", eq, tr, st)
            eq, tr, st = run_fm_entries(panel, a, b, nifty, indices, "closebuy", r_mult=3.0, next_open=True)
            sl["FO"] = (eq, tr)
            eq, tr, st = run_fm_entries(panel, a, b, nifty, indices, "high20", r_mult=3.0)
            sl["FH"] = (eq, tr)
            rec("FM_H3", eq, tr, st)
            eq, tr, st = run_setups_v2(panel, real, a, b, nifty_ok, stop_rule="setup", entry="next_open")
            sl["PO"] = (eq, tr)
            rec("C_F_A", *combine(sl, "FA", True))
            rec("C_F_A_O", *combine({"F": sl["FO"], "A": sl["A"]}, "FA", True))
            rec("C_F_A_H", *combine({"F": sl["FH"], "A": sl["A"]}, "FA", True))
            rec("C_F_A_P3_HO", *combine({"F": sl["FH"], "A": sl["A"], "P": sl["PO"]}, "FAP", True))
            print(sample, w, {c: (float(r["cagr_pct"]), r["max_drawdown_pct"]) for c, r in rep.items()}, flush=True)
            if sample == "ALL":
                for code in REF_CODES:
                    want = ref_numbers(REF_FILE, f"{code}@ALL", w)
                    got = (float(rep[code]["cagr_pct"]), float(rep[code]["max_drawdown_pct"]))
                    ok = all(abs(x - y) <= 0.05 for x, y in zip(want, got))
                    line = f"  reference check {code}@ALL {w}: file {want} run {got} -> {'MATCH' if ok else 'MISMATCH'}"
                    print(line, flush=True)
                    out.write(line + "\n")
                    if not ok:
                        out.close()
                        raise SystemExit(f"Reference {code} {w} does not reproduce {REF_FILE}; stopping.")
        del panel
        gc.collect()
    codes = ("A10", "FM_C3", "FM_H3", "C_F_A", "C_F_A_O", "C_F_A_H", "C_F_A_P3_HO")
    out.write(f"\n{'=' * 70}\nSUMMARY: CAGR % (max DD %, checks /6)\n{'=' * 70}\n")
    for sample in ("ALL", "A", "B"):
        for code in codes:
            parts = [f"{w} {res[(sample, w, code)]['cagr_pct']:.2f} ({res[(sample, w, code)]['max_drawdown_pct']:.1f}, "
                     f"{sum(res[(sample, w, code)]['checks'].values())}/6)" for w in WINDOWS]
            out.write(f"  {code + '@' + sample:16s} " + " | ".join(parts) + "\n")
    out.write("\nVERDICT (all stocks; beats Nifty in H0, W2, W1 AND CAGR within 2.0pp of the close-fill mix in W1 and W2):\n")
    for code, ref in JUDGED.items():
        beats = {w: bool(res[("ALL", w, code)]["cagr_pct"] > res[("ALL", w, code)]["nifty_cagr_pct"]) for w in ("H0", "W2", "W1")}
        gaps = {w: round(float(res[("ALL", w, ref)]["cagr_pct"] - res[("ALL", w, code)]["cagr_pct"]), 2) for w in ("W1", "W2")}
        ok = all(beats.values()) and all(g <= 2.0 for g in gaps.values())
        out.write(f"  {code:10s} beats Nifty {beats}; CAGR shortfall vs {ref} {gaps}pp -> "
                  f"{'HOLDS UP WITH REALISTIC ENTRIES' if ok else 'DOES NOT HOLD UP (IA decides)'}\n")
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
