"""
Falcon -- breakout entry + volume exit at the close, per docs/volume_exit_preregistration.md.

    python tests/run_volume_exit.py [W1 ...] > data/volume_exit.log
"""
import sys
sys.path.insert(0, ".")

import gc

import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES
from backtesting.falcon_momentum_entries import run_fm_entries
from backtesting.fixed_bracket import entries_s
from backtesting.pit_strategies import equal_weight_universe, judge, make_panel
from backtesting.s_plus import run_s_plus
from tests.run_mean_reversion import _nifty

PREREG = "docs/volume_exit_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31")}
VERSIONS = [("S3_REF2", "S3", 2.0, None, None),
            ("S3_VX3", "S3", 3.0, None, 1.5), ("S3_VX2", "S3", 2.0, None, 1.5),
            ("S3_RX3", "S3", 3.0, 0.10, 1.5), ("S3_RX2", "S3", 2.0, 0.10, 1.5),
            ("FM_VX3", "FM", 3.0, None, 1.5), ("FM_VX2", "FM", 2.0, None, 1.5),
            ("FM_RX3", "FM", 3.0, 0.10, 1.5), ("FM_RX2", "FM", 2.0, 0.10, 1.5)]
ONLY = sys.argv[1:]


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
    out = open("data/volume_exit_result.txt" if not ONLY else "data/volume_exit_smoke.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; breakout entry + volume exit at the close\n")
    for code, strat, r, rng, vx in VERSIONS:
        for w, (a, b) in WINDOWS.items():
            if ONLY and w not in ONLY:
                continue
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            if strat == "S3":
                equity, trades, extra = run_s_plus(panel, a, b, fn, nifty, r_multiple=r, market_filter=True,
                                                   range_max=rng, vol_exit=vx)
            else:
                equity, trades, extra = run_fm_entries(panel, a, b, nifty, indices, "high20", r_mult=r,
                                                       range_max=rng, vol_exit=vx)
            trades.to_csv(f"data/volume_exit_trades_{code}_{w}.csv", index=False)
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
                  f"grew {grew:.2f}L checks {sum(report['checks'].values())}/6 exits {mix}", flush=True)
    out.close()


if __name__ == "__main__":
    main()
