"""
Falcon -- descriptive analysis (not a strategy test): after a breakout, how
often does the price come back to the breakout level?

Breakouts, all universe signals, one per stock per 20 sessions:
  B: close at a 52-week closing high on >= 1.5x volume (level = that close)
  S: next session's high takes out the 20-session high trigger (level = trigger)
  F: Falcon setup whose pivot trades within 5 sessions (level = pivot)

For each breakout day d with level L, over the next 10 sessions:
  retest      = some low <= L x 1.01  (back to within 1% of the level)
  deep        = some low <= L x 0.97  (more than 3% below the level)
  never       = lows stay above L x 1.01
and the outcome 20 sessions after d: close / L - 1, and whether any high
reached L x 1.08.

    python tests/analyse_breakout_retracement.py > data/breakout_retracement.txt
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from backtesting.fixed_bracket import entries_b, entries_f, entries_s
from backtesting.pit_strategies import make_panel
from tests.run_mean_reversion import _nifty

WINDOWS = {"2019-26": ("2019-01-01", "2026-10-30"), "2008-17": ("2008-01-01", "2017-12-31")}
LOOK, HOLD, GAP = 10, 20, 20


def events(panel, start, end, fn):
    """(entity, breakout_idx, level) from the order generator, no slot limits."""
    hi = panel.high.to_numpy()
    cols = {e: j for j, e in enumerate(panel.close.columns)}
    out, last = [], {}
    for i, day in enumerate(panel.sessions):
        if day < start or day > end or i + LOOK + HOLD >= len(panel.sessions):
            continue
        for od in fn(i, day, set()):
            e = od[1]
            j = cols.get(e)
            if j is None:
                continue
            if od[0] == "market":                       # B: signal day is the breakout
                b, lvl = i, od[2]
            else:                                       # S, F: first session the trigger trades
                lvl, valid = od[2], od[5]
                hit = [k for k in range(i + 1, i + 1 + valid) if hi[k, j] >= lvl]
                if not hit:
                    continue
                b = hit[0]
            if b - last.get(e, -10**9) < GAP:
                continue
            last[e] = b
            out.append((j, b, lvl))
    return out


def describe(panel, ev):
    lo, hi, cl = panel.low.to_numpy(), panel.high.to_numpy(), panel.close.to_numpy()
    rows = []
    for j, b, L in ev:
        if not np.isfinite(L) or L <= 0:
            continue
        lows = lo[b + 1: b + 1 + LOOK, j]
        if not np.isfinite(lows).any():
            continue
        m = np.nanmin(lows)
        first = int(np.argmax(lows <= L * 1.01)) + 1 if (lows <= L * 1.01).any() else None
        c20 = cl[b + HOLD, j]
        rows.append({"retest": m <= L * 1.01, "deep": m <= L * 0.97, "days_to_retest": first,
                     "min_vs_level": m / L - 1, "ret20": c20 / L - 1 if np.isfinite(c20) else np.nan,
                     "hit8": np.nanmax(hi[b + 1: b + 1 + HOLD, j]) >= L * 1.08})
    return pd.DataFrame(rows)


def main():
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    panel = make_panel(prices, universe)
    del prices
    nifty, _ = _nifty()
    for wname, (s, e) in WINDOWS.items():
        s, e = pd.Timestamp(s), pd.Timestamp(e)
        setups = pd.read_parquet(f"data/pit/falcon_setups_{s.date()}_{e.date()}.parquet")
        for label, fn in [("B 52-week breakout", entries_b(panel)), ("S momentum breakout", entries_s(panel, nifty)),
                          ("F Falcon setup", entries_f(panel, setups))]:
            d = describe(panel, events(panel, s, e, fn))
            n = len(d)
            never = d[~d.retest]
            shallow = d[d.retest & ~d.deep]
            deep = d[d.deep]
            print(f"\n{label}  {wname}: {n} breakouts")
            print(f"  came back to the level (within 1%) in 10 sessions : {d.retest.mean() * 100:5.1f}%  "
                  f"(median {d.days_to_retest.median():.0f} sessions after the breakout)")
            print(f"    of which only a light retest (not >3% below)     : {len(shallow) / n * 100:5.1f}%")
            print(f"    of which fell more than 3% below the level        : {len(deep) / n * 100:5.1f}%")
            print(f"  never came back                                     : {len(never) / n * 100:5.1f}%")
            print(f"  20 sessions later vs level  (median / % above):")
            for name, g in [("never came back", never), ("light retest", shallow), ("fell >3% below", deep), ("all", d)]:
                print(f"    {name:18s} {g.ret20.median() * 100:+6.1f}%  {(g.ret20 > 0).mean() * 100:5.1f}% above  "
                      f"reached +8%: {g.hit8.mean() * 100:5.1f}%   (n={len(g)})")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
