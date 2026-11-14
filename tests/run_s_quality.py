"""
Falcon -- #3 with quality breakouts, per docs/s_quality_preregistration.md.

    python tests/run_s_quality.py > data/s_quality.log
"""
import sys
sys.path.insert(0, ".")

import pandas as pd

from backtesting.fixed_bracket import entries_s_quality
from backtesting.pit_strategies import equal_weight_universe, judge, make_panel
from backtesting.s_plus import run_s_plus
from tests.run_mean_reversion import _nifty

PREREG = "docs/s_quality_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31")}


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    panel = make_panel(pd.read_parquet("data/pit/prices_adjusted.parquet"), pd.read_parquet("data/pit/universe_monthly.parquet"))
    nifty, src = _nifty()
    fn = entries_s_quality(panel, nifty)
    out = open("data/s_quality_result.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; #3 + quality breakout + Nifty filter\n")
    for code, r in (("Q3", 3.0), ("Q2", 2.0)):
        for w, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            equity, trades, skipped = run_s_plus(panel, a, b, fn, nifty, r_multiple=r, market_filter=True)
            trades.to_csv(f"data/s_quality_trades_{code}_{w}.csv", index=False)
            report = judge(equity, trades, nifty, equal_weight_universe(panel, a, b))
            closed = trades[trades["exit_reason"] != "OPEN_AT_END"] if not trades.empty else trades
            net = closed["pnl"] / closed["cost_basis"] if len(closed) else pd.Series(dtype=float)
            lines = [f"\n{'=' * 70}\n{code}  {w} {a.date()} -> {b.date()}\n{'=' * 70}",
                     f"  {'trades (closed)':28s} {len(closed)}",
                     f"  {'win rate after costs':28s} {(net > 0).mean() * 100:.1f}%",
                     f"  {'avg win / avg loss':28s} {net[net > 0].mean() * 100:+.2f}% / {net[net <= 0].mean() * 100:+.2f}%",
                     f"  {'mean net per trade':28s} {net.mean() * 100:+.3f}%",
                     f"  {'exit mix':28s} {closed['exit_reason'].value_counts().to_dict() if len(closed) else {}}",
                     f"  {'skipped':28s} {skipped}"]
            lines += [f"  {k:28s} {v}" for k, v in report.items() if k != "checks"]
            lines += [f"    [{'PASS' if ok else 'FAIL'}] {c}" for c, ok in report["checks"].items()]
            out.write("\n".join(lines) + "\n")
            out.flush()
            print(f"{code} {w}: cagr {report.get('cagr_pct')} dd {report.get('max_drawdown_pct')} win {(net > 0).mean() * 100:.1f}% "
                  f"net/trade {net.mean() * 100:+.2f}% n {len(closed)} checks {sum(report['checks'].values())}/6 "
                  f"exposure {report.get('avg_gross_exposure_pct')} exits {closed['exit_reason'].value_counts().to_dict() if len(closed) else {}}", flush=True)
    out.close()


if __name__ == "__main__":
    main()
