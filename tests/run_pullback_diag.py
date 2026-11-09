"""
Falcon -- pullback diagnostics, Steps 1, 1b and 2 of docs/pullback_diagnostics_preregistration.md (half A).

    python tests/run_pullback_diag.py > data/pullback_diag.log
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd
import statsmodels.api as sm

from backtesting.falcon_momentum import SECTOR_INDICES, sector_maps
from backtesting.pit_strategies import equal_weight_universe
from backtesting.pullback import run_signal_hold
from backtesting.pullback_signals import FLAGS, HORIZONS, build_cells, signal_sets
from tests.half_a import load_half_a, report
from tests.run_mean_reversion import _nifty

PREREG = "docs/pullback_diagnostics_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31")}


def nw_t(x: pd.Series, dates: pd.Series):
    m = x.groupby(pd.to_datetime(dates).dt.to_period("M")).mean().dropna()
    if len(m) < 6:
        return float("nan"), len(m)
    fit = sm.OLS(m.to_numpy(), np.ones(len(m))).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
    return float(fit.tvalues[0]), len(m)


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    panel = load_half_a()
    nifty, src = _nifty()
    ix = pd.read_parquet("data/pit_sources/indices.parquet")
    n500 = ix[ix["Index"] == "NIFTY 500"].set_index("Date")["Close"].sort_index()
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    cells = build_cells(panel, nifty, n500, pd.Timestamp("2008-01-01"), pd.Timestamp("2026-10-30"))
    cells.to_parquet("data/pullback_cells.parquet")
    print(f"cells: {len(cells):,}", flush=True)
    cells["W"] = np.where(cells.date >= "2019-01-01", "W1", np.where(cells.date >= "2018-01-01", "Y2018", "W2"))
    sets = signal_sets(cells)
    out = open("data/pullback_diag.txt", "w", encoding="utf-8")
    out.write(f"Benchmark for excess: NIFTY 500; half A\n\n=== STEP 1: forward returns per signal set ===\n")
    edge = []
    for name, mask in sets.items():
        for wname, wmask in (("ALL W1+W2", cells.W.isin(["W1", "W2"])), ("W1", cells.W == "W1"),
                             ("W2", cells.W == "W2"), ("2018", cells.W == "Y2018")):
            x = cells[mask & wmask]
            if x.empty:
                continue
            t20, nm = nw_t(x.x20, x.date)
            line = (f"  {name:6s} {wname:9s} n {len(x):6d}  " +
                    "  ".join(f"ex{k} {x[f'x{k}'].mean() * 100:+.2f}%" for k in HORIZONS) +
                    f"  | t(ex20) {t20:+.2f} ({nm} months) | ret20 {x.r20.mean() * 100:+.2f}%  win20 {(x.x20 > 0).mean() * 100:.0f}%"
                    f" | max gain {x.mfe20.mean() * 100:+.1f}%  max drop {x.mae20.mean() * 100:+.1f}%")
            out.write(line + "\n")
            print(line, flush=True)
            if wname == "ALL W1+W2" and name != "L0" and x.x20.mean() >= 0.005 and t20 >= 2:
                edge.append(name)
    out.write(f"\nSets with an edge (mean ex20 >= +0.5%, t >= 2, W1+W2 pooled, L0 is the reference): {edge or 'none'}\n")
    print("edge:", edge, flush=True)

    out.write("\n=== STEP 2: remove one filter at a time from STRICT (W1+W2 pooled) ===\n")
    base = cells.W.isin(["W1", "W2"])
    strict = sets["STRICT"] & base
    for f in FLAGS:
        others = [g for g in FLAGS if g != f]
        without = base.copy()
        for g in others:
            without &= cells[g]
        a, b = cells[strict], cells[without]
        # paired monthly difference: with-set minus without-set
        ma = a.x20.groupby(a.date.dt.to_period("M")).mean()
        mb = b.x20.groupby(b.date.dt.to_period("M")).mean()
        diff = (ma - mb).dropna()
        if len(diff) >= 6:
            fit = sm.OLS(diff.to_numpy(), np.ones(len(diff))).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
            td = float(fit.tvalues[0])
        else:
            td = float("nan")
        delta = a.x20.mean() - b.x20.mean()
        verdict = "CLEARLY HELPS" if delta >= 0.005 and td >= 2 else "does not clearly help"
        line = (f"  without {f:7s}: n {len(b):6d} ex20 {b.x20.mean() * 100:+.2f}%  | with: n {len(a):5d} ex20 "
                f"{a.x20.mean() * 100:+.2f}%  | filter adds {delta * 100:+.2f}pp (t {td:+.2f})  -> {verdict}")
        out.write(line + "\n")
        print(line, flush=True)
    out.write("  note: 'without mom' only widens to the top 40% (the cell pre-screen).\n")

    if edge:
        out.write("\n=== STEP 1b: plain 20-session hold, 2.5 ATR stop ===\n")
        smaps = sector_maps(panel, indices)
        sdates = np.array(sorted(smaps))

        def sector_of(day):
            k = sdates.searchsorted(np.datetime64(day), side="right") - 1
            return smaps[pd.Timestamp(sdates[k])] if k >= 0 else {}
        res = open("data/pullback_hold_result.txt", "w", encoding="utf-8")
        res.write(f"Benchmark: {src}; half A; Step 1b\n")
        for name in edge:
            sig = cells[sets[name]][["t", "entity_id", "rank", "atr", "close"]]
            for w, (a_, b_) in WINDOWS.items():
                a_, b_ = pd.Timestamp(a_), pd.Timestamp(b_)
                eq, tr, st = run_signal_hold(panel, a_, b_, sig, sector_of)
                report(res, f"HOLD_{name}", w, a_, b_, eq, tr, nifty, equal_weight_universe(panel, a_, b_), st)
        res.close()
    out.close()


if __name__ == "__main__":
    main()
