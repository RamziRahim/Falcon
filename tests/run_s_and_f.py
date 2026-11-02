"""
Falcon -- run strategies S and F (docs/s_and_f_preregistration.md) on W1 and,
when the data covers it, W2. A strategy passes only if both windows pass.

    python tests/run_s_and_f.py > data/s_and_f_result.txt

F needs data/pit/falcon_setups_<start>_<end>.parquet for each window
(tests/scan_falcon_setups.py).
"""
import os
import sys
sys.path.insert(0, ".")

import pandas as pd

from backtesting.breakout_entries import run_strategy_f, run_strategy_s
from backtesting.pit_strategies import equal_weight_universe, judge, make_panel
from tests.run_mean_reversion import _nifty

PREREG = "docs/s_and_f_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31")}


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    panel = make_panel(prices, universe)
    nifty, src = _nifty()
    print(f"Benchmark: {src}")
    verdicts = {"S": {}, "F": {}}
    for name, (start, end) in WINDOWS.items():
        start, end = pd.Timestamp(start), pd.Timestamp(end)
        if prices["Date"].min() > start - pd.Timedelta(days=300) or prices["Date"].max() < end - pd.Timedelta(days=10):
            print(f"\n{name}: data/pit/ does not cover {start.date()} -> {end.date()} yet -- skipped")
            continue
        ew = equal_weight_universe(panel, start, end)
        runs = [("S", lambda: run_strategy_s(panel, start, end, nifty))]
        setups_path = f"data/pit/falcon_setups_{start.date()}_{end.date()}.parquet"
        if os.path.exists(setups_path):
            setups = pd.read_parquet(setups_path)
            runs.append(("F", lambda: run_strategy_f(panel, setups, start, end)))
        else:
            print(f"\n{name}: {setups_path} missing -- F skipped (run tests/scan_falcon_setups.py)")
        for label, run in runs:
            equity, trades = run()
            trades.to_csv(f"data/s_and_f_trades_{label}_{name}.csv", index=False)
            report = judge(equity, trades, nifty, ew)
            closed = trades[trades["exit_reason"] != "OPEN_AT_END"] if not trades.empty else trades
            win = (closed["pnl"] > 0).mean() * 100 if len(closed) else float("nan")
            print(f"\n{'=' * 70}\nStrategy {label}  {name} {start.date()} -> {end.date()}\n{'=' * 70}")
            for k, v in report.items():
                if k != "checks":
                    print(f"  {k:28s} {v}")
            print(f"  {'win_rate_pct (closed)':28s} {win:.1f}")
            print(f"  {'exit reasons':28s} {closed['exit_reason'].value_counts().to_dict() if len(closed) else {}}")
            for check, ok in report["checks"].items():
                print(f"    [{'PASS' if ok else 'FAIL'}] {check}")
            verdicts[label][name] = "PASS" if report["verdict"].startswith("EDGE") else "FAIL"
    print(f"\nWindow verdicts: {verdicts}")
    for label, v in verdicts.items():
        if set(v) == set(WINDOWS):
            print(f"Strategy {label} OVERALL: " + ("PROVISIONAL EDGE (both windows)" if all(x == "PASS" for x in v.values())
                                                  else "NO DEMONSTRATED EDGE"))
        else:
            print(f"Strategy {label} OVERALL: pending (missing {sorted(set(WINDOWS) - set(v))})")


if __name__ == "__main__":
    main()
