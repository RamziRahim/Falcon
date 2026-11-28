"""
Falcon -- daily structure flip inside a weekly uptrend (filters FS / FR / FM), two time versions
(C = same calendar time, B = same bar count), per docs/daily_flip_weekly_trend_preregistration.md.
Data: data/pit_v2, no ethical filter.

    PYTHONHASHSEED=0 python tests/run_daily_flip_weekly_trend.py > data/daily_flip_weekly_trend.log
"""
import sys
sys.path.insert(0, ".")

import gc
import os

import pandas as pd

from backtesting.pit_strategies import _cagr, equal_weight_universe, run_momentum
from backtesting.structure_flip import filter_signals, find_signals, run_flip, swing_lows, weekly_uptrend
from tests.half_a import report
from tests.run_a_exposure import ref_numbers
from tests.run_ethical_filter_history import load

PREREG = "docs/daily_flip_weekly_trend_preregistration.md"
WINDOWS = {"H0": ("2001-01-01", "2006-12-31"), "W2": ("2008-01-01", "2017-12-31"), "W1": ("2019-01-01", "2026-10-30")}
ENTRIES = {"a": ("first", "a"), "b": ("first", "b"), "a2": ("second", "a"), "b2": ("second", "b")}
EXITS = ("STR", "R2", "R3", "T26", "LL", "H2", "H3")
FILTERS = ("FS", "FR", "FM")
TIMES = {"C": {"expiry": 65, "hl1_bars": 130, "time_exit": 130}, "B": {"expiry": 13, "hl1_bars": 26, "time_exit": 26}}
WREFS = ["WF_b_LL", "WF_b2_LL"]
REFS = [f"DU_{en}_{ex}_{t}" for t in TIMES for en in ENTRIES for ex in EXITS]
CODES = [f"DF_{f}_{en}_{ex}_{t}" for t in TIMES for f in FILTERS for en in ENTRIES for ex in EXITS]
PRIMARIES = tuple(f"DF_{f}_{en}_LL_{t}" for f in ("FM", "FS", "FR") for en in ("b2", "b") for t in TIMES)


def check(out, file, code_file, code_run, sample, w, rep):
    try:
        want = ref_numbers(file, f"{code_file}@{sample}", w)
    except AttributeError:
        return
    got = (float(rep["cagr_pct"]), float(rep["max_drawdown_pct"]))
    ok = all(abs(x - y) <= 0.05 for x, y in zip(want, got))
    line = f"  reference check {code_run}@{sample} {w} vs {code_file} in {file}: file {want} run {got} -> {'MATCH' if ok else 'MISMATCH'}"
    print(line, flush=True)
    out.write(line + "\n")
    if not ok:
        out.close()
        raise SystemExit("Reference does not reproduce; stopping.")


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    ix = pd.read_parquet("data/pit_sources/indices_2000_2026.parquet")
    ix["Date"] = pd.to_datetime(ix["Date"])
    nifty = ix[ix["Index"] == "NIFTY 50"].set_index("Date")["Close"].sort_index()
    out = open("data/daily_flip_weekly_trend_result.txt", "w", encoding="utf-8")
    out.write("Benchmark: NSE NIFTY 50. Data data/pit_v2, no ethical filter. Blocks are CODE@SAMPLE.\n")
    res, nifty_cagr, yearly, risk = {}, {}, {}, {}
    for sample in ("ALL", "A", "B"):
        panel = load(sample, None)
        wsig = {"first": find_signals(panel, "W"), "second": find_signals(panel, "W", second=True)}
        wlows = swing_lows(panel, "W")
        sig = {}
        for t, tp in TIMES.items():
            sig[("first", t)] = find_signals(panel, "D", expiry=tp["expiry"], hl1_bars=tp["hl1_bars"])
            sig[("second", t)] = find_signals(panel, "D", second=True, expiry=tp["expiry"], hl1_bars=tp["hl1_bars"])
            out.write(f"daily signals {sample} {t}: first flip {len(sig[('first', t)])}, second flip {len(sig[('second', t)])} (all history)\n")
        lows = swing_lows(panel, "D")
        print(sample, "signals", {k: len(v) for k, v in sig.items()}, flush=True)
        fsig = {}
        for f in FILTERS:
            tr_ = weekly_uptrend(panel, f)
            for (which, t), ss in sig.items():
                fsig[(f, which, t)] = filter_signals(ss, tr_)
                n0, n1 = len(ss), len(fsig[(f, which, t)])
                out.write(f"  filter {f} {which} flip {t}: kept {n1} of {n0} ({100 * n1 / max(n0, 1):.1f}%)\n")
            del tr_
        for w, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            ew = equal_weight_universe(panel, a, b)
            am = run_momentum(panel, a, b, stop_pct=0.10)
            res[(sample, w, "A10")] = report(out, f"A10@{sample}", w, a, b, am[0], am[1], nifty, ew)
            check(out, "data/buystop_mix_result.txt", "A10", "A10", sample, w, res[(sample, w, "A10")])
            days = am[0].index
            nf = nifty.reindex(nifty.index.union(days)).ffill().reindex(days)
            nifty_cagr[w] = round(_cagr(nf), 2)
            if sample == "ALL":
                ny = nf.groupby(nf.index.year).last()
                yearly[("NIFTY", w)] = (ny / pd.concat([pd.Series([nf.iloc[0]], index=[ny.index[0] - 1]), ny]).shift(1).dropna() - 1) * 100
            for code in WREFS:
                en, ex = code.split("_")[1:]
                which, mode = ENTRIES[en]
                eq, tr = run_flip(panel, a, b, "W", mode, ex, wsig[which], wlows)
                r_ = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, ew)
                check(out, "data/weekly_flip_exits_result.txt", code, code, sample, w, r_)
            for code in REFS + CODES:
                parts = code.split("_")
                en, ex, t = parts[-3], parts[-2], parts[-1]
                which, mode = ENTRIES[en]
                sigs = sig[(which, t)] if parts[0] == "DU" else fsig[(parts[1], which, t)]
                st = {}
                eq, tr = run_flip(panel, a, b, "D", mode, ex, sigs, lows, stats=st, time_exit=TIMES[t]["time_exit"])
                info = {k: v for k, v in st.items() if k != "risk_sum"}
                if st.get("entries"):
                    info["avg_risk_pct"] = round(100 * st["risk_sum"] / st["entries"], 2)
                if not tr.empty:
                    info["exits"] = tr["exit_reason"].value_counts().to_dict()
                res[(sample, w, code)] = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, ew, info)
                if sample == "ALL":
                    e_ = eq["equity"]
                    ye = e_.groupby(e_.index.year).last()
                    yearly[(code, w)] = (ye / pd.concat([pd.Series([e_.iloc[0]], index=[ye.index[0] - 1]), ye]).shift(1).dropna() - 1) * 100
                    n = st.get("entries", 0) or 1
                    risk[(code, w)] = tuple(round(100 * st.get(kk, 0) / n) for kk in ("risk_lt5", "risk_5to10", "risk_ge10"))
            out.flush()
            print(sample, w, {c: res[(sample, w, c)]["cagr_pct"] for c in ("A10",) + PRIMARIES}, flush=True)
        del panel, sig, lows, fsig, wsig, wlows
        gc.collect()
    allc = ["A10"] + REFS + CODES
    out.write(f"\n{'=' * 70}\nSUMMARY: CAGR % (max DD %, checks /6). Nifty 50 CAGR: {nifty_cagr}\n{'=' * 70}\n")
    for sample in ("ALL", "A", "B"):
        for code in allc:
            parts = [f"{w} {res[(sample, w, code)]['cagr_pct']:.2f} ({res[(sample, w, code)]['max_drawdown_pct']:.1f}, "
                     f"{sum(res[(sample, w, code)]['checks'].values())}/6)" for w in WINDOWS]
            out.write(f"  {code + '@' + sample:22s} " + " | ".join(parts) + "\n")
    out.write("\nINITIAL RISK TO THE STOP, share of entries (all stocks): <5% / 5-10% / >=10%\n")
    for code in REFS + CODES:
        out.write(f"  {code:18s} " + " | ".join(f"{w} {risk[(code, w)][0]}% / {risk[(code, w)][1]}% / {risk[(code, w)][2]}%"
                                            for w in WINDOWS) + "\n")
    out.write("\nYEAR BY YEAR, all stocks, % return per calendar year (part years at window edges)\n")
    years = sorted({y for (c, w), s in yearly.items() for y in s.index})
    out.write(f"  {'code':18s} " + " ".join(f"{y:>6d}" for y in years) + "\n")
    for code in ["NIFTY"] + REFS + CODES:
        vals = {}
        for w in WINDOWS:
            for y, v in yearly[(code, w)].items():
                vals[y] = v
        out.write(f"  {code:18s} " + " ".join(f"{vals[y]:6.1f}" if y in vals else "     -" for y in years) + "\n")
    g = lambda s, w, c: float(res[(s, w, c)]["cagr_pct"])
    out.write("\nVERDICT (each primary: ALL W1 & W2 CAGR >= Nifty + 3.0pp; half B W1 & W2 CAGR > Nifty; ALL H0 CAGR > Nifty; "
              "ALL W1 & W2 CAGR >= the same entry/exit unfiltered):\n")
    passed = 0
    for code in PRIMARIES:
        conds = [(f"ALL {w} {g('ALL', w, code):.2f} vs Nifty {nifty_cagr[w]:.2f} + 3", g("ALL", w, code) >= nifty_cagr[w] + 3.0)
                 for w in ("W2", "W1")]
        conds += [(f"B {w} {g('B', w, code):.2f} vs Nifty {nifty_cagr[w]:.2f}", g("B", w, code) > nifty_cagr[w]) for w in ("W2", "W1")]
        conds.append((f"ALL H0 {g('ALL', 'H0', code):.2f} vs Nifty {nifty_cagr['H0']:.2f}", g("ALL", "H0", code) > nifty_cagr["H0"]))
        base = "DU_" + "_".join(code.split("_")[2:])
        conds += [(f"ALL {w} {g('ALL', w, code):.2f} vs {base} {g('ALL', w, base):.2f}", g("ALL", w, code) >= g("ALL", w, base))
                  for w in ("W2", "W1")]
        ok = all(x for _, x in conds)
        passed += ok
        out.write(f"  {code}: " + "; ".join(f"{t} {'PASS' if x else 'FAIL'}" for t, x in conds) + f" => {'PASSES' if ok else 'FAILS'}\n")
    out.write(f"  => {passed} of {len(PRIMARIES)} primaries passed (IA decides)\n")
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
