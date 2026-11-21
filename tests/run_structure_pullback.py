"""
Falcon -- swing-structure retest and higher-low pullback, per docs/structure_pullback_preregistration.md.

    PYTHONHASHSEED=0 python tests/run_structure_pullback.py > data/structure_pullback.log
"""
import sys
sys.path.insert(0, ".")

import gc
import os

import numpy as np
import pandas as pd

from backtesting.falcon_salvage import run_setups_v2
from backtesting.pit_strategies import equal_weight_universe, make_panel
from backtesting.structure_pullback import panel_signals, run_signals
from tests.half_a import load_half_a, report
from tests.run_a_exposure import WINDOWS, ref_numbers
from tests.run_falcon_v2 import SPANS
from tests.run_falcon_v3_patterns import prep3
from tests.run_mean_reversion import _nifty

PREREG = "docs/structure_pullback_preregistration.md"


def mom_ranks(panel, sig):
    c = panel.close
    cols = {e: j for j, e in enumerate(c.columns)}
    MOM = (c / c.shift(126) - 1).to_numpy(float)
    out = np.full(len(sig), np.nan)
    for t, idx in sig.groupby("t").groups.items():
        mem = [cols[e] for e in panel.universe_on(panel.sessions[t]) if e in cols]
        rk = pd.Series(MOM[t, mem], index=[c.columns[j] for j in mem]).dropna().rank(pct=True)
        out[sig.index.get_indexer(idx)] = [rk.get(e, np.nan) for e in sig.loc[idx, "entity_id"]]
    return np.where(np.isfinite(out), out, -1.0)


def by_setup(trades, sig, sessions):
    tr = trades[trades.exit_reason != "OPEN_AT_END"].copy()
    if tr.empty:
        return {}
    tr["entry_date"] = pd.to_datetime(tr.entry_date)
    tr["net"] = tr.pnl / tr.cost_basis
    m = sig.assign(entry_date=pd.to_datetime(sessions[sig.t.to_numpy()]))[["entity_id", "entry_date", "setup"]]
    m = m.drop_duplicates(["entity_id", "entry_date"])
    j = tr.merge(m, on=["entity_id", "entry_date"], how="left")
    return {k: {"n": int(len(x)), "win_pct": round(100 * float((x.net > 0).mean()), 1),
                "mean_net_pct": round(100 * float(x.net.mean()), 2)} for k, x in j.groupby("setup")}


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    nifty, src = _nifty()
    v3 = pd.concat([pd.read_parquet(f"data/pit/falcon_setups_v3_{sp}.parquet") for sp in SPANS])
    out = open("data/structure_pullback_result.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; swing-structure retest (TCR) and higher-low pullback (HLP). Blocks are CODE@SAMPLE\n")
    for sample in ("A", "B", "ALL"):
        panel = (make_panel(pd.read_parquet("data/pit/prices_adjusted.parquet"), pd.read_parquet("data/pit/universe_monthly.parquet"))
                 if sample == "ALL" else load_half_a(sample))
        gc.collect()
        s = panel.sessions
        nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
        nifty_ok = (nf > nf.rolling(50, min_periods=50).mean()).to_numpy()
        sig, n_breaks = panel_signals(panel)
        sig = sig.reset_index(drop=True)
        sig["mom_rank"] = mom_ranks(panel, sig)
        sig["date"] = s[sig.t.to_numpy()]
        if sample == "ALL":
            sig.to_parquet("data/pit/structure_pullback_signals.parquet", index=False)
        print(f"{sample}: signals {len(sig)} (TCR {int((sig.setup == 'TCR').sum())}, HLP {int((sig.setup == 'HLP').sum())}), "
              f"TCR breaks {n_breaks}, trend_ok {int(sig.trend_ok.sum())}", flush=True)
        s3 = prep3(panel, v3)
        real = s3[s3.verdict == "REAL_PATTERN"]
        versions = [("PB", sig[sig.trend_ok]), ("PB_TCR", sig[sig.trend_ok & (sig.setup == "TCR")]),
                    ("PB_HLP", sig[sig.trend_ok & (sig.setup == "HLP")]), ("PB_NF", sig)]
        for w, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            ew = equal_weight_universe(panel, a, b)
            years = (b - a).days / 365.25
            eq, tr, st = run_setups_v2(panel, real, a, b, nifty_ok, stop_rule="setup")
            rep = report(out, f"P3@{sample}", w, a, b, eq, tr, nifty, ew, st)
            if w in ("W1", "W2"):
                want = ref_numbers("data/falcon_v3_patterns_result.txt", f"P3@{sample}", w)
                got = (float(rep["cagr_pct"]), rep["max_drawdown_pct"])
                ok = all(abs(x - y) <= 0.05 for x, y in zip(want, got))
                print(f"  reference check P3@{sample} {w}: file {want} run {got} -> {'MATCH' if ok else 'MISMATCH'}", flush=True)
                if not ok:
                    raise SystemExit("Reference P3 does not reproduce the stored result; stopping.")
            p3_tpy = round(len(tr[tr.exit_reason != "OPEN_AT_END"]) / years, 1)
            for code, sg in versions:
                eq, tr, st = run_signals(panel, sg, a, b, nifty_ok)
                closed = tr[tr.exit_reason != "OPEN_AT_END"]
                in_w = sg[(sg.date >= a) & (sg.date <= b)]
                st["trades_per_year"] = round(len(closed) / years, 1)
                st["p3_trades_per_year"] = p3_tpy
                st["signals_per_year"] = {k: round(int((in_w.setup == k).sum()) / years, 1) for k in ("TCR", "HLP")}
                tcr = in_w[in_w.setup == "TCR"]
                st["tcr_entry_within_2_sessions_of_break_pct"] = round(100 * float((tcr.lag <= 2).mean()), 1) if len(tcr) else None
                st["by_setup"] = by_setup(tr, sg, s)
                report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, ew, st)
        del panel
        gc.collect()
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
