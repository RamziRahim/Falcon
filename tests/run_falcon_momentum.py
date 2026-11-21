"""
Falcon -- FM backtest per docs/falcon_momentum_preregistration.md.

    python tests/run_falcon_momentum.py            # both tracks: t40 (primary), t20 (secondary)
    python tests/run_falcon_momentum.py review     # t40 + 4-week review (docs/fm_review_preregistration.md)
"""
import sys
sys.path.insert(0, ".")

import gc

import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES, run_fm
from backtesting.pit_strategies import equal_weight_universe, judge, make_panel
from tests.run_mean_reversion import _nifty

PREREG = "docs/falcon_momentum_preregistration.md"
REVIEW_PREREG = "docs/fm_review_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31")}


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
    ew = {w: equal_weight_universe(panel, pd.Timestamp(a), pd.Timestamp(b)) for w, (a, b) in WINDOWS.items()}
    review = len(sys.argv) > 1 and sys.argv[1] == "review"
    if review and "**Status: FROZEN" not in open(REVIEW_PREREG, encoding="utf-8").read():
        raise SystemExit(f"{REVIEW_PREREG} is not frozen.")
    for ts in ((40,) if review else (40, 20)):
        tag = "fm_review" if review else f"falcon_momentum_t{ts}"
        out = open(f"data/{tag}_result.txt", "w", encoding="utf-8")
        out.write(f"Benchmark: {src}; FM with a {ts}-session time stop{' + 4-week review' if review else ''}\n")
        verdict = {}
        for name, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            equity, trades, stats = run_fm(panel, a, b, nifty, indices, ts, review_at=20 if review else None)
            trades.to_csv(f"data/{tag}_trades_{name}.csv", index=False)
            report = judge(equity, trades, nifty, ew[name])
            closed = trades[trades["exit_reason"] != "OPEN_AT_END"] if not trades.empty else trades
            net = closed["pnl"] / closed["cost_basis"] if len(closed) else pd.Series(dtype=float)
            lines = [f"\n{'=' * 70}\nFM, time stop {ts}  {name} {a.date()} -> {b.date()}\n{'=' * 70}",
                     f"  {'trades (closed)':28s} {len(closed)}",
                     f"  {'win rate after costs':28s} {(net > 0).mean() * 100:.1f}%",
                     f"  {'avg win / avg loss':28s} {net[net > 0].mean() * 100:+.2f}% / {net[net <= 0].mean() * 100:+.2f}%",
                     f"  {'mean net per trade':28s} {net.mean() * 100:+.3f}%",
                     f"  {'exit mix':28s} {closed['exit_reason'].value_counts().to_dict()}",
                     f"  {'stats':28s} {stats}"]
            lines += [f"  {k:28s} {v}" for k, v in report.items() if k != "checks"]
            lines += [f"    [{'PASS' if ok else 'FAIL'}] {c}" for c, ok in report["checks"].items()]
            out.write("\n".join(lines) + "\n")
            out.flush()
            print(f"t{ts} {name}: cagr {report.get('cagr_pct')} vs nifty {report.get('nifty_cagr_pct')} "
                  f"win {(net > 0).mean() * 100:.1f}% {report['verdict']}", flush=True)
            verdict[name] = "PASS" if report["verdict"].startswith("EDGE") else "FAIL"
        out.write(f"\nVerdicts: {verdict}\nFM t{ts}: " + ("PROVISIONAL EDGE (both windows)" if all(v == "PASS" for v in verdict.values()) else "NO DEMONSTRATED EDGE") + "\n")
        out.close()


if __name__ == "__main__":
    main()
