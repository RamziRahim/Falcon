"""
Falcon -- exit variants per docs/exit_variants_preregistration.md. All four
tracks run in one process (one panel load; parallel runs ran out of memory):

    python tests/run_exit_variants.py            # candle5 candle8 half2 half3
    python tests/run_exit_variants.py half2      # a single track
"""
import sys
sys.path.insert(0, ".")

import gc

import pandas as pd

from backtesting.exit_variants import run_variant
from backtesting.fixed_bracket import entries_b, entries_f, entries_mr, entries_s
from backtesting.pit_strategies import equal_weight_universe, judge, make_panel
from tests.run_mean_reversion import _nifty

PREREG = "docs/exit_variants_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31")}
TRACKS = {
    "candle5": dict(entries=("S", "B", "F"), kw=dict(stop_mode="candle", target_pct=0.05), title="breakout-candle stop, target +5%"),
    "candle8": dict(entries=("S", "B", "F"), kw=dict(stop_mode="candle", target_pct=0.08), title="breakout-candle stop, target +8%"),
    "half2": dict(entries=("F", "S", "B", "MR"), kw=dict(stop_mode="swing", r_multiple=2, partial=True), title="swing-low stop, 1:2, half at 1R + break-even"),
    "half3": dict(entries=("F", "S", "B", "MR"), kw=dict(stop_mode="swing", r_multiple=3, partial=True), title="swing-low stop, 1:3, half at 1.5R + break-even"),
}


def main():
    names = sys.argv[1:] or list(TRACKS)
    if any(n not in TRACKS for n in names):
        raise SystemExit(f"Only the pre-registered tracks may be run: {list(TRACKS)}")
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    panel = make_panel(prices, universe)
    panel100 = make_panel(prices, universe[universe["rank"] <= 100])
    del prices
    gc.collect()
    nifty, src = _nifty()
    ew = {w: equal_weight_universe(panel, pd.Timestamp(s), pd.Timestamp(e)) for w, (s, e) in WINDOWS.items()}
    for track in names:
        spec = TRACKS[track]
        out = open(f"data/exit_variants_{track}_result.txt", "w", encoding="utf-8")
        out.write(f"Benchmark: {src}; {spec['title']}\n")
        verdicts = {}
        for name, (start, end) in WINDOWS.items():
            start, end = pd.Timestamp(start), pd.Timestamp(end)
            setups = pd.read_parquet(f"data/pit/falcon_setups_{start.date()}_{end.date()}.parquet")
            makers = {
                "F": (panel, lambda: entries_f(panel, setups)),
                "S": (panel, lambda: entries_s(panel, nifty)),
                "B": (panel, lambda: entries_b(panel)),
                "MR": (panel100, lambda: entries_mr(panel100, nifty)),
            }
            for label in spec["entries"]:
                p, make = makers[label]
                equity, trades, skipped, halves = run_variant(p, start, end, make(), **spec["kw"])
                trades.to_csv(f"data/exit_variants_{track}_trades_{label}_{name}.csv", index=False)
                report = judge(equity, trades, nifty, ew[name])
                closed = trades[trades["exit_reason"] != "OPEN_AT_END"] if not trades.empty else trades
                net = closed["pnl"] / closed["cost_basis"] if len(closed) else pd.Series(dtype=float)
                lines = [f"\n{'=' * 70}\n{label} entries + {spec['title']}  {name} {start.date()} -> {end.date()}\n{'=' * 70}",
                         f"  {'trades (closed)':28s} {len(closed)}",
                         f"  {'win rate after costs':28s} {(net > 0).mean() * 100:.1f}%",
                         f"  {'avg win / avg loss':28s} {net[net > 0].mean() * 100:+.2f}% / {net[net <= 0].mean() * 100:+.2f}%",
                         f"  {'mean net per trade':28s} {net.mean() * 100:+.3f}%",
                         f"  {'half exits taken':28s} {halves}",
                         f"  {'exit mix':28s} {closed['exit_reason'].value_counts().to_dict()}",
                         f"  {'signals skipped':28s} {skipped}"]
                lines += [f"  {k:28s} {v}" for k, v in report.items() if k != "checks"]
                lines += [f"    [{'PASS' if ok else 'FAIL'}] {c}" for c, ok in report["checks"].items()]
                out.write("\n".join(lines) + "\n")
                out.flush()
                print(f"{track} {label} {name}: cagr {report.get('cagr_pct')} win {(net > 0).mean() * 100:.1f}% {report['verdict']}", flush=True)
                verdicts.setdefault(label, {})[name] = "PASS" if report["verdict"].startswith("EDGE") else "FAIL"
        out.write(f"\nVerdicts: {verdicts}\n")
        for label, v in verdicts.items():
            out.write(f"{label}: " + ("PROVISIONAL EDGE (both windows)" if all(x == "PASS" for x in v.values()) else "NO DEMONSTRATED EDGE") + "\n")
        out.close()


if __name__ == "__main__":
    main()
