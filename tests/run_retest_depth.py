"""
Falcon -- #3 retest entries (candle low / 20-EMA / 20-SMA) on half A, per
docs/retest_depth_preregistration.md.

    python tests/run_retest_depth.py [W1 ...] > data/retest_depth.log
"""
import sys
sys.path.insert(0, ".")

import gc

import pandas as pd

from backtesting.fixed_bracket import entries_s
from backtesting.pit_strategies import equal_weight_universe, judge, make_panel
from backtesting.s_retest import run_retest
from tests.run_mean_reversion import _nifty

PREREG = "docs/retest_depth_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31")}
MODES = {"CL": "candle_low", "E": "ema20", "S": "sma20"}
VERSIONS = [(f"{pre}{m}{r}", mode, float(r), pre == "K")
            for pre in ("R", "K") for m, mode in MODES.items() for r in (3, 2)]
ONLY = sys.argv[1:]


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
    fn = entries_s(panel, nifty)
    out = open("data/retest_depth_result.txt" if not ONLY else "data/retest_depth_smoke.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; half A only; #3 retest entries\n")
    for code, mode, r, clean in VERSIONS:
        for w, (a, b) in WINDOWS.items():
            if ONLY and w not in ONLY:
                continue
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            equity, trades, st = run_retest(panel, a, b, fn, nifty, mode, r_multiple=r, clean=clean)
            trades.to_csv(f"data/retest_depth_trades_{code}_{w}.csv", index=False)
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
                     f"  {'stats':28s} {st}",
                     f"  {'grew 10 lakh to':28s} {grew:.2f} lakh"]
            lines += [f"  {k:28s} {v}" for k, v in report.items() if k != "checks"]
            lines += [f"    [{'PASS' if ok else 'FAIL'}] {c}" for c, ok in report["checks"].items()]
            out.write("\n".join(lines) + "\n")
            out.flush()
            print(f"{code} {w}: cagr {report.get('cagr_pct')} dd {report.get('max_drawdown_pct')} "
                  f"win {(net > 0).mean() * 100:.1f}% net/trade {net.mean() * 100:+.2f}% n {len(closed)} "
                  f"grew {grew:.2f}L checks {sum(report['checks'].values())}/6 "
                  f"filled {st['filled']}/{st['breakouts']}", flush=True)
    out.close()


if __name__ == "__main__":
    main()
