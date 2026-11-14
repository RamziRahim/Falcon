import sys; sys.path.insert(0, ".")
import json, glob, numpy as np, pandas as pd
from backtesting.pit_strategies import make_panel
D = sys.argv[1]
key = json.load(open(f"{D}/answer_key.json"))
ans = {f.split('/')[-1][:-5]: json.load(open(f)) for f in glob.glob(f"{D}/answers/audit/*.json")}
p = make_panel(pd.read_parquet("data/pit/prices_adjusted.parquet"), pd.read_parquet("data/pit/universe_monthly.parquet"))
H, L, C = (x.to_numpy(float) for x in (p.high, p.low, p.close)); cols = {str(e): j for j, e in enumerate(p.close.columns)}
out = []
for k in key:
    j, t, pv, sp = cols[k["e"]], k["t"], k["pivot"], k["stop"]
    trig = next((i for i in range(t+1, min(t+6, len(C))) if H[i, j] > pv), None)
    res, r40 = "no trigger", np.nan
    if trig is not None:
        tgt = pv + 3*(pv - sp); res = "time"
        for i in range(trig, min(trig+40, len(C))):
            if L[i, j] <= sp: res = "stop"; break
            if H[i, j] >= tgt: res = "target"; break
        e = min(trig+39, len(C)-1); r40 = C[e, j]/pv - 1
    out.append({"chart": k["chart"], "kind": k["kind"], "pattern": k["pattern"], "verdict": ans.get(k["chart"], {}).get("verdict"),
                "seen": ans.get(k["chart"], {}).get("type"), "result": res, "ret40": r40, "closed_above": bool(trig is not None and C[trig, j] > pv)})
df = pd.DataFrame(out); df.to_csv(f"{D}/audit_joined.csv", index=False)
print(df.groupby("verdict").agg(n=("chart","size"), triggered=("result", lambda s: (s!="no trigger").sum()),
      stop=("result", lambda s:(s=="stop").sum()), target=("result", lambda s:(s=="target").sum()),
      ret40=("ret40", lambda s: round(100*s.mean(),1)), med40=("ret40", lambda s: round(100*s.median(),1))))
print(df[df.kind=="detected"].groupby("verdict").agg(n=("chart","size"), stop=("result", lambda s:(s=="stop").sum()),
      target=("result", lambda s:(s=="target").sum()), ret40=("ret40", lambda s: round(100*s.mean(),1))))
