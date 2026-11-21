"""
Falcon -- descriptive: long with a fixed stop of entry x 0.95 and target of
entry x 1.10 (1:2) on the same entries as tests/analyse_retest_to_target.py
(#3 breakout + Nifty filter, and Falcon Momentum). 20 and 40 sessions.
Conservative: a session touching both counts as the stop; the fill day's low
counts toward the stop (as in the backtests). Open at the end of the window ->
sold at that close. Costs ~0.4% round trip subtracted.

    python tests/analyse_fixed_long.py > data/fixed_long_5_10.txt
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from backtesting.pit_strategies import make_panel

COST, STOP, TGT = 0.004, 0.05, 0.10


def main():
    p = make_panel(pd.read_parquet("data/pit/prices_adjusted.parquet"), pd.read_parquet("data/pit/universe_monthly.parquet"))
    O, H, L, C = (x.to_numpy(float) for x in (p.open, p.high, p.low, p.close))
    high20 = p.high.rolling(20, min_periods=20).max().to_numpy(float)
    cols = {e: j for j, e in enumerate(p.close.columns)}
    pos = {d: k for k, d in enumerate(p.sessions)}
    n = len(p.sessions)
    trades = []
    for w, tag in (("W1", "W1"), ("W2", "W2"), ("H2018", "Y2018")):
        t = pd.read_csv(f"data/s_plus_trades_only_market_filter_{w}.csv", parse_dates=["entry_date"])
        for r in t.itertuples():
            j, f = cols.get(r.entity_id), pos.get(r.entry_date)
            if j is not None and f is not None:
                trades.append(("#3", tag, j, f, max(high20[f - 1, j], O[f, j])))
        lv = pd.read_csv(f"data/fm_variants_levels_R3_{tag}.csv", parse_dates=["entry_date"])
        for r in lv.itertuples():
            trades.append(("FM", tag, cols[r.entity_id], pos[r.entry_date], r.fill))
    rows = []
    for strat, per, j, f, entry in trades:
        for win in (20, 40):
            if f + win > n:
                continue
            hi = np.nan_to_num(H[f: f + win, j], nan=-np.inf)
            lo = np.nan_to_num(L[f: f + win, j], nan=np.inf)
            ks = np.flatnonzero(lo <= entry * (1 - STOP))
            kt = np.flatnonzero(hi >= entry * (1 + TGT))
            ks = ks[0] if len(ks) else None
            kt = kt[0] if len(kt) else None
            if ks is not None and (kt is None or ks <= kt):
                res, cls, k = -STOP, "stop", ks
            elif kt is not None:
                res, cls, k = TGT, "target", kt
            else:
                c = C[f + win - 1, j]
                res, cls, k = (c / entry - 1) if np.isfinite(c) else 0.0, "neither", win - 1
            rows.append({"strategy": strat, "period": per, "window": win, "cls": cls, "res": res - COST, "days": k + 1})
    d = pd.DataFrame(rows)
    d.to_csv("data/fixed_long_5_10.csv", index=False)
    names = {"#3": "#3 (breakout + Nifty filter)", "FM": "Falcon Momentum"}
    for strat in ("#3", "FM"):
        for pname, ps in (("all years", ["W1", "W2", "Y2018"]), ("2019-26", ["W1"]), ("2008-17", ["W2"]), ("2018", ["Y2018"])):
            print(f"\n=== Long -5% / +10% on {names[strat]} entries | {pname} ===")
            for win in (20, 40):
                x = d[(d.strategy == strat) & (d.period.isin(ps)) & (d.window == win)]
                sh = x.cls.value_counts(normalize=True) * 100
                nb = x[x.cls == "neither"]
                print(f"  {win}d, {len(x)} trades | target +10% {sh.get('target', 0):4.1f}% (median day {x[x.cls == 'target'].days.median():.0f}) | "
                      f"stop -5% {sh.get('stop', 0):4.1f}% (median day {x[x.cls == 'stop'].days.median():.0f}) | "
                      f"neither {sh.get('neither', 0):4.1f}% (avg {nb.res.mean() * 100 + COST * 100:+.1f}%) | "
                      f"avg per trade after costs {x.res.mean() * 100:+.2f}%")


if __name__ == "__main__":
    main()
