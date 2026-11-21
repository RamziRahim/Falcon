"""
Falcon -- #3 with the sector filter and five exit variants, per
docs/s_sector_preregistration.md. One process; shared panel, filter and entries.

    python tests/run_s_sector.py > data/s_sector.log
    python tests/run_s_sector.py nifty > data/s_sector_nifty.log   # Nifty 50 fallback, R3 and R2
    python tests/run_s_sector.py nifty R3BE R2BE                    # + break-even at +5% (appends)
"""
import sys
sys.path.insert(0, ".")

import gc

import pandas as pd

from backtesting.fixed_bracket import entries_s
from backtesting.pit_strategies import equal_weight_universe, judge, make_panel
from backtesting.s_sector import SectorFilter, run_s_sector
from tests.run_mean_reversion import _nifty

NIFTY_FALLBACK = len(sys.argv) > 1 and sys.argv[1] == "nifty"
PREREG = "docs/s_sector_nifty_preregistration.md" if NIFTY_FALLBACK else "docs/s_sector_preregistration.md"
TAG = "s_sector_nifty" if NIFTY_FALLBACK else "s_sector"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31")}
VARIANTS = {
    "R3": dict(mode="swing", r_multiple=3),
    "R2": dict(mode="swing", r_multiple=2),
    "F5": dict(mode="fixed"),
    "R3H": dict(mode="swing", r_multiple=3, half_at=0.05),
    "R2H": dict(mode="swing", r_multiple=2, half_at=0.05),
    "R3BE": dict(mode="swing", r_multiple=3, be_at=0.05),
    "R2BE": dict(mode="swing", r_multiple=2, be_at=0.05),
}
ONLY = [a for a in sys.argv[2:]]


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    panel = make_panel(prices, universe)
    del prices
    gc.collect()
    nifty, src = _nifty()
    flt = SectorFilter(panel, universe, nifty, pd.read_parquet("data/pit_sources/indices.parquet"),
                       fallback="nifty" if NIFTY_FALLBACK else "bucket")
    fn = entries_s(panel, nifty)
    ew = {w: equal_weight_universe(panel, pd.Timestamp(a), pd.Timestamp(b)) for w, (a, b) in WINDOWS.items()}
    out = open(f"data/{TAG}_result.txt", "a" if ONLY else "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; #3 entries + sector filter\n")
    for code, kw in VARIANTS.items():
        if NIFTY_FALLBACK and code not in (ONLY or ("R3", "R2")):
            continue
        for w, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            flt.used = {"sector": 0, "bucket": 0}
            equity, trades, st = run_s_sector(panel, a, b, fn, flt, **kw)
            trades.to_csv(f"data/{TAG}_trades_{code}_{w}.csv", index=False)
            report = judge(equity, trades, nifty, ew[w])
            closed = trades[trades["exit_reason"] != "OPEN_AT_END"] if not trades.empty else trades
            net = closed["pnl"] / closed["cost_basis"] if len(closed) else pd.Series(dtype=float)
            lines = [f"\n{'=' * 70}\n{code} {kw}  {w} {a.date()} -> {b.date()}\n{'=' * 70}",
                     f"  {'trades (closed)':28s} {len(closed)}",
                     f"  {'win rate after costs':28s} {(net > 0).mean() * 100:.1f}%",
                     f"  {'avg win / avg loss':28s} {net[net > 0].mean() * 100:+.2f}% / {net[net <= 0].mean() * 100:+.2f}%",
                     f"  {'mean net per trade':28s} {net.mean() * 100:+.3f}%",
                     f"  {'exit mix':28s} {closed['exit_reason'].value_counts().to_dict() if len(closed) else {}}",
                     f"  {'stats':28s} {st}",
                     f"  {'filter decided by':28s} {flt.used}"]
            lines += [f"  {k:28s} {v}" for k, v in report.items() if k != "checks"]
            lines += [f"    [{'PASS' if ok else 'FAIL'}] {c}" for c, ok in report["checks"].items()]
            out.write("\n".join(lines) + "\n")
            out.flush()
            print(f"{code} {w}: cagr {report.get('cagr_pct')} nifty {report.get('nifty_cagr_pct')} "
                  f"dd {report.get('max_drawdown_pct')} win {(net > 0).mean() * 100:.1f}% "
                  f"net/trade {net.mean() * 100:+.2f}% n {len(closed)} checks "
                  f"{sum(report['checks'].values())}/6", flush=True)
    out.close()


if __name__ == "__main__":
    main()
