import sys; sys.path.insert(0, ".")
"""Blind audit 2: charts of pattern engine v3 picks (REAL_PATTERN, 8 per pattern) and 10 Stage-2
stocks it found no pattern in. Seed 20261114. Writes <out>/charts/cNN.png, <out>/answer_key.json and
<out>/scan_counts.json."""
import json, time, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from backtesting.pit_strategies import make_panel
from technical_analysis.pattern_system_v3.engine import classify_nse_stock
OUT = sys.argv[1]
N_DRAWS = int(sys.argv[2]) if len(sys.argv) > 2 else 60000
rng = np.random.default_rng(20261114)
panel = make_panel(pd.read_parquet("data/pit/prices_adjusted.parquet"), pd.read_parquet("data/pit/universe_monthly.parquet"))
O,H,L,C,V = (x for x in (panel.open, panel.high, panel.low, panel.close, panel.volume))
s = panel.sessions; cols = {e:j for j,e in enumerate(C.columns)}
S200 = C.rolling(200, min_periods=200).mean().to_numpy(float)
S50 = C.rolling(50, min_periods=50).mean().to_numpy(float)
arr = {k: x.to_numpy(float) for k, x in (("Open", O), ("High", H), ("Low", L), ("Close", C), ("Volume", V))}
seen1 = {k["e"] for k in json.load(open("data/pattern_audit/answer_key.json"))}
PATS = ["VCP", "ASCENDING_TRIANGLE", "BULL_FLAG", "CUP_WITH_HANDLE", "FLAT_BASE"]
found = {p: [] for p in PATS}; controls = []; counts = {}
mem_cache = {}
t0 = time.time()
for _ in range(N_DRAWS):
    t = int(rng.integers(300, len(s)))
    if t not in mem_cache:
        mem_cache[t] = [e for e in panel.universe_on(s[t]) if e in cols]
    mem = mem_cache[t]
    if not mem: continue
    e = mem[int(rng.integers(len(mem)))]; j = cols[e]
    a = t - 399
    df = pd.DataFrame({k: v[a:t+1, j] for k, v in arr.items()}).dropna().reset_index(drop=True)
    if len(df) < 300: continue
    sig = classify_nse_stock(df)
    key = f"{sig.verdict}|{sig.pattern_type}"; counts[key] = counts.get(key, 0) + 1
    if str(e) in seen1: continue
    if sig.verdict == "REAL_PATTERN":
        found[sig.pattern_type].append({"kind": "detected", "pattern": sig.pattern_type, "e": e, "t": t,
                                         "pivot": sig.breakout_level, "stop": sig.stop_loss})
    elif sig.pattern_type == "NONE" and sig.notes and sig.notes[0].startswith("Passed Stage 2"):
        controls.append({"kind": "not_detected", "pattern": "", "e": e, "t": t,
                         "pivot": float(np.nanmax(arr["High"][t-19:t+1, j])), "stop": float(np.nanmin(arr["Low"][t-9:t+1, j]))})
print("draws", N_DRAWS, "secs", round(time.time() - t0), {p: len(v) for p, v in found.items()}, "controls", len(controls), flush=True)
json.dump({"draws": N_DRAWS, "counts": counts}, open(f"{OUT}/scan_counts.json", "w"), indent=1)
picks, used = [], set()
for p in PATS:
    pool = found[p]; n = 0
    for k in rng.permutation(len(pool)):
        c = pool[k]
        if c["e"] in used: continue
        used.add(c["e"]); picks.append(c); n += 1
        if n == 8: break
need = 40 - len(picks)
if need > 0:                                   # a rare pattern had fewer than 8: fill from flat base / flag pools
    extra = [c for p in ("FLAT_BASE", "BULL_FLAG", "CUP_WITH_HANDLE") for c in found[p] if c["e"] not in used]
    for k in rng.permutation(len(extra))[:need]:
        c = extra[k]
        if c["e"] in used: continue
        used.add(c["e"]); picks.append(c)
n = 0
for k in rng.permutation(len(controls)):
    c = controls[k]
    if c["e"] in used: continue
    used.add(c["e"]); picks.append(c); n += 1
    if n == 10: break
print("picks", pd.Series([p["pattern"] or "control" for p in picks]).value_counts().to_dict(), flush=True)
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
