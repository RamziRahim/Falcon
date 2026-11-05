"""
Falcon -- S+ per docs/s_plus_preregistration.md (one process, shared panel and
entry generator).

    python tests/run_s_plus.py > data/s_plus.log
"""
import sys
sys.path.insert(0, ".")

import gc

import pandas as pd

from backtesting.fixed_bracket import entries_s
from backtesting.pit_strategies import equal_weight_universe, judge, make_panel
from backtesting.s_plus import run_s_plus
from tests.run_mean_reversion import _nifty

PREREG = "docs/s_plus_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "H2018": ("2018-01-01", "2018-12-31")}
ALL = dict(market_filter=True, time_stop=40, atr_cap=True)
RUNS = [  # (label, settings, windows)
    ("S+ (all three)", ALL, ("W1", "W2", "H2018")),
    ("original #3", dict(), ("H2018",)),
    ("only market filter", dict(market_filter=True), ("W1", "W2")),
    ("only 40-session hold", dict(time_stop=40), ("W1", "W2")),
    ("only ATR-capped stop", dict(atr_cap=True), ("W1", "W2")),
]


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
    out = open("data/s_plus_result.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}\n")
    for label, kw, wins in RUNS:
        for w in wins:
            a, b = (pd.Timestamp(x) for x in WINDOWS[w])
            equity, trades, skipped = run_s_plus(panel, a, b, fn, nifty, **kw)
            slug = label.split(" (")[0].replace(" ", "_").replace("#", "").replace("+", "plus")
            trades.to_csv(f"data/s_plus_trades_{slug}_{w}.csv", index=False)
            report = judge(equity, trades, nifty, ew[w])
            closed = trades[trades["exit_reason"] != "OPEN_AT_END"] if not trades.empty else trades
            net = closed["pnl"] / closed["cost_basis"] if len(closed) else pd.Series(dtype=float)
            lines = [f"\n{'=' * 70}\n{label}  {w} {a.date()} -> {b.date()}\n{'=' * 70}",
                     f"  {'trades (closed)':28s} {len(closed)}",
                     f"  {'win rate after costs':28s} {(net > 0).mean() * 100:.1f}%",
                     f"  {'avg win / avg loss':28s} {net[net > 0].mean() * 100:+.2f}% / {net[net <= 0].mean() * 100:+.2f}%",
                     f"  {'mean net per trade':28s} {net.mean() * 100:+.3f}%",
                     f"  {'exit mix':28s} {closed['exit_reason'].value_counts().to_dict() if len(closed) else {}}",
                     f"  {'skipped':28s} {skipped}"]
            lines += [f"  {k:28s} {v}" for k, v in report.items() if k != "checks"]
            lines += [f"    [{'PASS' if ok else 'FAIL'}] {c}" for c, ok in report["checks"].items()]
            out.write("\n".join(lines) + "\n")
            out.flush()
            print(f"{label} {w}: cagr {report.get('cagr_pct')} nifty {report.get('nifty_cagr_pct')} ew {report.get('ew_universe_cagr_pct')} "
                  f"dd {report.get('max_drawdown_pct')} win {(net > 0).mean() * 100:.1f}% n {len(closed)} {report['verdict']}", flush=True)
    out.close()


if __name__ == "__main__":
    main()
