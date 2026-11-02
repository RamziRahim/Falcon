"""
Falcon -- run the two pre-registered redesign strategies on 2019-01-01 ..
2024-07-31 (survivorship-free data) and apply the pre-registered verdict.

    python tests/run_redesign_tests.py > data/redesign_result.txt

Needs data/pit/ (tests/build_pit_universe.py). Refuses to run unless
docs/redesign_preregistration.md is marked FROZEN, so the rules are fixed
before any result exists.
"""
import sys
sys.path.insert(0, ".")

import pandas as pd

from backtesting.pit_strategies import equal_weight_universe, judge, make_panel, run_breakout, run_momentum

START, END = pd.Timestamp("2019-01-01"), pd.Timestamp("2024-07-31")
PREREG = "docs/redesign_preregistration.md"


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen yet -- approve and freeze the rules before running.")
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    panel = make_panel(prices, universe)
    nifty = pd.read_parquet("data/raw/^NSEI.parquet")
    nifty["Date"] = pd.to_datetime(nifty["Date"])
    if nifty["Date"].dt.tz is not None:
        nifty["Date"] = nifty["Date"].dt.tz_localize(None)
    nifty = nifty.set_index("Date")["Close"].sort_index()
    nifty.index = nifty.index.normalize()
    ew = equal_weight_universe(panel, START, END)

    for name, runner in (("A: monthly momentum rotation", run_momentum), ("B: simple breakout", run_breakout)):
        equity, trades = runner(panel, START, END)
        trades.to_csv(f"data/redesign_trades_{name[0]}.csv", index=False)
        report = judge(equity, trades, nifty, ew)
        print(f"\n{'=' * 70}\nStrategy {name}  ({START.date()} -> {END.date()})\n{'=' * 70}")
        for k, v in report.items():
            if k != "checks":
                print(f"  {k:28s} {v}")
        print("  Pre-registered checks:")
        for check, ok in report["checks"].items():
            print(f"    [{'PASS' if ok else 'FAIL'}] {check}")


if __name__ == "__main__":
    main()
