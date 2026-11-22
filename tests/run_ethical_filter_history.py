"""
Falcon -- the shortlisted strategies with and without Falcon's ethical sector filter, 2001-2026,
per docs/ethical_filter_history_preregistration.md. Data: data/pit_v2.
Exclusions: data/pit_v2/ethical_exclusions.csv (tests/build_ethical_exclusions.py).

    PYTHONHASHSEED=0 python tests/run_ethical_filter_history.py > data/ethical_filter_history.log
"""
import sys
sys.path.insert(0, ".")

import gc
import hashlib
import os

import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES
from backtesting.falcon_momentum_entries import run_fm_entries
from backtesting.falcon_salvage import run_setups_v2
from backtesting.pit_strategies import _cagr, equal_weight_universe, make_panel, run_momentum
from tests.half_a import report
from tests.run_a_exposure import ref_numbers
from tests.run_falcon_v2 import SPANS
from tests.run_falcon_v3_patterns import prep3
from tests.run_portfolio_combo import combine

PREREG = "docs/ethical_filter_history_preregistration.md"
WINDOWS = {"H0": ("2001-01-01", "2006-12-31"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31"),
           "W1": ("2019-01-01", "2026-10-30"), "L25": ("2001-01-01", "2026-10-30")}
SETUPS = {"H0": ["data/pit_v2/falcon_setups_v3_2001-01-01_2006-12-31.parquet"],
          "L25": ["data/pit_v2/falcon_setups_v3_2001-01-01_2026-10-30.parquet"]}
SETUPS.update({w: [f"data/pit/falcon_setups_v3_{sp}.parquet"] for w, sp in
               zip(("W2", "Y2018", "W1"), ("2008-01-01_2017-12-31", "2018-01-01_2018-12-31", "2019-01-01_2026-10-30"))})
assert set(SPANS) == {"2008-01-01_2017-12-31", "2018-01-01_2018-12-31", "2019-01-01_2026-10-30"}
CODES = ("A10", "A10C", "FM_C3", "P3", "C_F_A", "C_F_A_P3")
JUDGED = ("A10", "C_F_A", "C_F_A_P3")
# unfiltered references on all stocks: window -> {code: (file, block header)}
REF = {"W1": {"A10": ("data/a_stop_result.txt", "A10")}, "W2": {"A10": ("data/a_stop_result.txt", "A10")},
       "Y2018": {"A10": ("data/a_stop_result.txt", "A10")}}
for _w in ("W1", "W2", "Y2018"):
    REF[_w].update({c: ("data/momentum_patterns_result.txt", f"{c}@ALL") for c in ("C_F_A", "C_F_A_P3", "FM_C3", "P3")})
REF["H0"] = {c: ("data/history_2001_2006_result.txt", f"{c}@ALL") for c in CODES}
CRASHES = {"2008": ("2008-01-01", "2009-03-31"), "2020": ("2020-02-01", "2020-04-30")}


def half_of(entity: str) -> str:
    return "A" if int(hashlib.sha256(entity.encode()).hexdigest(), 16) % 2 == 0 else "B"


def load(sample, excluded):
    prices = pd.read_parquet("data/pit_v2/prices_adjusted.parquet")
    uni = pd.read_parquet("data/pit_v2/universe_monthly.parquet")
    if sample != "ALL":
        stored = pd.read_csv("data/holdout_split.csv", index_col=0)["half"].to_dict()
        uni = uni[uni["entity_id"].map(lambda e: stored.get(e, half_of(e))) == sample]
    if excluded:
        uni = uni[~uni["entity_id"].isin(excluded)]
    panel = make_panel(prices, uni)
    del prices
    gc.collect()
    return panel


def crash_dd(equity, a, b):
    e = equity["equity"]
    low = e[a:b]
    if low.empty or e.index[0] > pd.Timestamp(a):
        return None
    return round(float(((low / e[:b].cummax().reindex(low.index)) - 1).min() * 100), 2)


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    exc = pd.read_csv("data/pit_v2/ethical_exclusions.csv")
    excluded = set(exc.loc[exc["excluded"], "entity_id"])
    ix = pd.read_parquet("data/pit_sources/indices_2000_2026.parquet")
    ix["Date"] = pd.to_datetime(ix["Date"])
    nifty = ix[ix["Index"] == "NIFTY 50"].set_index("Date")["Close"].sort_index()
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    setups = {w: pd.concat([pd.read_parquet(f) for f in fs]) for w, fs in SETUPS.items()}
    out = open("data/ethical_filter_history_result.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: NSE NIFTY 50 (data/pit_sources/indices_2000_2026.parquet). Data data/pit_v2. "
              f"Excluded stocks: {len(excluded)} (data/pit_v2/ethical_exclusions.csv).\n"
              "Blocks are CODE@SAMPLE[+ETH] (ETH = filtered). Judged: A10, C_F_A, C_F_A_P3 on ALL.\n")
    res = {}
    for sample in ("ALL", "A", "B"):
        for filt in (False, True):
            tag = f"{sample}{'+ETH' if filt else ''}"
            panel = load(sample, excluded if filt else None)
            s = panel.sessions
            nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
            nifty_ok = (nf > nf.rolling(50, min_periods=50).mean()).to_numpy()
            for w, (a, b) in WINDOWS.items():
                a, b = pd.Timestamp(a), pd.Timestamp(b)
                sw = setups[w]
                if filt:
                    sw = sw[~sw["entity_id"].isin(excluded)]
                s3 = prep3(panel, sw)
                real = s3[s3.verdict == "REAL_PATTERN"]
                ew = equal_weight_universe(panel, a, b)
                sl, rep, mst = {}, {}, {}

                def rec(code, eq, tr, extra=None):
                    ex = dict(extra or {})
                    if w == "L25":
                        ex.update({f"crash_dd_{k}_pct": crash_dd(eq, *v) for k, v in CRASHES.items()})
                    rep[code] = report(out, f"{code}@{tag}", w, a, b, eq, tr, nifty, ew, ex or None)
                    res[(tag, w, code)] = rep[code]

                eq, tr = run_momentum(panel, a, b, stop_pct=0.10, stats=mst)
                sl["A"] = (eq, tr)
                tg = mst.get("targets", {})
                ex_in = {}
                if w == "L25" and not filt and sample == "ALL":
                    for i, t in tg.items():
                        y = panel.sessions[i].year
                        ex_in.setdefault(y, []).append(sum(e in excluded for e in t))
                    ex_in = {"excluded_in_top20_avg_by_year": {y: round(sum(v) / len(v), 1) for y, v in sorted(ex_in.items())}}
                rec("A10", eq, tr, ex_in or None)
                eq, tr = run_momentum(panel, a, b, stop_pct=0.10, skip_after_stop=True)
                rec("A10C", eq, tr)
                eq, tr, st = run_fm_entries(panel, a, b, nifty, indices, "closebuy", r_mult=3.0)
                sl["F"] = (eq, tr)
                rec("FM_C3", eq, tr, st)
                eq, tr, st = run_setups_v2(panel, real, a, b, nifty_ok, stop_rule="setup")
                sl["P"] = (eq, tr)
                rec("P3", eq, tr, st)
                eq, tr = combine(sl, "FA", True)
                rec("C_F_A", eq, tr)
                eq, tr = combine(sl, "FAP", True)
                rec("C_F_A_P3", eq, tr)
                print(tag, w, {c: (r["cagr_pct"], r["max_drawdown_pct"]) for c, r in rep.items()}, flush=True)
                if tag == "ALL" and w in REF:
                    for code, (path, block) in REF[w].items():
                        want = ref_numbers(path, block, w)
                        got = (float(rep[code]["cagr_pct"]), float(rep[code]["max_drawdown_pct"]))
                        ok = all(abs(x - y) <= 0.50 for x, y in zip(want, got))
                        line = f"  reference check {code}@ALL {w}: file {want} run {got} -> {'MATCH' if ok else 'MISMATCH'}"
                        print(line, flush=True)
                        out.write(line + "\n")
                        if not ok:
                            out.close()
                            raise SystemExit(f"Reference {code} {w} does not reproduce {path}; stopping before filtered runs.")
            del panel
            gc.collect()
    out.write(f"\n{'=' * 70}\nSUMMARY: CAGR % (max DD %, checks /6), unfiltered -> filtered\n{'=' * 70}\n")
    for sample in ("ALL", "A", "B"):
        for code in CODES:
            parts = []
            for w in WINDOWS:
                u, f = res[(sample, w, code)], res[(f"{sample}+ETH", w, code)]
                parts.append(f"{w} {u['cagr_pct']:.2f}->{f['cagr_pct']:.2f} ({f['max_drawdown_pct']:.1f}, {sum(f['checks'].values())}/6)")
            out.write(f"  {code + '@' + sample:14s} " + " | ".join(parts) + "\n")
    out.write("\nVERDICT (all stocks; filtered CAGR > Nifty in H0, W2, W1 AND L25 cost <= 3.0pp):\n")
    for code in JUDGED:
        beats = {w: res[("ALL+ETH", w, code)]["cagr_pct"] > res[("ALL+ETH", w, code)]["nifty_cagr_pct"] for w in ("H0", "W2", "W1")}
        cost = res[("ALL", "L25", code)]["cagr_pct"] - res[("ALL+ETH", "L25", code)]["cagr_pct"]
        ok = all(beats.values()) and cost <= 3.0
        out.write(f"  {code:10s} beats Nifty {beats}; L25 cost {cost:+.2f}pp -> "
                  f"{'HOLDS UP WITH THE FILTER' if ok else 'DOES NOT HOLD UP (flag for IA)'}\n")
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
