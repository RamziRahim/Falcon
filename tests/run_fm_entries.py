"""
Falcon -- FM with entry triggers, per docs/falcon_momentum_entries_preregistration.md.

    python tests/run_fm_entries.py              # breakout, sweep, fvg
    python tests/run_fm_entries.py sweep        # one track
"""
import sys
sys.path.insert(0, ".")

import gc

import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES
from backtesting.falcon_momentum_entries import run_fm_entries
from backtesting.pit_strategies import equal_weight_universe, judge, make_panel
from tests.analyse_ia_breakout import find_breakouts
from tests.run_mean_reversion import _nifty

PREREG = "docs/falcon_momentum_entries_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31")}
MODES = ("breakout", "sweep", "fvg")


def main():
    modes = sys.argv[1:] or list(MODES)
    if any(m not in MODES for m in modes):
        raise SystemExit(f"Only the pre-registered tracks may be run: {MODES}")
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
    brk = {(j, t): (lvl, b) for j, t, lvl, b in find_breakouts(panel, 1.5, with_bos=True)} if "breakout" in modes else None
    for mode in modes:
        out = open(f"data/fm_entries_{mode}_result.txt", "w", encoding="utf-8")
        out.write(f"Benchmark: {src}; FM watch list + {mode} entry\n")
        verdict = {}
        for name, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            equity, trades, stats = run_fm_entries(panel, a, b, nifty, indices, mode, breakouts=brk)
            trades.to_csv(f"data/fm_entries_{mode}_trades_{name}.csv", index=False)
            report = judge(equity, trades, nifty, ew[name])
            closed = trades[trades["exit_reason"] != "OPEN_AT_END"] if not trades.empty else trades
            net = closed["pnl"] / closed["cost_basis"] if len(closed) else pd.Series(dtype=float)
            lines = [f"\n{'=' * 70}\nFM + {mode} entry  {name} {a.date()} -> {b.date()}\n{'=' * 70}",
                     f"  {'trades (closed)':28s} {len(closed)}",
                     f"  {'win rate after costs':28s} {(net > 0).mean() * 100:.1f}%",
                     f"  {'avg win / avg loss':28s} {net[net > 0].mean() * 100:+.2f}% / {net[net <= 0].mean() * 100:+.2f}%",
                     f"  {'mean net per trade':28s} {net.mean() * 100:+.3f}%",
                     f"  {'exit mix':28s} {closed['exit_reason'].value_counts().to_dict() if len(closed) else {}}",
                     f"  {'stats':28s} {stats}"]
            lines += [f"  {k:28s} {v}" for k, v in report.items() if k != "checks"]
            lines += [f"    [{'PASS' if ok else 'FAIL'}] {c}" for c, ok in report["checks"].items()]
            out.write("\n".join(lines) + "\n")
            out.flush()
            print(f"{mode} {name}: cagr {report.get('cagr_pct')} dd {report.get('max_drawdown_pct')} "
                  f"win {(net > 0).mean() * 100:.1f}% n {len(closed)} {report['verdict']}", flush=True)
            verdict[name] = "PASS" if report["verdict"].startswith("EDGE") else "FAIL"
        out.write(f"\nVerdicts: {verdict}\n{mode}: " + ("PROVISIONAL EDGE (both windows)" if all(v == "PASS" for v in verdict.values()) else "NO DEMONSTRATED EDGE") + "\n")
        out.close()


if __name__ == "__main__":
    main()
