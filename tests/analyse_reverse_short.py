"""
Falcon -- descriptive: IA's reverse short on the same trades as
tests/analyse_retest_to_target.py. Short at the long entry price; stop = the
long target (entry + R x risk); target = entry x 0.95. 20 and 40 sessions.

Conservative intraday rules: a session that touches both stop and target counts
as the stop. For #3 (buy-stop fills during the breakout day) the fill day's low
does not count toward the short target (it may have come before the entry); its
high does count toward the stop. For FM (fill at the open) the whole fill day
counts. Open at the end of the window -> covered at that close. Costs ~0.4%
round trip are subtracted (borrowing / futures costs not included).

    python tests/analyse_reverse_short.py > data/reverse_short.txt
    python tests/analyse_reverse_short.py 5 > data/reverse_short_5pct.txt   # stop = entry x 1.05 (1:1)
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from backtesting.pit_strategies import make_panel
from backtesting.swing_risk import pivot_lows, swing_stop

COST = 0.004
STOP5 = len(sys.argv) > 1 and sys.argv[1] == "5"


def main():
    p = make_panel(pd.read_parquet("data/pit/prices_adjusted.parquet"), pd.read_parquet("data/pit/universe_monthly.parquet"))
    O, H, L, C = (x.to_numpy(float) for x in (p.open, p.high, p.low, p.close))
    high20 = p.high.rolling(20, min_periods=20).max().to_numpy(float)
    piv = pivot_lows(p)
    pc = p.close.shift(1)
    tr = np.maximum(p.high - p.low, np.maximum((p.high - pc).abs(), (p.low - pc).abs()))
    atr = tr.rolling(14, min_periods=14).mean()
    cols = {e: j for j, e in enumerate(p.close.columns)}
    pos = {d: k for k, d in enumerate(p.sessions)}
    n = len(p.sessions)
    trades = []
    for w, tag in (("W1", "W1"), ("W2", "W2"), ("H2018", "Y2018")):
        t = pd.read_csv(f"data/s_plus_trades_only_market_filter_{w}.csv", parse_dates=["entry_date"])
        for r in t.itertuples():
            j, f = cols.get(r.entity_id), pos.get(r.entry_date)
            if j is None or f is None:
                continue
            i = f - 1
            entry = max(high20[i, j], O[f, j])
            stop = swing_stop(p, piv, atr, i, r.entity_id, min(high20[i, j], C[i, j]))
            if stop is None or stop >= entry:
                continue
            for R in (3, 2):
                trades.append(("#3", R, tag, j, f, entry, entry + R * (entry - stop)))
        for R in (3, 2):
            lv = pd.read_csv(f"data/fm_variants_levels_R{R}_{tag}.csv", parse_dates=["entry_date"])
            for r in lv.itertuples():
                trades.append(("FM", R, tag, cols[r.entity_id], pos[r.entry_date], r.fill, r.target))
    rows = []
    for strat, R, per, j, f, entry, long_tgt in trades:
        s_stop, s_tgt = (entry * 1.05 if STOP5 else long_tgt), entry * 0.95
        for win in (20, 40):
            if f + win > n:
                continue
            hi = np.nan_to_num(H[f: f + win, j], nan=-np.inf)
            lo = np.nan_to_num(L[f: f + win, j], nan=np.inf).copy()
            if strat == "#3":
                lo[0] = np.inf
            ks = np.flatnonzero(hi >= s_stop)
            kt = np.flatnonzero(lo <= s_tgt)
            ks = ks[0] if len(ks) else None
            kt = kt[0] if len(kt) else None
            if ks is not None and (kt is None or ks <= kt):
                res, cls, k = -(s_stop / entry - 1), "stop", ks
            elif kt is not None:
                res, cls, k = 0.05, "target", kt
            else:
                c = C[f + win - 1, j]
                res, cls, k = (1 - c / entry) if np.isfinite(c) else 0.0, "neither", win - 1
            rows.append({"strategy": strat, "R": R, "period": per, "window": win, "cls": cls,
                         "res": res - COST, "stop_pct": (s_stop / entry - 1) * 100, "days": k + 1})
    d = pd.DataFrame(rows)
    d.to_csv("data/reverse_short_5pct.csv" if STOP5 else "data/reverse_short.csv", index=False)
    names = {"#3": "#3 (breakout + Nifty filter)", "FM": "Falcon Momentum"}
    for strat in ("#3", "FM"):
        for pname, ps in (("all years", ["W1", "W2", "Y2018"]), ("2019-26", ["W1"]), ("2008-17", ["W2"]), ("2018", ["Y2018"])):
            print(f"\n=== Short on {names[strat]} trades | {pname} ===")
            for R in ((3,) if STOP5 else (3, 2)):
                for win in (20, 40):
                    x = d[(d.strategy == strat) & (d.R == R) & (d.period.isin(ps)) & (d.window == win)]
                    sh = x.cls.value_counts(normalize=True) * 100
                    nb = x[x.cls == "neither"]
                    print(f"  stop = {'+5%' if STOP5 else f'1:{R} long target (median +{x.stop_pct.median():.0f}%)'}, {win}d, {len(x)} trades | "
                          f"target -5% {sh.get('target', 0):4.1f}% (median day {x[x.cls == 'target'].days.median():.0f}) | "
                          f"stopped {sh.get('stop', 0):4.1f}% | neither {sh.get('neither', 0):4.1f}% (avg {nb.res.mean() * 100 + COST * 100:+.1f}%) | "
                          f"avg per trade after costs {x.res.mean() * 100:+.2f}%")


if __name__ == "__main__":
    main()
