"""
Falcon -- descriptive: of the trades that came back to the entry price, how many
then reached the target without hitting the stop first, and how fast.

  #3 : data/s_plus_trades_only_market_filter_{W1,W2,H2018}.csv (breakout entry +
       Nifty filter); entry = max(20-day high, open), swing-low stop rebuilt as in
       tests/analyse_trade_paths.py; 3R and 2R targets on the same trades
  FM : data/fm_variants_levels_{R3,R2}_{W1,W2,Y2018}.csv (logged fill/stop/target)

Windows of 20 and 40 sessions from the fill; retest = a low <= entry from the
session after the fill; stop wins same-day ties.

    python tests/analyse_retest_to_target.py > data/retest_to_target.txt
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from backtesting.pit_strategies import make_panel
from backtesting.swing_risk import pivot_lows, swing_stop


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
    trades = []                      # (strategy, R, period, j, f, entry, stop)
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
                trades.append(("#3 (breakout + Nifty filter)", R, tag, j, f, entry, stop))
        for R in (3, 2):
            lv = pd.read_csv(f"data/fm_variants_levels_R{R}_{tag}.csv", parse_dates=["entry_date"])
            for r in lv.itertuples():
                trades.append(("Falcon Momentum", R, tag, cols[r.entity_id], pos[r.entry_date], r.fill, r.stop))
    rows = []
    for strat, R, per, j, f, entry, stop in trades:
        tgt = entry + R * (entry - stop)
        for win in (20, 40):
            if f + win > n:
                continue
            lo = np.nan_to_num(L[f: f + win, j], nan=np.inf)
            hi = np.nan_to_num(H[f: f + win, j], nan=-np.inf)
            kr = np.flatnonzero(lo[1:] <= entry)
            kr = kr[0] + 1 if len(kr) else None
            ks = np.flatnonzero(lo <= stop)
            ks = ks[0] if len(ks) else None
            kt = np.flatnonzero(hi >= tgt)
            kt = kt[0] if len(kt) else None
            hit = kt is not None and (ks is None or kt < ks)
            rows.append({"strategy": strat, "R": R, "period": per, "window": win,
                         "retest": kr is not None and (kt is None or kr <= kt),
                         "retest_then_target": hit and kr is not None and kr <= kt,
                         "direct_target": hit and (kr is None or kr > kt),
                         "days": kt + 1 if hit else np.nan, "days_retest": kr if kr is not None else np.nan})
    d = pd.DataFrame(rows)
    d.to_csv("data/retest_to_target.csv", index=False)
    for strat in d.strategy.unique():
        for pname, ps in (("all years", ["W1", "W2", "Y2018"]), ("2019-26", ["W1"]), ("2008-17", ["W2"]), ("2018", ["Y2018"])):
            print(f"\n=== {strat} | {pname} ===")
            for R in (3, 2):
                for win in (20, 40):
                    x = d[(d.strategy == strat) & (d.R == R) & (d.period.isin(ps)) & (d.window == win)]
                    nt, rt = len(x), x.retest.sum()
                    rtt = x[x.retest_then_target]
                    print(f"  1:{R} {win:2d}d  trades {nt:5d} | came back to entry {rt:5d} ({rt / nt * 100:4.1f}%) | "
                          f"then target, no stop {len(rtt):4d} ({len(rtt) / nt * 100:4.1f}% of all, {len(rtt) / max(rt, 1) * 100:4.1f}% of retests) | "
                          f"days to target median {rtt.days.median():.0f} (25-75%: {rtt.days.quantile(.25):.0f}-{rtt.days.quantile(.75):.0f}), "
                          f"retest on day {rtt.days_retest.median():.0f} | direct {x.direct_target.mean() * 100:4.1f}%")


if __name__ == "__main__":
    main()
