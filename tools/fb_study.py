"""Event study of Falcon pattern breakouts on half A: what separates real from false breakouts."""
import sys; sys.path.insert(0, ".")
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from tests.half_a import load_half_a
from tests.run_mean_reversion import _nifty
panel = load_half_a("A"); nifty, _ = _nifty()
su = pd.read_parquet("data/falcon_salvage_setups_halfA.parquet")
s = panel.sessions; c = panel.close
O, H, L, C, V = (x.to_numpy(float) for x in (panel.open, panel.high, panel.low, c, panel.volume))
cols = {e: j for j, e in enumerate(c.columns)}
V50 = panel.volume.rolling(50, min_periods=50).mean().shift(1).to_numpy(float)
V10 = panel.volume.rolling(10, min_periods=10).mean().to_numpy(float)
pc = c.shift(1); tr = np.maximum(panel.high - panel.low, np.maximum((panel.high - pc).abs(), (panel.low - pc).abs()))
ATR = tr.rolling(14, min_periods=14).mean().to_numpy(float)
S50 = c.rolling(50, min_periods=50).mean().to_numpy(float); S200 = c.rolling(200, min_periods=200).mean().to_numpy(float)
HI52 = panel.high.rolling(252, min_periods=200).max().to_numpy(float)
nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s); n_ok = (nf > nf.rolling(50).mean()).to_numpy()
ew = (1 + c.ffill(limit=5).pct_change(fill_method=None).mean(axis=1).fillna(0)).cumprod(); ew_ok = (ew > ew.rolling(50).mean()).to_numpy()
T = len(s); rows = []; seen = set()
for r in su.itertuples():
    t, j = r.t, cols[r.entity_id]
    for f in range(t + 1, min(t + 6, T - 41)):
        o, h, l, x = O[f, j], H[f, j], L[f, j], C[f, j]
        if not np.isfinite(o): continue
        if l <= r.stop and h < r.pivot: break
        if h >= r.pivot:
            if o > r.pivot * 1.03 or (r.entity_id, f) in seen: break
            seen.add((r.entity_id, f))
            fill = max(r.pivot, o)
            lo = L[f: f + 40, j]; hi = H[f: f + 40, j]
            ks = np.flatnonzero(lo <= r.stop); kt = np.flatnonzero(hi >= r.target)
            ks = ks[0] if len(ks) else 99; kt = kt[0] if len(kt) else 99
            out = "stop" if ks <= kt and ks < 99 else ("target" if kt < 99 else "neither")
            exitpx = r.stop if out == "stop" else r.target if out == "target" else C[f + 39, j]
            rng = h - l
            rows.append(dict(W="W1" if s[f] >= pd.Timestamp("2019-01-01") else "W2", pattern=r.pname, out=out,
                ret=exitpx / fill - 1 - 0.004, r20=C[f + 20, j] / fill - 1, risk=(fill - r.stop) / fill,
                wick=x < r.pivot, red=x < o, closepos=(x - l) / rng if rng > 0 else np.nan,
                volx=V[f, j] / V50[f, j], gap=o / C[f - 1, j] - 1, open_above=o >= r.pivot,
                ext=x / r.pivot - 1, mom=r.mom_rank, n_up=r.N_UP, far=r.FAR, pivx3=r.PIV_X3, wide=r.WIDE,
                tight=np.nanmax(H[t - 19: t + 1, j]) / np.nanmin(L[t - 19: t + 1, j]) - 1,
                dry=V10[t, j] / V50[t, j], atrp=ATR[t, j] / C[t, j], nifty_ok=bool(n_ok[t]), ew_ok=bool(ew_ok[t]),
                hi52=C[t, j] / HI52[t, j], above200=C[t, j] > S200[t, j] and S50[t, j] > S200[t, j] and S200[t, j] > S200[t - 20, j],
                rr=r.rr, prior_up3=C[t, j] / C[t - 3, j] - 1))
            break
d = pd.DataFrame(rows); d.to_parquet("data/fb_events_halfA.parquet")
print("events", len(d), d.W.value_counts().to_dict())
def line(name, m):
    out = f"{name:44s}"
    for w in ("W1", "W2"):
        x = d[m & (d.W == w)]
        out += f" | {w} n {len(x):5d} stop {100*(x.out=='stop').mean():4.0f}% tgt {100*(x.out=='target').mean():4.0f}% net {100*x.ret.mean():+5.2f}% wick {100*x.wick.mean():3.0f}%"
    print(out)
A = pd.Series(True, index=d.index)
print("\n== overall and by pattern"); line("ALL", A)
for p in d.pattern.unique(): line(p, d.pattern == p)
print("\n== known BEFORE the trigger (at detection)")
line("momentum rank >= 0.8", d.mom >= .8); line("momentum rank 0.5-0.8", (d.mom >= .5) & (d.mom < .8)); line("momentum rank < 0.5", d.mom < .5)
line("above rising 200DMA, 50>200", d.above200); line("NOT above rising 200DMA", ~d.above200)
line("within 10% of 52w high", d.hi52 >= .9); line("10-25% below 52w high", (d.hi52 < .9) & (d.hi52 >= .75)); line(">25% below 52w high", d.hi52 < .75)
line("20d range <= 10%", d.tight <= .10); line("20d range 10-15%", (d.tight > .10) & (d.tight <= .15)); line("20d range > 15%", d.tight > .15)
line("volume dry-up (10d/50d < 0.8)", d.dry < .8); line("volume 0.8-1.2", (d.dry >= .8) & (d.dry <= 1.2)); line("volume rising (> 1.2)", d.dry > 1.2)
line("Nifty > 50DMA", d.nifty_ok); line("Nifty < 50DMA", ~d.nifty_ok); line("EW list > 50DMA", d.ew_ok); line("EW list < 50DMA", ~d.ew_ok)
line("stop distance <= 5%", d.risk <= .05); line("stop distance 5-8%", (d.risk > .05) & (d.risk <= .08)); line("stop distance > 8%", d.risk > .08)
line("pivot already exceeded >3% (PIV_X3)", d.pivx3); line("pivot not exceeded", ~d.pivx3)
line("ran up > 4% in 3 days before", d.prior_up3 > .04); line("flat/down 3 days before", d.prior_up3 <= .01)
print("\n== known AT THE OPEN of the trigger day")
line("opened at/above pivot (gap)", d.open_above); line("opened below pivot", ~d.open_above)
line("gap up > 1% at open", d.gap > .01); line("gap -0.5..+1%", (d.gap <= .01) & (d.gap >= -.005)); line("gap down < -0.5%", d.gap < -.005)
print("\n== known AT THE CLOSE of the trigger day")
line("closed below pivot (wick)", d.wick); line("closed above pivot", ~d.wick)
line("closed above, close in top 25% of range", ~d.wick & (d.closepos >= .75)); line("closed above, vol >= 1.5x", ~d.wick & (d.volx >= 1.5)); line("closed above, vol < 1.5x", ~d.wick & (d.volx < 1.5))
line("closed 0-2% above pivot", ~d.wick & (d.ext <= .02)); line("closed 2-5% above pivot", (d.ext > .02) & (d.ext <= .05)); line("closed > 5% above pivot", d.ext > .05)
print("\n== combinations (pre-trigger only)")
q = (d.mom >= .8) & d.above200 & (d.hi52 >= .85)
line("QUALITY: mom>=.8, rising 200, <=15% off high", q); line("QUALITY + Nifty>50DMA", q & d.nifty_ok); line("QUALITY + tight<=15%", q & (d.tight <= .15))
line("QUALITY + opened below pivot", q & ~d.open_above); line("NOT quality", ~q)
print("\n== QUALITY, by close"); line("QUALITY & closed above", q & ~d.wick); line("QUALITY & wick", q & d.wick)
x = d[q & ~d.wick]; print("  QUALITY & closed above: mean 20d return from the CLOSE:", {w: round(100 * ((1 + x[x.W == w].r20) / (1 + x[x.W == w].ext) - 1).mean(), 2) for w in ("W1", "W2")})
x = d[q & d.wick]; print("  QUALITY & wick: mean 20d return from the fill:", {w: round(100 * x[x.W == w].r20.mean(), 2) for w in ("W1", "W2")})
