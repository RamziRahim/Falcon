"""
Falcon -- descriptive: the price path after every trade actually taken by the
#3 sector-filter versions (data/s_sector_trades_*, data/s_sector_nifty_trades_*),
followed for 20 and for 40 sessions from the fill day, ignoring how the trade
was actually exited.

Levels are rebuilt from the signal: entry = max(20-day-high trigger, open of
the fill day); stop = swing-low stop at the signal day (F5: entry x 0.95);
target = entry + R x (entry - stop) (F5: entry x 1.05). Half / break-even
versions use their R target.

Classes (same-day stop + target counts as stop first; "came back to entry" is
measured from the session after the fill):
  direct        target hit before any return to the entry price, stop not hit
  retest        returned to the entry price, then hit the target, stop not hit
  stop, down    stop hit, target never reached afterwards in the window
  stop, then up stop hit, then the target was reached later in the window
  neither       neither stop nor target in the window

    python tests/analyse_trade_paths.py > data/trade_paths.txt
"""
import sys
sys.path.insert(0, ".")

import glob
import re

import numpy as np
import pandas as pd

from backtesting.pit_strategies import make_panel
from backtesting.swing_risk import pivot_lows, swing_stop

R = {"R3": 3, "R2": 2, "R3H": 3, "R2H": 2, "R3BE": 3, "R2BE": 2, "F5": None}
LABEL = {"R3": "1:3", "R2": "1:2", "F5": "±5% (1:1)", "R3H": "1:3 + half at 5%", "R2H": "1:2 + half at 5%",
         "R3BE": "1:3 + stop to cost at 5%", "R2BE": "1:2 + stop to cost at 5%"}
CLASSES = ["direct", "retest", "stop, down", "stop, then up", "neither"]


def classify(lo, hi, entry, stop, tgt):
    ks = np.flatnonzero(lo <= stop)
    kt = np.flatnonzero(hi >= tgt)
    ks = ks[0] if len(ks) else None
    if ks is not None and (not len(kt) or ks <= kt[0]):          # stop came first (ties: stop)
        later = np.flatnonzero(hi[ks + 1:] >= tgt)
        return "stop, then up" if len(later) else "stop, down"
    if not len(kt):
        return "neither"
    k = kt[0]
    return "retest" if k >= 1 and (lo[1: k + 1] <= entry).any() else "direct"


def main():
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    panel = make_panel(prices, universe)
    del prices
    O, H, L, C = (x.to_numpy(float) for x in (panel.open, panel.high, panel.low, panel.close))
    high20 = panel.high.rolling(20, min_periods=20).max().to_numpy(float)
    piv = pivot_lows(panel)
    pc = panel.close.shift(1)
    tr = np.maximum(panel.high - panel.low, np.maximum((panel.high - pc).abs(), (panel.low - pc).abs()))
    atr = tr.rolling(14, min_periods=14).mean()
    cols = {e: j for j, e in enumerate(panel.close.columns)}
    pos = {d: k for k, d in enumerate(panel.sessions)}
    n = len(panel.sessions)
    rows = []
    for path in sorted(glob.glob("data/s_sector_trades_*.csv") + glob.glob("data/s_sector_nifty_trades_*.csv")):
        m = re.match(r"data/(s_sector(?:_nifty)?)_trades_(\w+?)_(W1|W2|Y2018)\.csv", path)
        family, code, win = m.groups()
        t = pd.read_csv(path, parse_dates=["entry_date"])
        for r in t.itertuples():
            j, f = cols.get(r.entity_id), pos.get(r.entry_date)
            if j is None or f is None or f < 1:
                continue
            i = f - 1
            trig = high20[i, j]
            entry = max(trig, O[f, j]) if np.isfinite(trig) else O[f, j]
            if R[code] is None:
                stop, tgt = entry * 0.95, entry * 1.05
            else:
                stop = swing_stop(panel, piv, atr, i, r.entity_id, min(trig, C[i, j]))
                if stop is None or stop >= entry:
                    continue
                tgt = entry + R[code] * (entry - stop)
            for win_len in (20, 40):
                if f + win_len > n:
                    continue
                lo, hi = L[f: f + win_len, j], H[f: f + win_len, j]
                if not np.isfinite(lo).all():
                    lo, hi = np.nan_to_num(lo, nan=np.inf), np.nan_to_num(hi, nan=-np.inf)
                rows.append({"filter": "sector, else Nifty" if family.endswith("nifty") else "sector, else mid/small",
                             "version": code, "period": win, "days": win_len,
                             "cls": classify(lo, hi, entry, stop, tgt)})
    d = pd.DataFrame(rows)
    d.to_csv("data/trade_paths.csv", index=False)
    periods = [("all 2008-2026", ["W1", "W2", "Y2018"]), ("2019-26", ["W1"]), ("2008-17", ["W2"]), ("2018", ["Y2018"])]
    for flt in ["sector, else mid/small", "sector, else Nifty"]:
        for pname, ps in periods:
            print(f"\n=== Filter: {flt} | {pname} ===")
            print(f"  {'version':28s} {'days':>4s} {'trades':>6s}  " + "  ".join(f"{c:>13s}" for c in CLASSES))
            for code in R:
                for wl in (20, 40):
                    x = d[(d["filter"] == flt) & (d.version == code) & (d.period.isin(ps)) & (d.days == wl)]
                    if x.empty:
                        continue
                    share = x.cls.value_counts(normalize=True) * 100
                    print(f"  {LABEL[code]:28s} {wl:4d} {len(x):6d}  " + "  ".join(f"{share.get(c, 0):12.1f}%" for c in CLASSES))


if __name__ == "__main__":
    main()
