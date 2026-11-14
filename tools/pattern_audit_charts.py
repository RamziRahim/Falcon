import sys; sys.path.insert(0, ".")
import json, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from backtesting.pit_strategies import make_panel
OUT = sys.argv[1]
SPANS = ["2008-01-01_2017-12-31", "2018-01-01_2018-12-31", "2019-01-01_2026-10-30"]
rng = np.random.default_rng(20261113)
panel = make_panel(pd.read_parquet("data/pit/prices_adjusted.parquet"), pd.read_parquet("data/pit/universe_monthly.parquet"))
O,H,L,C,V = (x for x in (panel.open, panel.high, panel.low, panel.close, panel.volume))
s = panel.sessions; pos = {d:k for k,d in enumerate(s)}; cols = {e:j for j,e in enumerate(C.columns)}
Cn = C.to_numpy(float); S200 = C.rolling(200, min_periods=200).mean().to_numpy(float)
S50 = C.rolling(50, min_periods=50).mean().to_numpy(float)
setups = pd.concat([pd.read_parquet(f"data/pit/falcon_setups_v2_{sp}.parquet") for sp in SPANS])
setups = setups[setups.entity_id.isin(cols) & setups.scan_date.map(lambda d: pd.Timestamp(d) in pos)]
setups["t"] = setups.scan_date.map(lambda d: pos[pd.Timestamp(d)])
setups = setups[setups.t >= 260]
picks, used = [], set()
for pat in ["is_vcp_breakout", "is_flat_base_breakout", "is_ascending_triangle_breakout", "is_bull_flag_breakout"]:
    g = setups[setups.pattern == pat].sample(frac=1, random_state=int(rng.integers(1e9)))
    n = 0
    for r in g.itertuples():
        if r.entity_id in used: continue
        used.add(r.entity_id); n += 1
        picks.append({"kind": "detected", "pattern": pat.replace("is_","").replace("_breakout",""), "e": r.entity_id, "t": int(r.t),
                      "pivot": float(r.pivot), "stop": float(r.stop)})
        if n == 10: break
det_keys = {(e, t) for e, t in zip(setups.entity_id, setups.t)}
det_by_e = setups.groupby("entity_id").t.apply(np.array).to_dict()
n = 0
while n < 10:
    t = int(rng.integers(260, len(s) - 1)); mem = [e for e in panel.universe_on(s[t]) if e in cols and e not in used]
    if not mem: continue
    e = mem[int(rng.integers(len(mem)))]; j = cols[e]
    if not (np.isfinite(S200[t, j]) and Cn[t, j] > S200[t, j] and S50[t, j] > S200[t, j] and S200[t, j] > S200[t-20, j]): continue
    if e in det_by_e and np.any(np.abs(det_by_e[e] - t) <= 10): continue
    pivot = float(H.iloc[t-19:t+1, j].max()); stop = float(L.iloc[t-9:t+1, j].min())
    used.add(e); n += 1
    picks.append({"kind": "not_detected", "pattern": "", "e": e, "t": t, "pivot": pivot, "stop": stop})
order = rng.permutation(len(picks))
key = []
for k, idx in enumerate(order, 1):
    p = picks[idx]; j = cols[p["e"]]; t = p["t"]; a = t - 179
    o,h,l,c,v = (x.iloc[a:t+1, j].to_numpy(float) for x in (O,H,L,C,V))
    x = np.arange(len(c))
    fig, (ax, axv) = plt.subplots(2, 1, figsize=(10, 5.6), dpi=110, gridspec_kw={"height_ratios": [4, 1]}, sharex=True)
    up = c >= o
    ax.vlines(x, l, h, color=np.where(up, "#1a7f5a", "#c0392b"), lw=0.8)
    ax.bar(x, np.where(np.abs(c-o) < 1e-9, (h-l)*0.01+1e-9, c-o), bottom=o, width=0.7, color=np.where(up, "#1a7f5a", "#c0392b"))
    ax.plot(x, S50[a:t+1, j], color="#2e6fd8", lw=1.1, label="50-day avg")
    ax.plot(x, S200[a:t+1, j], color="#8e44ad", lw=1.1, label="200-day avg")
    ax.axhline(p["pivot"], color="#111", ls="--", lw=1.1, label="breakout level")
    ax.axhline(p["stop"], color="#e67e22", ls=":", lw=1.3, label="stop")
    ax.legend(loc="upper left", fontsize=8, frameon=False); ax.grid(alpha=0.2)
    lo, hi = np.nanmin(l), np.nanmax(h); ax.set_ylim(min(lo, p["stop"])*0.97, max(hi, p["pivot"])*1.03)
    axv.bar(x, v, color=np.where(up, "#1a7f5a", "#c0392b"), width=0.7); axv.set_yticks([]); axv.grid(alpha=0.2)
    vm = pd.Series(v).rolling(50, min_periods=1).mean(); axv.plot(x, vm, color="#555", lw=0.9)
    axv.set_xticks([0, 60, 120, 179]); axv.set_xticklabels(["−180 sessions", "−120", "−60", "scan day"], fontsize=8)
    fig.tight_layout(); fig.savefig(f"{OUT}/charts/c{k:02d}.png"); plt.close(fig)
    key.append({"chart": f"c{k:02d}", **{kk: (str(vv) if kk == "e" else vv) for kk, vv in p.items()}, "date": str(s[t].date())})
json.dump(key, open(f"{OUT}/answer_key.json", "w"), indent=1)
print(len(key), pd.Series([k["kind"] for k in key]).value_counts().to_dict())
