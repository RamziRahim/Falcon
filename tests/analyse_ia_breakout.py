"""
Falcon -- descriptive screen of IA's momentum-breakout definition (2026-11-04):

  "the stock has broken the previous swing high (in a downtrend or an
   uptrend), the price is consolidating in a range, and there is a range
   breakout with higher volume than average volume"

Rules, fixed before running:
  1. Swing high: Falcon fractal (no bar within 3 sessions either side has a
     higher High), usable from 3 sessions after the pivot (confirmed).
  2. Break of structure (BOS): the first close above the most recent
     confirmed swing high.
  3. Consolidation: the sessions after the BOS day, before the breakout day:
     at least 5 and at most 30 of them, and their High-to-Low range
     (max High / min Low - 1) is at most 10%.
  4. Range breakout on day t: close_t > level, where level = the highest High
     from the BOS day to t-1 (the top of the range), and volume_t >
     1.5 x the 50-session average volume (also reported with > 1.0 x).
  5. Stock in that month's universe; one breakout per stock per 20 sessions.

Measured over the 20 sessions after t (entry = close_t):
  reached +8%   : some High >= close_t x 1.08
  fakeout       : some Low <= level x 0.97 AND close_(t+20) < level
  20-day return : close_(t+20) / close_t - 1
Compared with random twins: a random session of the same stock in the same
window, entry = its close, level = its close x (level / close_t) of the
paired breakout (same distance to the "level").

    python tests/analyse_ia_breakout.py > data/ia_breakout_screen.txt
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from backtesting.pit_strategies import make_panel

WINDOWS = {"2019-26": ("2019-01-01", "2026-10-30"), "2008-17": ("2008-01-01", "2017-12-31")}
W, MIN_CONS, MAX_CONS, MAX_WIDTH, HOLD, GAP = 3, 5, 30, 0.10, 20, 20
VOL_MULTS = (1.5, 1.0)


def last_confirmed_swing_high(high: np.ndarray) -> np.ndarray:
    """For each session, the value of the most recent swing high confirmed by
    that session (pivot at least W sessions earlier)."""
    n, m = high.shape
    beaten = np.zeros_like(high, dtype=bool)
    for r in range(1, W + 1):
        left = np.full_like(high, np.nan)
        right = np.full_like(high, np.nan)
        left[r:] = high[:-r]
        right[:-r] = high[r:]
        with np.errstate(invalid="ignore"):
            beaten |= (left > high) | (right > high)
    piv = np.isfinite(high) & ~beaten
    piv[:W] = False
    piv[n - W:] = False
    vals = np.where(piv, high, np.nan)
    confirmed = np.full_like(high, np.nan)
    confirmed[W:] = vals[:-W]                                    # usable W sessions later
    return pd.DataFrame(confirmed).ffill().to_numpy()


def find_breakouts(panel, vol_mult, with_bos=False):
    hi, lo = panel.high.to_numpy(float), panel.low.to_numpy(float)
    cl, vol = panel.close.to_numpy(float), panel.volume.to_numpy(float)
    vavg = panel.volume.rolling(50, min_periods=50).mean().shift(1).to_numpy(float)
    sh = last_confirmed_swing_high(hi)
    with np.errstate(invalid="ignore"):
        above = cl > sh
    prev_above = np.zeros_like(above)
    prev_above[1:] = above[:-1]
    bos = above & ~prev_above                                     # first close above the swing high
    n, m = cl.shape
    out = []
    for j in range(m):
        bos_days = np.flatnonzero(bos[:, j])
        if not len(bos_days):
            continue
        with np.errstate(invalid="ignore"):
            cand = np.flatnonzero(vol[:, j] > vol_mult * vavg[:, j])
        last_t = -10**9
        for t in cand:
            k = np.searchsorted(bos_days, t, side="left") - 1     # latest BOS strictly before t
            if k < 0:
                continue
            b = bos_days[k]
            cons = t - b - 1
            if cons < MIN_CONS or cons > MAX_CONS or t + HOLD >= n:
                continue
            seg_hi, seg_lo = hi[b + 1: t, j], lo[b + 1: t, j]
            if not (np.isfinite(seg_hi).all() and np.isfinite(seg_lo).all()):
                continue
            if seg_hi.max() / seg_lo.min() - 1 > MAX_WIDTH:
                continue
            level = np.nanmax(hi[b: t, j])
            if not cl[t, j] > level or t - last_t < GAP:
                continue
            last_t = t
            out.append((j, t, level, b) if with_bos else (j, t, level))
    return out


def measure(panel, ev):
    hi, lo, cl = panel.high.to_numpy(float), panel.low.to_numpy(float), panel.close.to_numpy(float)
    rows = []
    for j, t, L, entry in ev:
        h, l, c20 = hi[t + 1: t + 1 + HOLD, j], lo[t + 1: t + 1 + HOLD, j], cl[t + HOLD, j]
        if not np.isfinite(l).any() or not np.isfinite(c20):
            continue
        rows.append({"hit8": np.nanmax(h) >= entry * 1.08,
                     "fake": (np.nanmin(l) <= L * 0.97) and c20 < L,
                     "ret20": c20 / entry - 1, "above_level": c20 >= L})
    return pd.DataFrame(rows)


def main():
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    panel = make_panel(prices, universe)
    del prices
    sessions = panel.sessions
    cols = list(panel.close.columns)
    cl = panel.close.to_numpy(float)
    rng = np.random.default_rng(20261104)
    for vm in VOL_MULTS:
        allev = find_breakouts(panel, vm)
        for wname, (s, e) in WINDOWS.items():
            s, e = pd.Timestamp(s), pd.Timestamp(e)
            lo_i, hi_i = int(sessions.searchsorted(s)), int(sessions.searchsorted(e, side="right"))
            ev = [(j, t, L, cl[t, j]) for j, t, L in allev
                  if lo_i <= t < hi_i and cols[j] in panel.universe_on(sessions[t])]
            twins = []
            for j, t, L, entry in ev:
                for _ in range(20):
                    r = int(rng.integers(lo_i, min(hi_i, len(sessions) - HOLD - 1)))
                    if np.isfinite(cl[r, j]):
                        twins.append((j, r, cl[r, j] * L / entry, cl[r, j]))
                        break
            a, b = measure(panel, ev), measure(panel, twins)
            dist = np.median([entry / L - 1 for _, _, L, entry in ev]) * 100 if ev else np.nan
            print(f"\nIA breakout, volume > {vm}x 50-day average, {wname}: {len(a)} breakouts "
                  f"(median close {dist:.1f}% above the range top)")
            print(f"  {'':34s} {'breakout':>9s} {'random':>8s}")
            for name, col in [("reached +8% within 20 sessions", "hit8"), ("fakeout (>3% below level, stays below)", "fake"),
                              ("above the level after 20 sessions", "above_level")]:
                print(f"  {name:34s} {a[col].mean() * 100:8.1f}% {b[col].mean() * 100:7.1f}%")
            print(f"  {'median 20-session return':34s} {a.ret20.median() * 100:+8.1f}% {b.ret20.median() * 100:+7.1f}%")
            print(f"  {'mean 20-session return':34s} {a.ret20.mean() * 100:+8.1f}% {b.ret20.mean() * 100:+7.1f}%")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
