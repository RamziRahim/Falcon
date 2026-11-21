"""
Falcon -- test A with and without a 10% stop, per docs/a_stop_preregistration.md.

    python tests/run_a_stop.py > data/a_stop.log
"""
import sys
sys.path.insert(0, ".")

import pandas as pd

from backtesting.pit_strategies import equal_weight_universe, judge, make_panel, run_momentum
from tests.run_mean_reversion import _nifty

PREREG = "docs/a_stop_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31")}


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    panel = make_panel(pd.read_parquet("data/pit/prices_adjusted.parquet"), pd.read_parquet("data/pit/universe_monthly.parquet"))
    nifty, src = _nifty()
    out = open("data/a_stop_result.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; test A, with and without a 10% stop\n")
    for code, sp in (("A", None), ("A10", 0.10)):
        for w, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            equity, trades = run_momentum(panel, a, b, stop_pct=sp)
            trades.to_csv(f"data/a_stop_trades_{code}_{w}.csv", index=False)
            report = judge(equity, trades, nifty, equal_weight_universe(panel, a, b))
            closed = trades[trades["exit_reason"] != "OPEN_AT_END"] if not trades.empty else trades
            net = closed["pnl"] / closed["cost_basis"] if len(closed) else pd.Series(dtype=float)
            yearly = equity["equity"].resample("YE").last().pct_change().dropna() * 100
            first = equity["equity"].resample("YE").last().iloc[0] / equity["equity"].iloc[0] * 100 - 100
            lines = [f"\n{'=' * 70}\n{code}  {w} {a.date()} -> {b.date()}\n{'=' * 70}",
                     f"  {'positions (closed)':28s} {len(closed)}",
                     f"  {'win rate after costs':28s} {(net > 0).mean() * 100:.1f}%",
                     f"  {'avg win / avg loss':28s} {net[net > 0].mean() * 100:+.2f}% / {net[net <= 0].mean() * 100:+.2f}%",
                     f"  {'exit mix':28s} {closed['exit_reason'].value_counts().to_dict() if len(closed) else {}}",
                     f"  {'calendar years %':28s} {[round(first, 1)] + [round(v, 1) for v in yearly]}"]
            lines += [f"  {k:28s} {v}" for k, v in report.items() if k != "checks"]
            lines += [f"    [{'PASS' if ok else 'FAIL'}] {c}" for c, ok in report["checks"].items()]
            out.write("\n".join(lines) + "\n")
            out.flush()
            print(f"{code} {w}: cagr {report.get('cagr_pct')} nifty {report.get('nifty_cagr_pct')} ew {report.get('ew_universe_cagr_pct')} "
                  f"dd {report.get('max_drawdown_pct')} nifty_dd {report.get('nifty_max_drawdown_pct')} win {(net > 0).mean() * 100:.1f}% "
                  f"checks {sum(report['checks'].values())}/6 exits {closed['exit_reason'].value_counts().to_dict()}", flush=True)
    out.close()


if __name__ == "__main__":
    main()
