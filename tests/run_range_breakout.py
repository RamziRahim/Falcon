"""
Falcon -- #3 with a true range breakout on half A, per docs/range_breakout_preregistration.md.

    python tests/run_range_breakout.py [W1 ...] > data/range_breakout.log
"""
import sys
sys.path.insert(0, ".")

import gc

import numpy as np
import pandas as pd

from backtesting.fixed_bracket import entries_s_range
from backtesting.pit_strategies import equal_weight_universe, judge, make_panel
from backtesting.s_plus import run_s_plus
from tests.run_mean_reversion import _nifty

PREREG = "docs/range_breakout_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31")}
VERSIONS = [("RB3", 3.0, False), ("RB2", 2.0, False), ("RBK3", 3.0, True), ("RBK2", 2.0, True)]
ONLY = sys.argv[1:]


def first(mask):
    k = np.flatnonzero(mask)
    return k[0] if len(k) else None


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    half = pd.read_csv("data/holdout_split.csv", index_col=0)["half"]
    uni = pd.read_parquet("data/pit/universe_monthly.parquet")
    uni = uni[uni["entity_id"].isin(set(half[half == "A"].index))]
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    panel = make_panel(prices, uni)
    del prices
    gc.collect()
    nifty, src = _nifty()
    fn = entries_s_range(panel, nifty)
    H, L = panel.high.to_numpy(float), panel.low.to_numpy(float)
    SMA = panel.close.rolling(20, min_periods=20).mean().shift(1).to_numpy(float)
    cols = {e: j for j, e in enumerate(panel.close.columns)}
    pos = {d: k for k, d in enumerate(panel.sessions)}
    n = len(pos)
    suffix = "" if not ONLY else "_smoke"
    out = open(f"data/range_breakout_result{suffix}.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; half A only; #3 with a true range breakout\n")
    paths = []
    for code, r, clean in VERSIONS:
        for w, (a, b) in WINDOWS.items():
            if ONLY and w not in ONLY:
                continue
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            levels = []
            equity, trades, extra = run_s_plus(panel, a, b, fn, nifty, r_multiple=r, market_filter=True,
                                               close_vol=1.5, clean_close=clean, levels=levels)
            trades.to_csv(f"data/range_breakout_trades_{code}_{w}.csv", index=False)
            report = judge(equity, trades, nifty, equal_weight_universe(panel, a, b))
            closed = trades[trades["exit_reason"] != "OPEN_AT_END"] if not trades.empty else trades
            net = closed["pnl"] / closed["cost_basis"] if len(closed) else pd.Series(dtype=float)
            grew = 10 * equity["equity"].iloc[-1] / equity["equity"].iloc[0]
            mix = closed["exit_reason"].value_counts().to_dict() if len(closed) else {}
            lines = [f"\n{'=' * 70}\n{code}  {w} {a.date()} -> {b.date()}\n{'=' * 70}",
                     f"  {'trades (closed)':28s} {len(closed)}",
                     f"  {'win rate after costs':28s} {(net > 0).mean() * 100:.1f}%",
                     f"  {'avg win / avg loss':28s} {net[net > 0].mean() * 100:+.2f}% / {net[net <= 0].mean() * 100:+.2f}%",
                     f"  {'mean net per trade':28s} {net.mean() * 100:+.3f}%",
                     f"  {'exit mix':28s} {mix}",
                     f"  {'skipped / stats':28s} {extra}",
                     f"  {'grew 10 lakh to':28s} {grew:.2f} lakh"]
            lines += [f"  {k:28s} {v}" for k, v in report.items() if k != "checks"]
            lines += [f"    [{'PASS' if ok else 'FAIL'}] {c}" for c, ok in report["checks"].items()]
            out.write("\n".join(lines) + "\n")
            out.flush()
            print(f"{code} {w}: cagr {report.get('cagr_pct')} dd {report.get('max_drawdown_pct')} "
                  f"win {(net > 0).mean() * 100:.1f}% net/trade {net.mean() * 100:+.2f}% n {len(closed)} "
                  f"grew {grew:.2f}L checks {sum(report['checks'].values())}/6", flush=True)
            for e, d, fill, stop, tgt in levels:
                j, f = cols[e], pos[pd.Timestamp(d)]
                rg = fn.ranges.get((e, f - 1))
                if rg is None or f + 41 > n:
                    continue
                rlow = rg[1]
                for wl in (20, 40):
                    lo = np.nan_to_num(L[f + 1: f + 1 + wl, j], nan=np.inf)
                    hi = np.nan_to_num(H[f + 1: f + 1 + wl, j], nan=-np.inf)
                    sma = np.where(np.isfinite(SMA[f + 1: f + 1 + wl, j]), SMA[f + 1: f + 1 + wl, j], -np.inf)
                    ks, kt, kb = first(lo <= stop), first(hi >= tgt), first(lo <= fill)

                    def after(k):
                        if k is None or (ks is not None and ks < k) or (kt is not None and kt < k):
                            return None
                        s2, t2 = first(lo[k:] <= stop), first(hi[k:] >= tgt)
                        if s2 is not None and (t2 is None or s2 <= t2):
                            return "then stop"
                        return "then target" if t2 is not None else "then neither"
                    kr = first(lo <= rlow) if rlow > stop else None
                    km = first(lo <= sma)
                    km = km if km is not None and sma[km] > stop else None
                    paths.append({"version": code, "period": w, "days": wl,
                                  "direct": kt is not None and (ks is None or kt < ks) and (kb is None or kb > kt),
                                  "tgt": kt is not None and (ks is None or kt < ks),
                                  "stop": ks is not None and (kt is None or ks <= kt),
                                  "range_low": after(kr), "sma20": after(km), "rl_below_stop": rlow <= stop})
    out.close()
    d = pd.DataFrame(paths)
    d.to_csv(f"data/range_breakout_paths{suffix}.csv", index=False)
    with open(f"data/range_breakout_paths{suffix}.txt", "w", encoding="utf-8") as fh:
        for (code, w, wl), g in d.groupby(["version", "period", "days"], sort=False):
            N = len(g)
            fh.write(f"\n{code} {w} {wl} days, {N} trades | direct {g.direct.mean() * 100:.1f}% | target before stop "
                     f"{g.tgt.mean() * 100:.1f}% | stop first {g.stop.mean() * 100:.1f}% | range low at/below stop "
                     f"{g.rl_below_stop.mean() * 100:.0f}%\n")
            for c, name in (("range_low", "back to range low"), ("sma20", "back to 20-SMA")):
                x = g[c].dropna()
                vc = x.value_counts(normalize=True) * 100
                fh.write(f"   {name:18s} {len(x) / N * 100:5.1f}% -> target {vc.get('then target', 0):4.0f}% | "
                         f"stop {vc.get('then stop', 0):4.0f}% | neither {vc.get('then neither', 0):4.0f}%\n")
    print(open(f"data/range_breakout_paths{suffix}.txt").read())


if __name__ == "__main__":
    main()
