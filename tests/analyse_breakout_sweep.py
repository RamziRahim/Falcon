"""
Falcon -- descriptive analysis (not a strategy test): after a breakout, does
the price dip below the level first ("sweep") and then reach +8%, or the
other way round?

Same breakout events as tests/analyse_breakout_retracement.py. Over the 20
sessions after the breakout day, with level L:
  sweep  = first session whose low <= L x 0.97
  target = first session whose high >= L x 1.08
A session with both counts as sweep-first (conservative, same as the
backtests' stop-wins-ties rule).

    python tests/analyse_breakout_sweep.py > data/breakout_sweep.txt
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from backtesting.fixed_bracket import entries_b, entries_f, entries_s
from backtesting.pit_strategies import make_panel
from tests.analyse_breakout_retracement import HOLD, WINDOWS, events
from tests.run_mean_reversion import _nifty

SWEEP, TARGET = 0.97, 1.08


def classify(panel, ev):
    lo, hi = panel.low.to_numpy(), panel.high.to_numpy()
    rows = []
    for j, b, L in ev:
        if not np.isfinite(L) or L <= 0:
            continue
        lows, highs = lo[b + 1: b + 1 + HOLD, j], hi[b + 1: b + 1 + HOLD, j]
        if not np.isfinite(lows).any():
            continue
        s = np.flatnonzero(lows <= L * SWEEP)
        t = np.flatnonzero(highs >= L * TARGET)
        s0, t0 = (s[0] if len(s) else None), (t[0] if len(t) else None)
        if t0 is None and s0 is None:
            kind = "neither"
        elif s0 is None:
            kind = "+8% with no dip >3% below"
        elif t0 is None:
            kind = "dipped, never reached +8%"
        elif s0 <= t0:
            depth = np.nanmin(lows[: t0 + 1]) / L - 1
            kind = "dipped first, then +8%"
            rows.append({"kind": kind, "depth": depth, "days": t0 - s0})
            continue
        else:
            kind = "+8% first, then dipped"
        rows.append({"kind": kind, "depth": np.nan, "days": np.nan})
    return pd.DataFrame(rows)


def main():
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    panel = make_panel(prices, universe)
    del prices
    nifty, _ = _nifty()
    order = ["+8% with no dip >3% below", "dipped first, then +8%", "+8% first, then dipped",
             "dipped, never reached +8%", "neither"]
    for wname, (s, e) in WINDOWS.items():
        s, e = pd.Timestamp(s), pd.Timestamp(e)
        setups = pd.read_parquet(f"data/pit/falcon_setups_{s.date()}_{e.date()}.parquet")
        for label, fn in [("B 52-week breakout", entries_b(panel)), ("S momentum breakout", entries_s(panel, nifty)),
                          ("F Falcon setup", entries_f(panel, setups))]:
            d = classify(panel, events(panel, s, e, fn))
            share = d["kind"].value_counts(normalize=True) * 100
            print(f"\n{label}  {wname}: {len(d)} breakouts")
            for k in order:
                print(f"  {k:30s} {share.get(k, 0.0):5.1f}%")
            sw = d[d["kind"] == "dipped first, then +8%"]
            if len(sw):
                print(f"  dip-then-+8% cases: median low {sw.depth.median() * 100:+.1f}% vs level "
                      f"(25-75%: {sw.depth.quantile(.75) * 100:+.1f}% .. {sw.depth.quantile(.25) * 100:+.1f}%), "
                      f"median {sw.days.median():.0f} sessions from the dip to +8%")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
