"""
Falcon -- descriptive screen: IA's breakout (tests/analyse_ia_breakout.py,
volume > 1.5 x 50-day average) with four filters, each alone and all
together, vs random days in the same stock. Rules fixed before running
(2026-11-04):

  tightening : the High-Low range of the second half of the consolidation
               is < 75% of the range of the first half
  volume dry : average volume during the consolidation < the 50-session
               average volume on the BOS day
  RS > Nifty : the stock's 63-session return at the breakout close beats
               the Nifty 50's 63-session return
  market ok  : Nifty 50 close > its 200-session SMA on the breakout day
  all four   : every filter at once

Same measures and random-twin method as tests/analyse_ia_breakout.py.

    python tests/analyse_ia_breakout_filters.py > data/ia_breakout_filters.txt
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from backtesting.pit_strategies import make_panel
from tests.analyse_ia_breakout import HOLD, WINDOWS, find_breakouts, measure
from tests.run_mean_reversion import _nifty


def features(panel, ev, nifty):
    hi, lo = panel.high.to_numpy(float), panel.low.to_numpy(float)
    cl, vol = panel.close.to_numpy(float), panel.volume.to_numpy(float)
    vavg = panel.volume.rolling(50, min_periods=50).mean().shift(1).to_numpy(float)
    nf = nifty.reindex(nifty.index.union(panel.sessions)).ffill().reindex(panel.sessions).to_numpy(float)
    nsma = pd.Series(nf).rolling(200, min_periods=200).mean().to_numpy()
    out = []
    for j, t, L, b in ev:
        seg = np.arange(b + 1, t)
        half = len(seg) // 2
        first, second = seg[:half], seg[half:]
        w1 = hi[first, j].max() / lo[first, j].min() - 1 if half else np.nan
        w2 = hi[second, j].max() / lo[second, j].min() - 1
        rs = (cl[t, j] / cl[t - 63, j] - 1) - (nf[t] / nf[t - 63] - 1) if t >= 63 else np.nan
        out.append({"tight": w2 < 0.75 * w1, "dry": np.nanmean(vol[seg, j]) < vavg[b, j],
                    "rs": rs > 0, "market": nf[t] > nsma[t]})
    return pd.DataFrame(out)


def main():
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    panel = make_panel(prices, universe)
    del prices
    nifty, _ = _nifty()
    sessions, cols = panel.sessions, list(panel.close.columns)
    cl = panel.close.to_numpy(float)
    rng = np.random.default_rng(20261104)
    allev = find_breakouts(panel, 1.5, with_bos=True)
    for wname, (s, e) in WINDOWS.items():
        s, e = pd.Timestamp(s), pd.Timestamp(e)
        lo_i, hi_i = int(sessions.searchsorted(s)), int(sessions.searchsorted(e, side="right"))
        ev = [x for x in allev if lo_i <= x[1] < hi_i and cols[x[0]] in panel.universe_on(sessions[x[1]])]
        f = features(panel, ev, nifty)
        f["all four"] = f.tight & f.dry & f.rs & f.market
        print(f"\nIA breakout + filters, {wname} ({len(ev)} breakouts before filters)")
        print(f"  {'filter':12s} {'n':>6s} | {'reach +8%':>18s} | {'fakeout':>18s} | {'mean 20d return':>18s}")
        print(f"  {'':12s} {'':>6s} | {'brk':>8s} {'rand':>8s} | {'brk':>8s} {'rand':>8s} | {'brk':>8s} {'rand':>8s}")
        for name, col in [("none", None), ("tightening", "tight"), ("volume dry", "dry"),
                          ("RS > Nifty", "rs"), ("market ok", "market"), ("all four", "all four")]:
            sel = [x for x, keep in zip(ev, f[col] if col else [True] * len(ev)) if keep]
            evm = [(j, t, L, cl[t, j]) for j, t, L, _ in sel]
            twins = []
            for j, t, L, entry in evm:
                for _ in range(20):
                    r = int(rng.integers(lo_i, min(hi_i, len(sessions) - HOLD - 1)))
                    if np.isfinite(cl[r, j]):
                        twins.append((j, r, cl[r, j] * L / entry, cl[r, j]))
                        break
            a, b = measure(panel, evm), measure(panel, twins)
            if a.empty:
                print(f"  {name:12s} {0:6d}")
                continue
            print(f"  {name:12s} {len(a):6d} | {a.hit8.mean() * 100:7.1f}% {b.hit8.mean() * 100:7.1f}% | "
                  f"{a.fake.mean() * 100:7.1f}% {b.fake.mean() * 100:7.1f}% | "
                  f"{a.ret20.mean() * 100:+7.2f}% {b.ret20.mean() * 100:+7.2f}%")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
