"""
Falcon -- descriptive (not a strategy test): strategy #3's breakouts
(data/s_breakout_outcomes.csv: every filled 20-day-high breakout with the
Nifty above its 50-day average) with a fixed 1:1 bracket: stop = entry x 0.95,
target = entry x 1.05, followed for 20 sessions from the fill day.

Classes (stop wins same-day ties; the fill day's low counts for the stop,
retracement is measured from the session after the fill):
  direct           : target hit, price never came back to the entry first
  shallow retrace  : target hit after coming back to the entry, never below entry x 0.975
  deep retrace     : target hit after dipping below entry x 0.975 (but not to the stop)
  stopped          : stop hit before the target
  neither          : still open after 20 sessions (sold at the close)

    python tests/analyse_s_bracket5.py > data/s_bracket5.txt
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from backtesting.pit_strategies import make_panel

WINDOWS = {"2019-26": ("2019-01-01", "2026-10-30"), "2008-17": ("2008-01-01", "2017-12-31"), "2018": ("2018-01-01", "2018-12-31")}
HOLD, PCT = 20, 0.05


def main():
    d = pd.read_csv("data/s_breakout_outcomes.csv", parse_dates=["date"])
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    panel = make_panel(prices, universe)
    del prices
    H, L, C = (x.to_numpy(float) for x in (panel.high, panel.low, panel.close))
    cols = {e: j for j, e in enumerate(panel.close.columns)}
    pos = {dt: k for k, dt in enumerate(panel.sessions)}
    out = []
    for r in d.itertuples():
        j, f = cols[r.entity], pos[r.date]
        hi, lo, cl = H[f: f + HOLD, j], L[f: f + HOLD, j], C[f: f + HOLD, j]
        stop, tgt = r.entry * (1 - PCT), r.entry * (1 + PCT)
        ks = np.flatnonzero(lo <= stop)
        kt = np.flatnonzero(hi >= tgt)
        ks = ks[0] if len(ks) else None
        kt = kt[0] if len(kt) else None
        if ks is not None and (kt is None or ks <= kt):
            cls, res = "stopped", -PCT
        elif kt is not None:
            path = lo[1: kt + 1] if kt >= 1 else np.array([])
            if kt == 0 or not (path <= r.entry).any():
                cls = "direct"
            elif (path < r.entry * 0.975).any():
                cls = "deep retrace"
            else:
                cls = "shallow retrace"
            res = PCT
        else:
            cls, res = "neither", cl[-1] / r.entry - 1
        out.append({"date": r.date, "cls": cls, "res": res, "days": (kt if cls not in ("stopped", "neither") else ks) })
    o = pd.DataFrame(out)
    order = ["direct", "shallow retrace", "deep retrace", "stopped", "neither"]
    labels = {"direct": "target hit directly (never back to entry)",
              "shallow retrace": "target hit after coming back to entry (dip < 2.5%)",
              "deep retrace": "target hit after a deeper dip (2.5% to 5%)",
              "stopped": "stop hit (-5%) before target",
              "neither": "neither within 20 sessions (sold at close)"}
    for w, (a, b) in WINDOWS.items():
        x = o[(o.date >= a) & (o.date <= b)]
        n = len(x)
        print(f"\n{w}: {n} breakouts, stop -5% / target +5%")
        for c in order:
            g = x[x.cls == c]
            extra = f"  median result {g.res.median() * 100:+.1f}%" if c == "neither" else \
                    (f"  median {g.days.median():.0f} sessions" if len(g) else "")
            print(f"  {labels[c]:52s} {len(g):5d} ({len(g) / n * 100:5.1f}%){extra}")
        hit = x.cls.isin(order[:3]).mean() * 100
        print(f"  total target hits {hit:.1f}%  | mean result before costs {x.res.mean() * 100:+.2f}% per trade"
              f"  | after ~0.4% round-trip costs {x.res.mean() * 100 - 0.4:+.2f}%")


if __name__ == "__main__":
    main()
