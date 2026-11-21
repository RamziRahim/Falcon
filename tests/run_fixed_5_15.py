"""
Falcon -- fixed -5% / +15% on FM and on #3 + Nifty filter, per
docs/fixed_5_15_preregistration.md.

    python tests/run_fixed_5_15.py > data/fixed_5_15.log
"""
import sys
sys.path.insert(0, ".")

import gc

import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES, run_fm
from backtesting.fixed_bracket import entries_s
from backtesting.pit_strategies import equal_weight_universe, judge, make_panel
from backtesting.s_plus import run_s_plus
from tests.run_mean_reversion import _nifty

PREREG = "docs/fixed_5_15_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31")}


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    panel = make_panel(prices, universe)
    del prices
    gc.collect()
    nifty, src = _nifty()
    ix = pd.read_parquet("data/pit_sources/indices.parquet")
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    fn = entries_s(panel, nifty)
    ew = {w: equal_weight_universe(panel, pd.Timestamp(a), pd.Timestamp(b)) for w, (a, b) in WINDOWS.items()}
    out = open("data/fixed_5_15_result.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; fixed -5% / +15%\n")
    for code in ("FM-F515", "S3-F515"):
        for w, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            if code == "FM-F515":
                equity, trades, _ = run_fm(panel, a, b, nifty, indices, 40, fixed_stop=0.05, fixed_tgt=0.15)
            else:
                equity, trades, _ = run_s_plus(panel, a, b, fn, nifty, market_filter=True, fixed_stop=0.05, fixed_tgt=0.15)
            trades.to_csv(f"data/fixed_5_15_trades_{code}_{w}.csv", index=False)
            report = judge(equity, trades, nifty, ew[w])
            closed = trades[trades["exit_reason"] != "OPEN_AT_END"] if not trades.empty else trades
            net = closed["pnl"] / closed["cost_basis"] if len(closed) else pd.Series(dtype=float)
            lines = [f"\n{'=' * 70}\n{code}  {w} {a.date()} -> {b.date()}\n{'=' * 70}",
                     f"  {'trades (closed)':28s} {len(closed)}",
                     f"  {'win rate after costs':28s} {(net > 0).mean() * 100:.1f}%",
                     f"  {'avg win / avg loss':28s} {net[net > 0].mean() * 100:+.2f}% / {net[net <= 0].mean() * 100:+.2f}%",
                     f"  {'mean net per trade':28s} {net.mean() * 100:+.3f}%",
                     f"  {'exit mix':28s} {closed['exit_reason'].value_counts().to_dict() if len(closed) else {}}"]
            lines += [f"  {k:28s} {v}" for k, v in report.items() if k != "checks"]
            lines += [f"    [{'PASS' if ok else 'FAIL'}] {c}" for c, ok in report["checks"].items()]
            out.write("\n".join(lines) + "\n")
            out.flush()
            ex = closed["exit_reason"].value_counts().to_dict() if len(closed) else {}
            print(f"{code} {w}: cagr {report.get('cagr_pct')} nifty {report.get('nifty_cagr_pct')} dd {report.get('max_drawdown_pct')} "
                  f"win {(net > 0).mean() * 100:.1f}% avg win/loss {net[net > 0].mean() * 100:+.1f}/{net[net <= 0].mean() * 100:+.1f} "
                  f"net/trade {net.mean() * 100:+.2f}% n {len(closed)} checks {sum(report['checks'].values())}/6 {ex}", flush=True)
    out.close()


if __name__ == "__main__":
    main()
