"""
Falcon -- descriptive check: do breakout days behave differently from random
days in the same stocks?

For every breakout event (same events as tests/analyse_breakout_retracement.py),
pick a random session for the same stock in the same window (seeded), with
level = that session's close, and classify both with the same rules as
tests/analyse_breakout_sweep.py (dip = low <= L x 0.97, target = high >= L x 1.08,
20 sessions; same-day both counts as dip first).

    python tests/analyse_breakout_vs_random.py > data/breakout_vs_random.txt
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from backtesting.fixed_bracket import entries_b, entries_f, entries_s
from backtesting.pit_strategies import make_panel
from tests.analyse_breakout_retracement import HOLD, LOOK, WINDOWS, events
from tests.analyse_breakout_sweep import classify
from tests.run_mean_reversion import _nifty

ORDER = ["+8% with no dip >3% below", "dipped first, then +8%", "+8% first, then dipped",
         "dipped, never reached +8%", "neither"]


def random_twins(panel, ev, start, end, rng):
    sessions = panel.sessions
    lo_i = int(sessions.searchsorted(start))
    hi_i = min(int(sessions.searchsorted(end, side="right")), len(sessions) - LOOK - HOLD - 1)
    cl = panel.close.to_numpy()
    out = []
    for j, _, _ in ev:
        for _ in range(20):
            b = int(rng.integers(lo_i, hi_i))
            if np.isfinite(cl[b, j]):
                out.append((j, b, cl[b, j]))
                break
    return out


def main():
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    panel = make_panel(prices, universe)
    del prices
    nifty, _ = _nifty()
    rng = np.random.default_rng(20261104)
    for wname, (s, e) in WINDOWS.items():
        s, e = pd.Timestamp(s), pd.Timestamp(e)
        setups = pd.read_parquet(f"data/pit/falcon_setups_{s.date()}_{e.date()}.parquet")
        for label, fn in [("B 52-week breakout", entries_b(panel)), ("S momentum breakout", entries_s(panel, nifty)),
                          ("F Falcon setup", entries_f(panel, setups))]:
            ev = events(panel, s, e, fn)
            real = classify(panel, ev)["kind"].value_counts(normalize=True) * 100
            rand = classify(panel, random_twins(panel, ev, s, e, rng))["kind"].value_counts(normalize=True) * 100
            print(f"\n{label}  {wname}: {len(ev)} breakouts vs the same number of random days in the same stocks")
            print(f"  {'':30s} {'breakout':>9s} {'random':>8s}")
            for k in ORDER:
                print(f"  {k:30s} {real.get(k, 0.0):8.1f}% {rand.get(k, 0.0):7.1f}%")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
