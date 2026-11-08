"""
Falcon -- combining A10, #3 + Nifty and FM, per docs/portfolio_combo_preregistration.md.

    python tests/run_portfolio_combo.py [W1 ...] > data/portfolio_combo.log
"""
import sys
sys.path.insert(0, ".")

import gc

import numpy as np
import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES, run_fm
from backtesting.fixed_bracket import entries_s
from backtesting.pit_strategies import equal_weight_universe, judge, make_panel, run_momentum
from backtesting.s_plus import run_s_plus
from tests.run_mean_reversion import _nifty

PREREG = "docs/portfolio_combo_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31")}
COMBOS = {"P_ASF_R": ("ASF", True), "P_ASF_H": ("ASF", False), "P_AS_R": ("AS", True),
          "P_AF_R": ("AF", True), "P_SF_R": ("SF", True)}
ONLY = sys.argv[1:]


def combine(sleeves: dict, codes: str, rebalance: bool):
    eq = pd.DataFrame({c: sleeves[c][0]["equity"] for c in codes}).ffill().dropna()
    gx = pd.DataFrame({c: sleeves[c][0]["gross_exposure"] for c in codes}).reindex(eq.index).ffill().fillna(0)
    n = len(codes)
    if rebalance:
        rets = eq.pct_change().fillna(0)
        month = eq.index.to_period("M")
        total, w = [1.0], np.full(n, 1 / n)
        weights = []
        for k in range(len(eq)):
            if k > 0:
                if month[k] != month[k - 1]:             # reset at the first session of a new month
                    w = np.full(n, 1 / n)
                g = w * (1 + rets.iloc[k].to_numpy())
                total.append(total[-1] * g.sum())
                w = g / g.sum()
            weights.append(w.copy())
        comb = pd.Series(total, index=eq.index)
        wdf = pd.DataFrame(weights, index=eq.index, columns=list(codes))
    else:
        norm = eq / eq.iloc[0]
        comb = norm.sum(axis=1) / n
        wdf = norm.div(norm.sum(axis=1), axis=0)
    expo = (wdf * gx).sum(axis=1)
    start = eq.iloc[0].mean()
    equity = pd.DataFrame({"equity": comb * start, "gross_exposure": expo})
    rows = []
    for c in codes:
        t = sleeves[c][1].copy()
        if t.empty:
            continue
        d = pd.to_datetime(t["entry_date"])
        pos = eq.index.searchsorted(d).clip(0, len(eq) - 1)
        scale = (wdf[c].to_numpy()[pos] * equity["equity"].to_numpy()[pos]) / eq[c].to_numpy()[pos]
        for col in ("pnl", "cost_basis", "proceeds"):
            if col in t:
                t[col] = t[col] * scale
        t["sleeve"] = c
        rows.append(t)
    return equity, pd.concat(rows, ignore_index=True)


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    panel = make_panel(prices, pd.read_parquet("data/pit/universe_monthly.parquet"))
    del prices
    gc.collect()
    nifty, src = _nifty()
    ix = pd.read_parquet("data/pit_sources/indices.parquet")
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    fn = entries_s(panel, nifty)
    out = open("data/portfolio_combo_result.txt" if not ONLY else "data/portfolio_combo_smoke.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; portfolio combinations of A10, #3 + Nifty, FM R3\n")

    def write(code, w, a, b, equity, trades, ew, extra=""):
        report = judge(equity, trades, nifty, ew)
        closed = trades[trades["exit_reason"] != "OPEN_AT_END"] if not trades.empty else trades
        grew = 10 * equity["equity"].iloc[-1] / equity["equity"].iloc[0]
        lines = [f"\n{'=' * 70}\n{code}  {w} {a.date()} -> {b.date()}\n{'=' * 70}",
                 f"  {'trades (closed)':28s} {len(closed)}",
                 f"  {'grew 10 lakh to':28s} {grew:.2f} lakh"]
        if extra:
            lines.append(f"  {'monthly return corr':28s} {extra}")
        lines += [f"  {k:28s} {v}" for k, v in report.items() if k != "checks"]
        lines += [f"    [{'PASS' if ok else 'FAIL'}] {c}" for c, ok in report["checks"].items()]
        out.write("\n".join(lines) + "\n")
        out.flush()
        print(f"{code} {w}: cagr {report.get('cagr_pct')} dd {report.get('max_drawdown_pct')} "
              f"nifty {report.get('nifty_cagr_pct')} n {len(closed)} grew {grew:.2f}L "
              f"checks {sum(report['checks'].values())}/6", flush=True)

    for w, (a, b) in WINDOWS.items():
        if ONLY and w not in ONLY:
            continue
        a, b = pd.Timestamp(a), pd.Timestamp(b)
        ew = equal_weight_universe(panel, a, b)
        sleeves = {"A": run_momentum(panel, a, b, stop_pct=0.10),
                   "S": run_s_plus(panel, a, b, fn, nifty, r_multiple=3.0, market_filter=True)[:2],
                   "F": run_fm(panel, a, b, nifty, indices, 40)[:2]}
        for c, (eq, tr) in sleeves.items():
            eq.to_csv(f"data/portfolio_combo_equity_{c}_{w}.csv")
            write(f"sleeve_{c}", w, a, b, eq, tr, ew)
        m = pd.DataFrame({c: s[0]["equity"].resample("ME").last().pct_change() for c, s in sleeves.items()}).dropna()
        corr = m.corr().round(2)
        cstr = f"A-S {corr.loc['A', 'S']}, A-F {corr.loc['A', 'F']}, S-F {corr.loc['S', 'F']}"
        for code, (codes, reb) in COMBOS.items():
            equity, trades = combine(sleeves, codes, reb)
            write(code, w, a, b, equity, trades, ew, cstr)
    out.close()


if __name__ == "__main__":
    main()
