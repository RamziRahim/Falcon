"""
Falcon -- fixed 1:3 bracket (stop -2%, target +6%, 5 x 20%) on the F, S, B and
MR entry signals, per docs/fixed_rr_preregistration.md.

    python tests/run_fixed_rr.py > data/fixed_rr_result.txt
"""
import sys
sys.path.insert(0, ".")

import gc

import pandas as pd

from backtesting.fixed_bracket import entries_b, entries_f, entries_mr, entries_s, run_bracket
from backtesting.pit_strategies import equal_weight_universe, judge, make_panel
from tests.run_mean_reversion import _nifty

PREREG = "docs/fixed_rr_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31")}


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    panel = make_panel(prices, universe)
    panel100 = make_panel(prices, universe[universe["rank"] <= 100])
    del prices
    gc.collect()
    nifty, src = _nifty()
    print(f"Benchmark: {src}")
    verdicts = {}
    for name, (start, end) in WINDOWS.items():
        start, end = pd.Timestamp(start), pd.Timestamp(end)
        ew = equal_weight_universe(panel, start, end)
        setups = pd.read_parquet(f"data/pit/falcon_setups_{start.date()}_{end.date()}.parquet")
        combos = {
            "F": (panel, lambda: entries_f(panel, setups)),
            "S": (panel, lambda: entries_s(panel, nifty)),
            "B": (panel, lambda: entries_b(panel)),
            "MR": (panel100, lambda: entries_mr(panel100, nifty)),
        }
        for label, (p, make) in combos.items():
            equity, trades = run_bracket(p, start, end, make())
            trades.to_csv(f"data/fixed_rr_trades_{label}_{name}.csv", index=False)
            report = judge(equity, trades, nifty, ew)
            closed = trades[trades["exit_reason"] != "OPEN_AT_END"] if not trades.empty else trades
            net = closed["pnl"] / closed["cost_basis"] if len(closed) else pd.Series(dtype=float)
            print(f"\n{'=' * 70}\n{label} entries + 1:3 bracket  {name} {start.date()} -> {end.date()}\n{'=' * 70}")
            print(f"  {'trades (closed)':28s} {len(closed)}")
            print(f"  {'win rate after costs':28s} {(net > 0).mean() * 100:.1f}%")
            print(f"  {'avg win / avg loss':28s} {net[net > 0].mean() * 100:+.2f}% / {net[net <= 0].mean() * 100:+.2f}%")
            print(f"  {'mean net per trade':28s} {net.mean() * 100:+.3f}%")
            print(f"  {'exit mix':28s} {closed['exit_reason'].value_counts().to_dict()}")
            same = closed[closed["entry_date"] == closed["exit_date"]]
            print(f"  {'exited on the fill day':28s} {len(same)} ({same['exit_reason'].value_counts().to_dict()})")
            for k, v in report.items():
                if k != "checks":
                    print(f"  {k:28s} {v}")
            for check, ok in report["checks"].items():
                print(f"    [{'PASS' if ok else 'FAIL'}] {check}")
            verdicts.setdefault(label, {})[name] = "PASS" if report["verdict"].startswith("EDGE") else "FAIL"
    print(f"\nVerdicts: {verdicts}")
    for label, v in verdicts.items():
        print(f"{label}: " + ("PROVISIONAL EDGE (both windows)" if all(x == "PASS" for x in v.values()) else "NO DEMONSTRATED EDGE"))


if __name__ == "__main__":
    main()
