"""
Falcon -- the shortlisted strategies on 2001-2006, per docs/history_2001_2006_preregistration.md.
Data: data/pit_v2 (data gate passed: tests/check_pit_v2_gate.py and
data/pit_v2/big_moves_in_universe.csv, see the doc). Needs
data/pit_v2/falcon_setups_v3_2001-01-01_2006-12-31.parquet (tests/scan_falcon_setups_v3.py).

    PYTHONHASHSEED=0 python tests/run_history_2001_2006.py > data/history_2001_2006.log
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
from tests.run_falcon_v3_patterns import prep3
from tests.run_portfolio_combo import combine

PREREG = "docs/history_2001_2006_preregistration.md"
H0 = ("2001-01-01", "2006-12-31")
LOAD_TO = pd.Timestamp("2007-12-31")      # prices after this cannot affect a run that ends 2006-12-31
JUDGED = ("A10", "C_F_A", "C_F_A_P3")


def half_of(entity: str) -> str:
    """data/holdout_split.csv rule (reproduces all 1,622 stored assignments): SHA-256 of entity_id, even -> A."""
    return "A" if int(hashlib.sha256(entity.encode()).hexdigest(), 16) % 2 == 0 else "B"


def load(sample):
    prices = pd.read_parquet("data/pit_v2/prices_adjusted.parquet", filters=[("Date", "<=", LOAD_TO)])
    uni = pd.read_parquet("data/pit_v2/universe_monthly.parquet")
    if sample != "ALL":
        stored = pd.read_csv("data/holdout_split.csv", index_col=0)["half"].to_dict()
        uni = uni[uni["entity_id"].map(lambda e: stored.get(e, half_of(e))) == sample]
    panel = make_panel(prices, uni)
    del prices
    gc.collect()
    return panel


def crash_dd(equity):
    """Reported only: lowest equity in May-June 2006 against the highest equity before it (from 2001-01-01)."""
    e = equity["equity"]
    low = e["2006-05-01":"2006-06-30"]
    if low.empty:
        return None
    return round(float(((low / e[:"2006-06-30"].cummax().reindex(low.index)) - 1).min() * 100), 2)


def main():
    text = open(PREREG, encoding="utf-8").read()
    if "**Status: FROZEN" not in text:
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    ix = pd.read_parquet("data/pit_sources/indices_2000_2026.parquet")
    ix["Date"] = pd.to_datetime(ix["Date"])
    nifty = ix[ix["Index"] == "NIFTY 50"].set_index("Date")["Close"].sort_index()
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    v3 = pd.read_parquet("data/pit_v2/falcon_setups_v3_2001-01-01_2006-12-31.parquet")
    a, b = pd.Timestamp(H0[0]), pd.Timestamp(H0[1])
    out = open("data/history_2001_2006_result.txt", "w", encoding="utf-8")
    n0 = nifty[a:b]
    out.write(f"Benchmark: NSE NIFTY 50 (data/pit_sources/indices_2000_2026.parquet); H0 {a.date()} -> {b.date()}; "
              f"Nifty CAGR {_cagr(n0):.2f}%, Nifty in May-June 2006 vs prior high "
              f"{(n0['2006-05-01':'2006-06-30'] / n0[:'2006-06-30'].cummax().reindex(n0['2006-05-01':'2006-06-30'].index) - 1).min() * 100:.2f}%\n"
              f"Sector indices available at H0 start: {sorted(c for c in indices.columns if indices[c][:a].notna().any())}\n"
              "Blocks are CODE@SAMPLE (ALL / A / B). Judged (ALL only): A10, C_F_A, C_F_A_P3.\n")
    summary = {}
    for sample in ("ALL", "A", "B"):
        panel = load(sample)
        s = panel.sessions
        nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
        nifty_ok = (nf > nf.rolling(50, min_periods=50).mean()).to_numpy()
        s3 = prep3(panel, v3)
        real = s3[s3.verdict == "REAL_PATTERN"]
        ew = equal_weight_universe(panel, a, b)
        sl, rep, dd06 = {}, {}, {}

        def rec(code, eq, tr, extra=None):
            dd06[code] = crash_dd(eq)
            ex = dict(extra or {}, crash_dd_may_jun_2006_pct=dd06[code])
            rep[code] = report(out, f"{code}@{sample}", "H0", a, b, eq, tr, nifty, ew, ex)

        eq, tr = run_momentum(panel, a, b, stop_pct=0.10)
        sl["A"] = (eq, tr)
        rec("A10", eq, tr)
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
        summary[sample] = {c: (r["cagr_pct"], r["nifty_cagr_pct"], r["max_drawdown_pct"], sum(r["checks"].values()), dd06[c])
                           for c, r in rep.items()}
        del panel
        gc.collect()
    out.write(f"\n{'=' * 70}\nSUMMARY (CAGR %, Nifty CAGR %, max DD %, checks passed /6, May-Jun 2006 DD %)\n{'=' * 70}\n")
    for sample, rows in summary.items():
        for code, (c, n, dd, k, d6) in rows.items():
            tag = ""
            if sample == "ALL" and code in JUDGED:
                tag = "HOLDS UP" if (c > n and k >= 4) else "DOES NOT HOLD UP"
            out.write(f"  {code + '@' + sample:16s} CAGR {c:7.2f}  Nifty {n:6.2f}  DD {dd:7.2f}  checks {k}/6  "
                      f"2006 {d6}  {tag}\n")
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
