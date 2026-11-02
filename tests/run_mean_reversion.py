"""
Falcon -- pre-registered mean-reversion test (docs/mean_reversion_preregistration.md).

    python tests/run_mean_reversion.py > data/mean_reversion_result.txt

Runs strategy MR (and the reported-only 3xATR-stop variant) on W1
(2019-01-01 -> 2026-10-30) and, if data/pit/ reaches back to 2007, W2
(2008-01-01 -> 2017-12-31). Verdict: PASS only if both windows pass.
"""
import os
import sys
sys.path.insert(0, ".")

import pandas as pd

from backtesting.pit_strategies import judge_mean_reversion, make_panel, run_mean_reversion

PREREG = "docs/mean_reversion_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31")}
TOP_N = 100


def _nifty():
    path = "data/pit_sources/indices.parquet"
    if os.path.exists(path):
        idx = pd.read_parquet(path)
        n = idx[idx["Index"] == "NIFTY 50"].set_index("Date")["Close"].sort_index()
        if len(n):
            return n, "NSE NIFTY 50 (data/pit_sources/indices.parquet)"
    n = pd.read_parquet("data/raw/^NSEI.parquet")
    n["Date"] = pd.to_datetime(n["Date"])
    if n["Date"].dt.tz is not None:
        n["Date"] = n["Date"].dt.tz_localize(None)
    s = n.set_index("Date")["Close"].sort_index()
    s.index = s.index.normalize()
    return s, "Yahoo ^NSEI"


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    panel = make_panel(prices, universe[universe["rank"] <= TOP_N])
    nifty, nifty_source = _nifty()
    print(f"Universe: top {TOP_N} by traded value; benchmark: {nifty_source}")
    verdicts = {}
    for name, (start, end) in WINDOWS.items():
        start, end = pd.Timestamp(start), pd.Timestamp(end)
        if prices["Date"].min() > start - pd.Timedelta(days=300) or prices["Date"].max() < end - pd.Timedelta(days=10):
            print(f"\n{name} {start.date()} -> {end.date()}: data/pit/ does not cover it yet -- skipped")
            continue
        for label, stop in (("MR (primary)", None), ("MR + 3xATR disaster stop (reported only)", 3.0)):
            equity, trades = run_mean_reversion(panel, start, end, nifty, stop_atr_mult=stop)
            report = judge_mean_reversion(equity, trades, nifty)
            print(f"\n{'=' * 70}\n{name} {start.date()} -> {end.date()}  {label}\n{'=' * 70}")
            for k, v in report.items():
                if k not in ("checks",):
                    print(f"  {k:26s} {v}")
            for check, ok in report["checks"].items():
                print(f"    [{'PASS' if ok else 'FAIL'}] {check}")
            if stop is None:
                verdicts[name] = report["verdict"]
                trades.to_csv(f"data/mean_reversion_trades_{name}.csv", index=False)
    print(f"\nWindow verdicts: {verdicts}")
    if set(verdicts) == set(WINDOWS):
        print("OVERALL: " + ("PROVISIONAL EDGE (both windows pass) -- next is paper trading"
                             if all(v == "PASS" for v in verdicts.values()) else "NO DEMONSTRATED EDGE"))
    else:
        print("OVERALL: pending -- W2 needs the 2007-2017 data")


if __name__ == "__main__":
    main()
