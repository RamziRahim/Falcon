"""
Falcon -- test A holding the top 10 / 15 (and 20 for reference), with and without a
10% stop. docs/a_stop_preregistration.md addendum.

    python tests/run_a_topn.py > data/a_topn.log
"""
import sys
sys.path.insert(0, ".")

import pandas as pd

from backtesting.pit_strategies import equal_weight_universe, judge, make_panel, run_momentum
from tests.run_mean_reversion import _nifty

WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31")}


def main():
    panel = make_panel(pd.read_parquet("data/pit/prices_adjusted.parquet"), pd.read_parquet("data/pit/universe_monthly.parquet"))
    nifty, src = _nifty()
    ew = {w: equal_weight_universe(panel, pd.Timestamp(a), pd.Timestamp(b)) for w, (a, b) in WINDOWS.items()}
    out = open("data/a_topn_result.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; test A top-N, with and without a 10% stop\n")
    for hold in (10, 15):
        for sp in (None, 0.10):
            code = f"A{hold}" + ("-stop10" if sp else "")
            for w, (a, b) in WINDOWS.items():
                a, b = pd.Timestamp(a), pd.Timestamp(b)
                equity, trades = run_momentum(panel, a, b, stop_pct=sp, hold=hold)
                trades.to_csv(f"data/a_topn_trades_{code}_{w}.csv", index=False)
                report = judge(equity, trades, nifty, ew[w])
                closed = trades[trades["exit_reason"] != "OPEN_AT_END"] if not trades.empty else trades
                net = closed["pnl"] / closed["cost_basis"] if len(closed) else pd.Series(dtype=float)
                ye = equity["equity"].resample("YE").last()
                years = [round(ye.iloc[0] / equity["equity"].iloc[0] * 100 - 100, 1)] + [round(v, 1) for v in ye.pct_change().dropna() * 100]
                lines = [f"\n{'=' * 70}\n{code}  {w} {a.date()} -> {b.date()}\n{'=' * 70}",
                         f"  {'positions (closed)':28s} {len(closed)}",
                         f"  {'win rate after costs':28s} {(net > 0).mean() * 100:.1f}%",
                         f"  {'avg win / avg loss':28s} {net[net > 0].mean() * 100:+.2f}% / {net[net <= 0].mean() * 100:+.2f}%",
                         f"  {'exit mix':28s} {closed['exit_reason'].value_counts().to_dict() if len(closed) else {}}",
                         f"  {'calendar years %':28s} {years}"]
                lines += [f"  {k:28s} {v}" for k, v in report.items() if k != "checks"]
                lines += [f"    [{'PASS' if ok else 'FAIL'}] {c}" for c, ok in report["checks"].items()]
                out.write("\n".join(lines) + "\n")
                out.flush()
                fails = [c for c, ok in report["checks"].items() if not ok]
                print(f"{code} {w}: cagr {report.get('cagr_pct')} dd {report.get('max_drawdown_pct')} win {(net > 0).mean() * 100:.1f}% "
                      f"t {report.get('monthly_excess_t_nw3')} top3 {report.get('top3_profit_share')} checks {sum(report['checks'].values())}/6 "
                      f"fails {fails} years {years}", flush=True)
    out.close()


if __name__ == "__main__":
    main()
