"""Shared loader and report writer for the half-A tests (docs/close_entry_preregistration.md)."""
import gc

import pandas as pd

from backtesting.pit_strategies import judge, make_panel


def load_half_a(which: str = "A"):
    half = pd.read_csv("data/holdout_split.csv", index_col=0)["half"]
    uni = pd.read_parquet("data/pit/universe_monthly.parquet")
    uni = uni[uni["entity_id"].isin(set(half[half == which].index))]
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    panel = make_panel(prices, uni)
    del prices
    gc.collect()
    return panel


def report(out, code, w, a, b, equity, trades, nifty, ew, extra=None):
    rep = judge(equity, trades, nifty, ew)
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
             f"  {'stats':28s} {extra}",
             f"  {'grew 10 lakh to':28s} {grew:.2f} lakh"]
    lines += [f"  {k:28s} {v}" for k, v in rep.items() if k != "checks"]
    lines += [f"    [{'PASS' if ok else 'FAIL'}] {c}" for c, ok in rep["checks"].items()]
    out.write("\n".join(lines) + "\n")
    out.flush()
    print(f"{code} {w}: cagr {rep.get('cagr_pct')} dd {rep.get('max_drawdown_pct')} nifty {rep.get('nifty_cagr_pct')} "
          f"win {(net > 0).mean() * 100:.1f}% net/trade {net.mean() * 100:+.2f}% n {len(closed)} "
          f"grew {grew:.2f}L checks {sum(rep['checks'].values())}/6", flush=True)
    return rep
