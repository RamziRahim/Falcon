"""
Falcon -- FM exit variants and trade-path breakdown, per
docs/fm_variants_preregistration.md.

    python tests/run_fm_variants.py > data/fm_variants.log
"""
import sys
sys.path.insert(0, ".")

import gc

import numpy as np
import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES, run_fm
from backtesting.pit_strategies import equal_weight_universe, judge, make_panel
from tests.analyse_trade_paths import CLASSES, classify
from tests.run_mean_reversion import _nifty

PREREG = "docs/fm_variants_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31")}
VARIANTS = {"R3": dict(r_mult=3.0), "R2": dict(r_mult=2.0),
            "R3BE": dict(r_mult=3.0, be_at=0.05), "R2BE": dict(r_mult=2.0, be_at=0.05)}
LABEL = {"R3": "1:3", "R2": "1:2", "R3BE": "1:3 + stop to cost at 5%", "R2BE": "1:2 + stop to cost at 5%"}


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    panel = make_panel(prices, universe)
    del prices
    gc.collect()
    nifty, src = _nifty()
    ix = pd.read_parquet("data/pit_sources/indices.parquet")
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    ew = {w: equal_weight_universe(panel, pd.Timestamp(a), pd.Timestamp(b)) for w, (a, b) in WINDOWS.items()}
    H, L = panel.high.to_numpy(float), panel.low.to_numpy(float)
    cols = {e: j for j, e in enumerate(panel.close.columns)}
    pos = {d: k for k, d in enumerate(panel.sessions)}
    n = len(panel.sessions)
    out = open("data/fm_variants_result.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; FM (40-session time stop) exit variants\n")
    paths = []
    for code, kw in VARIANTS.items():
        for w, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            levels = []
            equity, trades, stats = run_fm(panel, a, b, nifty, indices, 40, levels=levels, **kw)
            trades.to_csv(f"data/fm_variants_trades_{code}_{w}.csv", index=False)
            lv = pd.DataFrame(levels, columns=["entity_id", "entry_date", "fill", "stop", "target"])
            lv.to_csv(f"data/fm_variants_levels_{code}_{w}.csv", index=False)
            report = judge(equity, trades, nifty, ew[w])
            closed = trades[trades["exit_reason"] != "OPEN_AT_END"] if not trades.empty else trades
            net = closed["pnl"] / closed["cost_basis"] if len(closed) else pd.Series(dtype=float)
            lines = [f"\n{'=' * 70}\nFM {code} {kw}  {w} {a.date()} -> {b.date()}\n{'=' * 70}",
                     f"  {'trades (closed)':28s} {len(closed)}",
                     f"  {'win rate after costs':28s} {(net > 0).mean() * 100:.1f}%",
                     f"  {'avg win / avg loss':28s} {net[net > 0].mean() * 100:+.2f}% / {net[net <= 0].mean() * 100:+.2f}%",
                     f"  {'mean net per trade':28s} {net.mean() * 100:+.3f}%",
                     f"  {'exit mix':28s} {closed['exit_reason'].value_counts().to_dict() if len(closed) else {}}"]
            lines += [f"  {k:28s} {v}" for k, v in report.items() if k != "checks"]
            lines += [f"    [{'PASS' if ok else 'FAIL'}] {c}" for c, ok in report["checks"].items()]
            out.write("\n".join(lines) + "\n")
            out.flush()
            print(f"FM {code} {w}: cagr {report.get('cagr_pct')} nifty {report.get('nifty_cagr_pct')} "
                  f"dd {report.get('max_drawdown_pct')} win {(net > 0).mean() * 100:.1f}% "
                  f"net/trade {net.mean() * 100:+.2f}% n {len(closed)} checks {sum(report['checks'].values())}/6", flush=True)
            for r in lv.itertuples():
                j, f = cols[r.entity_id], pos[pd.Timestamp(r.entry_date)]
                for wl in (20, 40):
                    if f + wl > n:
                        continue
                    lo = np.nan_to_num(L[f: f + wl, j], nan=np.inf)
                    hi = np.nan_to_num(H[f: f + wl, j], nan=-np.inf)
                    paths.append({"version": code, "period": w, "days": wl,
                                  "cls": classify(lo, hi, r.fill, r.stop, r.target)})
    out.close()
    d = pd.DataFrame(paths)
    d.to_csv("data/fm_trade_paths.csv", index=False)
    with open("data/fm_trade_paths.txt", "w", encoding="utf-8") as fh:
        for pname, ps in [("all 2008-2026", ["W1", "W2", "Y2018"]), ("2019-26", ["W1"]), ("2008-17", ["W2"]), ("2018", ["Y2018"])]:
            fh.write(f"\n=== FM | {pname} ===\n")
            fh.write(f"  {'version':28s} {'days':>4s} {'trades':>6s}  " + "  ".join(f"{c:>13s}" for c in CLASSES) + "\n")
            for code in VARIANTS:
                for wl in (20, 40):
                    x = d[(d.version == code) & (d.period.isin(ps)) & (d.days == wl)]
                    if x.empty:
                        continue
                    sh = x.cls.value_counts(normalize=True) * 100
                    fh.write(f"  {LABEL[code]:28s} {wl:4d} {len(x):6d}  " + "  ".join(f"{sh.get(c, 0):12.1f}%" for c in CLASSES) + "\n")
    print(open("data/fm_trade_paths.txt").read())


if __name__ == "__main__":
    main()
