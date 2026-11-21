"""
Falcon -- Wyckoff swing strategy, per docs/wyckoff_swing_preregistration.md.

    PYTHONHASHSEED=0 python tests/run_wyckoff_swing.py > data/wyckoff_swing.log
"""
import sys
sys.path.insert(0, ".")

import gc
import os
import time

import numpy as np
import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES, sector_maps
from backtesting.falcon_salvage import run_setups_v2
from backtesting.pit_strategies import equal_weight_universe, make_panel
from backtesting.wyckoff_swing import panel_candidates, run_wyckoff, swing_machine, weekly_mode
from tests.half_a import load_half_a, report
from tests.run_a_exposure import WINDOWS, ref_numbers
from tests.run_falcon_v2 import SPANS
from tests.run_falcon_v3_patterns import prep3
from tests.run_mean_reversion import _nifty
from tests.run_structure_pullback import mom_ranks

PREREG = "docs/wyckoff_swing_preregistration.md"
# code: (entry kind, min BOS count, universe, sizing, risk)
VERSIONS = [("WY", "WY", 2, "U200", "SD", 0.005), ("WY_U500", "WY", 2, "U500", "SD", 0.005),
            ("WY_SF", "WY", 2, "U200", "SF", 0.01), ("WY_U500_SF", "WY", 2, "U500", "SF", 0.01),
            ("WY_1", "WY", 1, "U200", "SD", 0.005), ("WY_R1", "WY", 2, "U200", "SD", 0.01),
            ("WY_R2", "WY", 2, "U200", "SD", 0.02), ("BASE_BOS", "BOS", 2, "U200", "SD", 0.005),
            ("BASE_TAP", "TAP", 2, "U200", "SD", 0.005)]


def month_index(sessions, keys):
    keys = sorted(keys)
    pos = np.searchsorted(np.array(keys, dtype="datetime64[ns]"), sessions.values, side="right") - 1
    return [keys[k] if k >= 0 else None for k in pos]


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    nifty, src = _nifty()
    ix = pd.read_parquet("data/pit_sources/indices.parquet")
    nf_ohlc = ix[ix["Index"] == "NIFTY 50"].set_index("Date")[["High", "Low", "Close"]].sort_index()
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    v3 = pd.concat([pd.read_parquet(f"data/pit/falcon_setups_v3_{sp}.parquet") for sp in SPANS])
    um = pd.read_parquet("data/pit/universe_monthly.parquet")
    top200 = {pd.Timestamp(m): set(g.loc[g["rank"] <= 200, "entity_id"]) for m, g in um.groupby("month_end")}
    out = open("data/wyckoff_swing_result.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; Wyckoff swing strategy. Blocks are CODE@SAMPLE (ALL / A / B)\n")
    for sample in ("A", "B", "ALL"):
        t0 = time.time()
        panel = (make_panel(pd.read_parquet("data/pit/prices_adjusted.parquet"), um)
                 if sample == "ALL" else load_half_a(sample))
        gc.collect()
        s = panel.sessions
        nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
        nifty_ok = (nf > nf.rolling(50, min_periods=50).mean()).to_numpy()
        n3 = nf_ohlc.reindex(nf_ohlc.index.union(s)).ffill().reindex(s)
        _, nmode, _, _ = swing_machine(n3.High.to_numpy(float), n3.Low.to_numpy(float), n3.Close.to_numpy(float))
        nifty_up = nmode == 1
        cand, SLV, SLC, ATR = panel_candidates(panel)
        cand = cand.reset_index(drop=True)
        cand["mom_rank"] = mom_ranks(panel, cand)
        wk = weekly_mode(panel)
        cols = set(panel.close.columns)
        mkey = month_index(s, panel.universe.keys())
        u500 = [panel.universe.get(k, set()) if k is not None else set() for k in mkey]
        u200 = [(top200.get(k, set()) & u500[i]) if k is not None else set() for i, k in enumerate(mkey)]
        smaps = sector_maps(panel, indices)
        skey = month_index(s, smaps.keys()) if smaps else [None] * len(s)
        sector_on = lambda i: smaps.get(skey[i], {}) if skey[i] is not None else {}
        print(f"{sample}: candidates {len(cand)} " + str(cand.groupby(["kind"]).size().to_dict())
              + f", double-bias WY {int(((cand.kind == 'WY') & (cand['count'] >= 2)).sum())}; prep {time.time() - t0:.0f}s", flush=True)
        s3 = prep3(panel, v3)
        real = s3[s3.verdict == "REAL_PATTERN"]
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
            for code, kind, mincount, uni, sizing, risk in VERSIONS:
                cg = cand[(cand.kind == kind) & (cand["count"] >= mincount)]
                mem = u200 if uni == "U200" else u500
                eq, tr, st = run_wyckoff(panel, cg, a, b, nifty_up, wk, SLV, SLC, ATR, lambda i, m=mem: m[i],
                                         sizing=sizing, risk=risk, sector_on=sector_on)
                closed = tr[tr.exit_reason != "OPEN_AT_END"]
                st["trades_per_year"] = round(len(closed) / years, 1)
                gains, losses = closed.pnl[closed.pnl > 0].sum(), -closed.pnl[closed.pnl < 0].sum()
                st["profit_factor"] = round(float(gains / losses), 2) if losses > 0 else None
                st["t1_share_pct"] = round(100 * st["t1_hits"] / max(st["filled"], 1), 1)
                report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, ew, st)
            print(f"  {sample} {w} done ({time.time() - t0:.0f}s)", flush=True)
        del panel, SLV, SLC, ATR, wk
        gc.collect()
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
