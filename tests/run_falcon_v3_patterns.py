"""
Falcon -- pattern engine v3 in the backtest, per docs/falcon_v3_patterns_preregistration.md.

    PYTHONHASHSEED=0 python tests/run_falcon_v3_patterns.py > data/falcon_v3_patterns.log
"""
import sys
sys.path.insert(0, ".")

import gc
import os

import numpy as np
import pandas as pd

from backtesting.falcon_salvage import run_setups_v2
from backtesting.pit_strategies import equal_weight_universe, make_panel
from tests.half_a import load_half_a, report
from tests.run_a_exposure import WINDOWS, ref_numbers
from tests.run_falcon_v2 import SPANS, prep
from tests.run_mean_reversion import _nifty

PREREG = "docs/falcon_v3_patterns_preregistration.md"


def prep3(panel, setups):
    """mom_rank (126-session return rank among that day's universe) for v3 setups."""
    c = panel.close
    cols = {e: j for j, e in enumerate(c.columns)}
    pos = {d: k for k, d in enumerate(panel.sessions)}
    su = setups[setups.entity_id.isin(cols)].copy()
    su["t"] = su.scan_date.map(lambda d: pos.get(pd.Timestamp(d)))
    su = su.dropna(subset=["t"])
    su["t"] = su.t.astype(int)
    MOM = (c / c.shift(126) - 1).to_numpy(float)
    ranks = {}
    for t in su.t.unique():
        mem = [cols[e] for e in panel.universe_on(panel.sessions[t]) if e in cols]
        ranks[t] = pd.Series(MOM[t, mem], index=[c.columns[j] for j in mem]).dropna().rank(pct=True)
    su["mom_rank"] = [ranks[t].get(e, np.nan) for t, e in zip(su.t, su.entity_id)]
    return su


def by_pattern(trades, setups):
    """Trades matched to the latest setup of that stock scanned before entry (information only)."""
    tr = trades[trades.exit_reason != "OPEN_AT_END"].copy()
    if tr.empty:
        return {}
    tr["entry_date"] = pd.to_datetime(tr.entry_date)
    tr["net"] = tr.pnl / tr.cost_basis
    s = setups[["entity_id", "scan_date", "pattern"]].copy()
    s["scan_date"] = pd.to_datetime(s.scan_date)
    m = pd.merge_asof(tr.sort_values("entry_date"), s.sort_values("scan_date"), left_on="entry_date",
                      right_on="scan_date", by="entity_id", allow_exact_matches=False)
    g = m.groupby("pattern")
    return {p: {"n": int(len(x)), "win_pct": round(100 * float((x.net > 0).mean()), 1),
                "mean_net_pct": round(100 * float(x.net.mean()), 2)} for p, x in g}


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    nifty, src = _nifty()
    v2 = pd.concat([pd.read_parquet(f"data/pit/falcon_setups_v2_{sp}.parquet") for sp in SPANS])
    v3 = pd.concat([pd.read_parquet(f"data/pit/falcon_setups_v3_{sp}.parquet") for sp in SPANS])
    out = open("data/falcon_v3_patterns_result.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; Falcon pattern engine v3. Blocks are CODE@SAMPLE (ALL / A / B)\n")
    for sample in ("A", "B", "ALL"):
        panel = (make_panel(pd.read_parquet("data/pit/prices_adjusted.parquet"), pd.read_parquet("data/pit/universe_monthly.parquet"))
                 if sample == "ALL" else load_half_a(sample))
        gc.collect()
        s = panel.sessions
        nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
        nifty_ok = (nf > nf.rolling(50, min_periods=50).mean()).to_numpy()
        sv = prep(panel, v2)
        s3 = prep3(panel, v3)
        real, both = s3[s3.verdict == "REAL_PATTERN"], s3
        print(f"{sample}: v3 setups REAL {len(real)}, REAL+UNSURE {len(both)}; by pattern (REAL) "
              f"{real.pattern.value_counts().to_dict()}", flush=True)
        versions = [("FV2", sv[sv.f_trend & sv.f_high], "max_atr3"), ("P3", real, "setup"), ("P3U", both, "setup")]
        for code, su, rule in versions:
            for w, (a, b) in WINDOWS.items():
                a, b = pd.Timestamp(a), pd.Timestamp(b)
                eq, tr, st = run_setups_v2(panel, su, a, b, nifty_ok, stop_rule=rule)
                years = (b - a).days / 365.25
                closed = tr[tr.exit_reason != "OPEN_AT_END"]
                in_w = su[(pd.to_datetime(su.scan_date) >= a) & (pd.to_datetime(su.scan_date) <= b)]
                st["setups_per_year"] = round(len(in_w) / years, 1)
                st["trades_per_year"] = round(len(closed) / years, 1)
                st["triggered_pct_of_orders"] = round(100 * st["filled"] / max(st["orders"], 1), 1)
                st["touch_rejected_pct"] = round(100 * st["touch_rejected"] / max(st["pivot_touches"], 1), 1)
                if code != "FV2":
                    st["by_pattern"] = by_pattern(tr, su)
                rep = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, equal_weight_universe(panel, a, b), st)
                if code == "FV2" and w in ("W1", "W2"):
                    want = ref_numbers("data/falcon_v2_result.txt", f"FV2@{sample}", w)
                    got = (float(rep["cagr_pct"]), rep["max_drawdown_pct"])
                    ok = all(abs(x - y) <= 0.05 for x, y in zip(want, got))
                    print(f"  reference check {sample} {w}: file {want} run {got} -> {'MATCH' if ok else 'MISMATCH'}", flush=True)
                    if not ok:
                        raise SystemExit("Reference FV2 does not reproduce the existing result file; stopping.")
        del panel
        gc.collect()
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
