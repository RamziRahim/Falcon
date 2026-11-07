"""Strategy A (frozen) on the unseen 2008-2017 window -- see the dated note of 2026-11-03 in docs/redesign_preregistration.md."""
import sys; sys.path.insert(0, ".")
import pandas as pd
from backtesting.pit_strategies import equal_weight_universe, judge, make_panel, run_momentum
from tests.run_mean_reversion import _nifty
prices = pd.read_parquet("data/pit/prices_adjusted.parquet"); universe = pd.read_parquet("data/pit/universe_monthly.parquet")
panel = make_panel(prices, universe); del prices
nifty, src = _nifty(); start, end = pd.Timestamp("2008-01-01"), pd.Timestamp("2017-12-31")
eq, tr = run_momentum(panel, start, end); tr.to_csv("data/momentum_trades_A_W2.csv", index=False)
rep = judge(eq, tr, nifty, equal_weight_universe(panel, start, end))
print(f"Strategy A on W2 {start.date()} -> {end.date()} (benchmark {src})")
for k, v in rep.items():
    if k != "checks": print(f"  {k:28s} {v}")
for c, ok in rep["checks"].items(): print(f"    [{'PASS' if ok else 'FAIL'}] {c}")
