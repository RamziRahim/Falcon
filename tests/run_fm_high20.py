"""
Falcon -- FM watch list + 20-day-high buy-stop entry, five exit variants, per
docs/fm_high20_preregistration.md.

    python tests/run_fm_high20.py > data/fm_high20.log
"""
import sys
sys.path.insert(0, ".")

import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES
from backtesting.falcon_momentum_entries import run_fm_entries
from backtesting.pit_strategies import equal_weight_universe, judge, make_panel
from tests.run_mean_reversion import _nifty

PREREG = "docs/fm_high20_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31")}
VARIANTS = {"H3": dict(r_mult=3.0), "H2": dict(r_mult=2.0), "H5": dict(fixed_stop=0.05, fixed_tgt=0.05),
            "H3BE": dict(r_mult=3.0, be_at=0.05), "H2BE": dict(r_mult=2.0, be_at=0.05)}


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    only = sys.argv[1:]
    panel = make_panel(pd.read_parquet("data/pit/prices_adjusted.parquet"), pd.read_parquet("data/pit/universe_monthly.parquet"))
    nifty, src = _nifty()
    ix = pd.read_parquet("data/pit_sources/indices.parquet")
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    ew = {w: equal_weight_universe(panel, pd.Timestamp(a), pd.Timestamp(b)) for w, (a, b) in WINDOWS.items()}
    out = open("data/fm_high20_result.txt", "a" if only else "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; FM watch list + 20-day-high entry\n")
    for code, kw in VARIANTS.items():
        if only and code not in only:
            continue
        for w, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            equity, trades, stats = run_fm_entries(panel, a, b, nifty, indices, "high20", **kw)
            trades.to_csv(f"data/fm_high20_trades_{code}_{w}.csv", index=False)
            report = judge(equity, trades, nifty, ew[w])
            closed = trades[trades["exit_reason"] != "OPEN_AT_END"] if not trades.empty else trades
            net = closed["pnl"] / closed["cost_basis"] if len(closed) else pd.Series(dtype=float)
            lines = [f"\n{'=' * 70}\n{code} {kw}  {w} {a.date()} -> {b.date()}\n{'=' * 70}",
                     f"  {'trades (closed)':28s} {len(closed)}",
                     f"  {'win rate after costs':28s} {(net > 0).mean() * 100:.1f}%",
                     f"  {'avg win / avg loss':28s} {net[net > 0].mean() * 100:+.2f}% / {net[net <= 0].mean() * 100:+.2f}%",
                     f"  {'mean net per trade':28s} {net.mean() * 100:+.3f}%",
                     f"  {'exit mix':28s} {closed['exit_reason'].value_counts().to_dict() if len(closed) else {}}",
                     f"  {'stats':28s} {stats}"]
            lines += [f"  {k:28s} {v}" for k, v in report.items() if k != "checks"]
            lines += [f"    [{'PASS' if ok else 'FAIL'}] {c}" for c, ok in report["checks"].items()]
            out.write("\n".join(lines) + "\n")
            out.flush()
            print(f"{code} {w}: cagr {report.get('cagr_pct')} dd {report.get('max_drawdown_pct')} win {(net > 0).mean() * 100:.1f}% "
                  f"net/trade {net.mean() * 100:+.2f}% n {len(closed)} checks {sum(report['checks'].values())}/6 "
                  f"exits {closed['exit_reason'].value_counts().to_dict() if len(closed) else {}}", flush=True)
    out.close()


if __name__ == "__main__":
    main()
