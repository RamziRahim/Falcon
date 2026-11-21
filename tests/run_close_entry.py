"""
Falcon -- clean-candle close entry for #3 and FM on half A, per docs/close_entry_preregistration.md.

    python tests/run_close_entry.py [W1 ...] > data/close_entry.log
"""
import sys
sys.path.insert(0, ".")

import gc

import numpy as np
import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES, run_fm
from backtesting.falcon_momentum_entries import run_fm_entries
from backtesting.fixed_bracket import entries_s
from backtesting.pit_strategies import equal_weight_universe, judge, make_panel
from backtesting.s_plus import run_s_plus
from tests.analyse_trade_paths import CLASSES, classify
from tests.run_mean_reversion import _nifty

PREREG = "docs/close_entry_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31")}
VERSIONS = [("S3_REF3", "S", "stop", 3.0), ("S3_REF2", "S", "stop", 2.0),
            ("S3_C3", "S", "close", 3.0), ("S3_C2", "S", "close", 2.0),
            ("S3_CV3", "S", "closevol", 3.0), ("S3_CV2", "S", "closevol", 2.0),
            ("FM_REF3", "F", "monday", 3.0), ("FM_REF2", "F", "monday", 2.0), ("FM_H3", "F", "high20", 3.0),
            ("FM_C3", "F", "closebuy", 3.0), ("FM_C2", "F", "closebuy", 2.0),
            ("FM_CV3", "F", "closebuy_vol", 3.0), ("FM_CV2", "F", "closebuy_vol", 2.0)]
ONLY = sys.argv[1:]


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    half = pd.read_csv("data/holdout_split.csv", index_col=0)["half"]
    keep = set(half[half == "A"].index)
    uni = pd.read_parquet("data/pit/universe_monthly.parquet")
    uni = uni[uni["entity_id"].isin(keep)]
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    panel = make_panel(prices, uni)
    del prices
    gc.collect()
    print(f"half A: {panel.close.shape[1]} stocks", flush=True)
    nifty, src = _nifty()
    ix = pd.read_parquet("data/pit_sources/indices.parquet")
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    base = entries_s(panel, nifty)
    close_fn = lambda i, day, busy: [("closebuy", od[1], od[2], od[4]) for od in base(i, day, busy)]
    H, L = panel.high.to_numpy(float), panel.low.to_numpy(float)
    cols = {e: j for j, e in enumerate(panel.close.columns)}
    pos = {d: k for k, d in enumerate(panel.sessions)}
    n = len(panel.sessions)
    suffix = "" if not ONLY else "_smoke"
    out = open(f"data/close_entry_result{suffix}.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; half A only; clean-candle close entry\n")
    paths = []
    for code, strat, entry, r in VERSIONS:
        for w, (a, b) in WINDOWS.items():
            if ONLY and w not in ONLY:
                continue
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            levels = []
            if strat == "S":
                fn = base if entry == "stop" else close_fn
                equity, trades, extra = run_s_plus(panel, a, b, fn, nifty, r_multiple=r, market_filter=True,
                                                   close_vol=1.5 if entry == "closevol" else None, levels=levels)
            elif entry == "monday":
                equity, trades, extra = run_fm(panel, a, b, nifty, indices, 40, r_mult=r, levels=levels)
            else:
                equity, trades, extra = run_fm_entries(panel, a, b, nifty, indices, entry, r_mult=r, levels=levels)
            trades.to_csv(f"data/close_entry_trades_{code}_{w}.csv", index=False)
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
            at_close = entry in ("close", "closevol", "closebuy", "closebuy_vol")
            for lv in levels:
                e, d, fill, stop, tgt = lv[:5]
                j, f = cols[e], pos[pd.Timestamp(d)]
                for wl in (20, 40):
                    if f + 1 + wl > n:
                        continue
                    s0 = f + 1 if at_close else f
                    lo = np.nan_to_num(L[s0: s0 + wl, j], nan=np.inf)
                    hi = np.nan_to_num(H[s0: s0 + wl, j], nan=-np.inf)
                    after = np.nan_to_num(L[f + 1: f + 1 + wl, j], nan=np.inf)
                    paths.append({"version": code, "period": w, "days": wl,
                                  "back_to_buy": bool((after <= fill).any()), "hit_stop": bool((lo <= stop).any()),
                                  "cls": classify(lo if not at_close else np.r_[fill, lo][:wl],
                                                  hi if not at_close else np.r_[fill, hi][:wl], fill, stop, tgt)})
    out.close()
    d = pd.DataFrame(paths)
    d.to_csv(f"data/close_entry_paths{suffix}.csv", index=False)
    with open(f"data/close_entry_paths{suffix}.txt", "w", encoding="utf-8") as fh:
        for pname, ps in [("2019-26", ["W1"]), ("2008-17", ["W2"]), ("2018", ["Y2018"])]:
            fh.write(f"\n=== half A | {pname} ===\n")
            fh.write(f"  {'version':10s} {'days':>4s} {'trades':>6s} {'back to buy':>12s} {'hit stop':>9s}  "
                     + "  ".join(f"{c:>13s}" for c in CLASSES) + "\n")
            for code, *_ in VERSIONS:
                for wl in (20, 40):
                    x = d[(d.version == code) & (d.period.isin(ps)) & (d.days == wl)]
                    if x.empty:
                        continue
                    sh = x.cls.value_counts(normalize=True) * 100
                    fh.write(f"  {code:10s} {wl:4d} {len(x):6d} {x.back_to_buy.mean() * 100:11.1f}% {x.hit_stop.mean() * 100:8.1f}%  "
                             + "  ".join(f"{sh.get(c, 0):12.1f}%" for c in CLASSES) + "\n")
    print(open(f"data/close_entry_paths{suffix}.txt").read())


if __name__ == "__main__":
    main()
