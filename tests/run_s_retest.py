"""
Falcon -- #3 with retest entries, per docs/s_retest_preregistration.md.

    python tests/run_s_retest.py > data/s_retest.log
"""
import sys
sys.path.insert(0, ".")

import gc

import pandas as pd

from backtesting.fixed_bracket import entries_s
from backtesting.pit_strategies import equal_weight_universe, judge, make_panel
from backtesting.s_retest import run_retest
from tests.run_mean_reversion import _nifty

PREREG = "docs/s_retest_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31")}
VARIANTS = {"RL3": dict(mode="limit", r_multiple=3), "RL2": dict(mode="limit", r_multiple=2),
            "RR3": dict(mode="reclaim", r_multiple=3), "RR2": dict(mode="reclaim", r_multiple=2)}


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    panel = make_panel(prices, universe)
    del prices
    gc.collect()
    nifty, src = _nifty()
    fn = entries_s(panel, nifty)
    ew = {w: equal_weight_universe(panel, pd.Timestamp(a), pd.Timestamp(b)) for w, (a, b) in WINDOWS.items()}
    out = open("data/s_retest_result.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; #3 + Nifty filter, retest entries\n")
    for code, kw in VARIANTS.items():
        for w, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            equity, trades, st = run_retest(panel, a, b, fn, nifty, **kw)
            trades.to_csv(f"data/s_retest_trades_{code}_{w}.csv", index=False)
            report = judge(equity, trades, nifty, ew[w])
            closed = trades[trades["exit_reason"] != "OPEN_AT_END"] if not trades.empty else trades
            net = closed["pnl"] / closed["cost_basis"] if len(closed) else pd.Series(dtype=float)
            lines = [f"\n{'=' * 70}\n{code} {kw}  {w} {a.date()} -> {b.date()}\n{'=' * 70}",
                     f"  {'trades (closed)':28s} {len(closed)}",
                     f"  {'win rate after costs':28s} {(net > 0).mean() * 100:.1f}%",
                     f"  {'avg win / avg loss':28s} {net[net > 0].mean() * 100:+.2f}% / {net[net <= 0].mean() * 100:+.2f}%",
                     f"  {'mean net per trade':28s} {net.mean() * 100:+.3f}%",
                     f"  {'exit mix':28s} {closed['exit_reason'].value_counts().to_dict() if len(closed) else {}}",
                     f"  {'stats':28s} {st}"]
            lines += [f"  {k:28s} {v}" for k, v in report.items() if k != "checks"]
            lines += [f"    [{'PASS' if ok else 'FAIL'}] {c}" for c, ok in report["checks"].items()]
            out.write("\n".join(lines) + "\n")
            out.flush()
            print(f"{code} {w}: cagr {report.get('cagr_pct')} nifty {report.get('nifty_cagr_pct')} "
                  f"dd {report.get('max_drawdown_pct')} win {(net > 0).mean() * 100:.1f}% "
                  f"net/trade {net.mean() * 100:+.2f}% n {len(closed)} checks {sum(report['checks'].values())}/6 {st}", flush=True)
    out.close()


if __name__ == "__main__":
    main()
