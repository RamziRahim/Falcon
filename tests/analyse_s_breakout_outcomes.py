"""
Falcon -- descriptive (not a strategy test): what happened after strategy #3's
20-day-high breakouts (S signals, Nifty > 50-SMA filter, every filled signal,
no slot limit), over the 20 sessions after the fill.

  level  = the 20-day-high trigger, entry = max(level, open of the fill day)
  stop   = swing-low stop (swing_risk.swing_stop at the signal day); skip if > 15%
  target = entry + 3 x (entry - stop)   and, separately, entry x 1.05
  retest = a later low <= level (price came back to the breakout level)
Same-day ambiguity: stop first. Fill-day low counts (conservative, as in the backtests).

    python tests/analyse_s_breakout_outcomes.py > data/s_breakout_outcomes.txt
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from backtesting.fixed_bracket import entries_s
from backtesting.pit_strategies import make_panel
from backtesting.swing_risk import pivot_lows, swing_stop
from tests.run_mean_reversion import _nifty

WINDOWS = {"2019-26": ("2019-01-01", "2026-10-30"), "2008-17": ("2008-01-01", "2017-12-31"), "2018": ("2018-01-01", "2018-12-31")}
HOLD = 20


def first(mask):
    k = np.flatnonzero(mask)
    return k[0] if len(k) else None


def main():
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    panel = make_panel(prices, universe)
    del prices
    nifty, _ = _nifty()
    s = panel.sessions
    nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
    ok = (nf > nf.rolling(50, min_periods=50).mean()).to_numpy()
    fn = entries_s(panel, nifty)
    piv = pivot_lows(panel)
    pc = panel.close.shift(1)
    tr = np.maximum(panel.high - panel.low, np.maximum((panel.high - pc).abs(), (panel.low - pc).abs()))
    atr = tr.rolling(14, min_periods=14).mean()
    O, H, L, C = (x.to_numpy(float) for x in (panel.open, panel.high, panel.low, panel.close))
    cols = {e: j for j, e in enumerate(panel.close.columns)}
    rows = []
    for i, day in enumerate(s):
        if day < pd.Timestamp("2008-01-01") or i + 1 + HOLD >= len(s) or not ok[i]:
            continue
        for od in fn(i, day, set()):
            e, lvl, gap = od[1], od[2], od[3]
            j, f = cols[e], i + 1
            if not (np.isfinite(O[f, j]) and H[f, j] >= lvl and O[f, j] <= lvl * (1 + gap)):
                continue
            entry = max(lvl, O[f, j])
            stop = swing_stop(panel, piv, atr, i, e, min(lvl, C[i, j]))
            if stop is None or entry <= stop or (entry - stop) / entry > 0.15:
                continue
            tgt3 = entry + 3 * (entry - stop)
            lo, hi, cl = L[f: f + HOLD, j], H[f: f + HOLD, j], C[f: f + HOLD, j]
            if not np.isfinite(lo).all():
                continue
            k_stop, k_t3, k_t5 = first(lo <= stop), first(hi >= tgt3), first(hi >= entry * 1.05)
            k_ret = first(lo[1:] <= lvl)
            k_ret = None if k_ret is None else k_ret + 1
            def before(a, b):           # a happens strictly before b (stop wins ties)
                return a is not None and (b is None or a < b)
            rows.append({"date": s[f], "entity": e, "sym": panel.symbol.get(e, e) if hasattr(panel, "symbol") else e,
                         "entry": entry, "stop": stop, "level": lvl, "risk_pct": (entry - stop) / entry * 100,
                         "t3": before(k_t3, k_stop) or (k_t3 is not None and k_stop is None),
                         "stopped": k_stop is not None and (k_t3 is None or k_stop <= k_t3),
                         "t5": k_t5 is not None and (k_stop is None or k_t5 < k_stop),
                         "stopped_before5": k_stop is not None and (k_t5 is None or k_stop <= k_t5),
                         "retest_before_t3": k_ret is not None and (k_t3 is None or k_ret <= k_t3),
                         "retest_before_t5": k_ret is not None and (k_t5 is None or k_ret <= k_t5),
                         "end_ret": cl[-1] / entry - 1})
    d = pd.DataFrame(rows)
    d.to_csv("data/s_breakout_outcomes.csv", index=False)
    for w, (a, b) in WINDOWS.items():
        x = d[(d.date >= a) & (d.date <= b)]
        n = len(x)
        pct = lambda m: f"{m.sum():6d} ({m.mean() * 100 if n else 0:5.1f}%)"
        neither3 = ~x.t3 & ~x.stopped
        print(f"\n{w}: {n} filled breakouts (Nifty above its 50-day average), median risk {x.risk_pct.median():.1f}%")
        print("  1:3 target, within 20 sessions:")
        print(f"    hit target                            {pct(x.t3)}")
        print(f"      after coming back to the breakout   {pct(x.t3 & x.retest_before_t3)}")
        print(f"      without coming back                 {pct(x.t3 & ~x.retest_before_t3)}")
        print(f"    hit stop first (failed)               {pct(x.stopped)}")
        print(f"    neither (sold at 20 sessions)         {pct(neither3)}  "
              f"median {x[neither3].end_ret.median() * 100:+.1f}%")
        print("  +5% target, within 20 sessions:")
        print(f"    reached +5% before the stop           {pct(x.t5)}")
        print(f"      after coming back to the breakout   {pct(x.t5 & x.retest_before_t5)}")
        print(f"      without coming back                 {pct(x.t5 & ~x.retest_before_t5)}")
        print(f"    stopped before +5%                    {pct(x.stopped_before5)}")
        print(f"  came back to the breakout level at all  {pct(x.retest_before_t3 | x.retest_before_t5)}")


if __name__ == "__main__":
    main()
