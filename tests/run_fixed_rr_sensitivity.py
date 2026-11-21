"""
SENSITIVITY ONLY (not a verdict): the S and F entries fill on a buy-stop
during the day, so the fill day's low may have come BEFORE the breakout.
Re-runs those two with the optimistic assumption that the fill-day stop counts
only if the close is at or below it. Both brackets, both windows.

    python tests/run_fixed_rr_sensitivity.py > data/fixed_rr_sensitivity.txt
"""
import sys
sys.path.insert(0, ".")

import gc

import pandas as pd

import backtesting.fixed_bracket as fb
from backtesting.pit_strategies import make_panel
from tests.run_mean_reversion import _nifty

WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31")}


def main():
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    panel = make_panel(prices, universe)
    del prices
    gc.collect()
    nifty, _ = _nifty()
    nifty_c = nifty
    for stop, target in ((0.02, 0.06), (0.03, 0.06)):
        fb.STOP_PCT, fb.TARGET_PCT = stop, target
        for name, (start, end) in WINDOWS.items():
            start, end = pd.Timestamp(start), pd.Timestamp(end)
            setups = pd.read_parquet(f"data/pit/falcon_setups_{start.date()}_{end.date()}.parquet")
            for label, make in (("F", lambda: fb.entries_f(panel, setups)), ("S", lambda: fb.entries_s(panel, nifty))):
                eq, tr = fb.run_bracket(panel, start, end, make(), optimistic_stop_fill_day=True)
                closed = tr[tr["exit_reason"] != "OPEN_AT_END"]
                net = closed["pnl"] / closed["cost_basis"]
                yrs = (eq.index[-1] - eq.index[0]).days / 365.25
                cagr = ((eq["equity"].iloc[-1] / eq["equity"].iloc[0]) ** (1 / yrs) - 1) * 100
                n = nifty_c.reindex(nifty_c.index.union(eq.index)).ffill().reindex(eq.index)
                ncagr = ((n.iloc[-1] / n.iloc[0]) ** (1 / yrs) - 1) * 100
                print(f"{label} -{stop:.0%}/+{target:.0%} {name}: trades {len(closed)}, win {(net > 0).mean() * 100:.1f}%, "
                      f"mean net {net.mean() * 100:+.2f}%, CAGR {cagr:.1f}% vs Nifty {ncagr:.1f}%, "
                      f"max DD {((eq['equity'] / eq['equity'].cummax()) - 1).min() * 100:.1f}%")


if __name__ == "__main__":
    main()
