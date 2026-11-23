"""
Descriptive study (not a strategy test): which facts known at entry go with better FM_C3
trades? Half A only, W1 and W2. Output: data/conviction_study.txt

    PYTHONHASHSEED=0 python tools/conviction_study.py
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES
from backtesting.falcon_momentum_entries import run_fm_entries
from tests.run_ethical_filter_history import load

WINDOWS = {"W2": ("2008-01-01", "2017-12-31"), "W1": ("2019-01-01", "2026-10-30")}


def main():
    ix = pd.read_parquet("data/pit_sources/indices_2000_2026.parquet")
    ix["Date"] = pd.to_datetime(ix["Date"])
    nifty = ix[ix["Index"] == "NIFTY 50"].set_index("Date")["Close"].sort_index()
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    panel = load("A", None)
    s = panel.sessions
    C, H, L, V = (panel.close.to_numpy(float), panel.high.to_numpy(float), panel.low.to_numpy(float),
                  panel.volume.to_numpy(float))
    cols = {e: j for j, e in enumerate(panel.close.columns)}
    pos = {d: i for i, d in enumerate(s)}
    hi20 = panel.high.rolling(20, min_periods=20).max().shift(1).to_numpy(float)
    hi252 = panel.high.rolling(252, min_periods=200).max().to_numpy(float)
    v50 = panel.volume.rolling(50, min_periods=50).mean().shift(1).to_numpy(float)
    pc = panel.close.shift(1).to_numpy(float)
    tr = np.fmax(np.fmax(H - L, np.abs(H - pc)), np.abs(L - pc))
    atr = pd.DataFrame(tr, index=s).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean().to_numpy(float)
    r126 = (panel.close / panel.close.shift(126) - 1)
    rank126 = r126.rank(axis=1, pct=True).to_numpy(float)
    nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
    ntrend = (nf / nf.rolling(50, min_periods=50).mean() - 1).to_numpy(float)
    rows = []
    for w, (a, b) in WINDOWS.items():
        eq, trd = run_fm_entries(panel, pd.Timestamp(a), pd.Timestamp(b), nifty, indices, "closebuy", r_mult=3.0)[:2]
        for t in trd.itertuples():
            i, j = pos.get(pd.Timestamp(t.entry_date)), cols.get(t.entity_id)
            if i is None or j is None:
                continue
            c = C[i, j]
            rows.append({"window": w, "net": t.pnl / t.cost_basis * 100, "win": t.pnl > 0, "exit": t.exit_reason,
                         "close_above_20d_high": (c / hi20[i, j] - 1) * 100,
                         "volume_x_50d": V[i, j] / v50[i, j],
                         "below_52w_high": (1 - c / hi252[i, j]) * 100,
                         "momentum_pct_126d": rank126[i, j] * 100,
                         "atr3_pct_of_price": 3 * atr[i, j] / c * 100,
                         "close_in_day_range": (c - L[i, j]) / (H[i, j] - L[i, j]) if H[i, j] > L[i, j] else np.nan,
                         "nifty_vs_50dma": ntrend[i] * 100})
    df = pd.DataFrame(rows)
    df.to_csv("data/conviction_study_trades.csv", index=False)
    out = open("data/conviction_study.txt", "w", encoding="utf-8")
    out.write("FM_C3 trades, half A. net = return per trade after costs (%). Terciles cut on both windows pooled.\n")
    out.write(f"Trades: {df.groupby('window').size().to_dict()}\n")
    for w in WINDOWS:
        d = df[df.window == w]
        out.write(f"All trades {w}: net {d.net.mean():+.2f}%  win {d.win.mean() * 100:.0f}%  "
                  f"exits {d['exit'].value_counts().to_dict()}\n")
    feats = [c for c in df.columns if c not in ("window", "net", "win", "exit")]
    for f in feats:
        x = df[f].replace([np.inf, -np.inf], np.nan)
        q = x.quantile([1 / 3, 2 / 3]).to_numpy()
        lab = pd.cut(x, [-np.inf, q[0], q[1], np.inf], labels=["low", "mid", "high"])
        out.write(f"\n{f}  (cuts {q[0]:.2f} / {q[1]:.2f})\n")
        for w in WINDOWS:
            m = df.window == w
            g = df[m].groupby(lab[m], observed=True)
            out.write(f"  {w}: " + " | ".join(f"{k} net {v.net.mean():+.2f}% win {v.win.mean() * 100:.0f}% n {len(v)}"
                                             for k, v in g) + "\n")
    out.close()
    print(open("data/conviction_study.txt").read())


if __name__ == "__main__":
    main()
