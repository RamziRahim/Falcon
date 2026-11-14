"""
Falcon -- draw sample strategy-#3 entries from data/s_breakout_outcomes.csv:
one breakout that came back to the breakout level and then hit the 1:3 target,
one that went straight to target, and one that failed (stopped). Candles,
20-day-high breakout level, entry, stop, 1:3 target and +5% line.

    python tests/plot_s_breakout_samples.py   -> data/charts/s_breakout_samples.png
"""
import sys
sys.path.insert(0, ".")

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from backtesting.pit_strategies import make_panel

BEFORE, AFTER = 45, 22


def candles(ax, o, h, l, c):
    for k in range(len(o)):
        if not np.isfinite(o[k]):
            continue
        up = c[k] >= o[k]
        col = "#1a9850" if up else "#d73027"
        ax.vlines(k, l[k], h[k], color=col, linewidth=0.8)
        ax.add_patch(plt.Rectangle((k - 0.35, min(o[k], c[k])), 0.7, max(abs(c[k] - o[k]), 1e-9),
                                   color=col, alpha=0.9))


def main():
    d = pd.read_csv("data/s_breakout_outcomes.csv", parse_dates=["date"])
    d = d[(d.date >= "2019-01-01") & (d.risk_pct.between(4, 9))]
    picks = [
        ("Came back to the breakout level, then hit the 1:3 target", d[d.t3 & d.retest_before_t3]),
        ("Went straight to the 1:3 target", d[d.t3 & ~d.retest_before_t3]),
        ("Failed: stop hit", d[d.stopped & ~d.t5]),
    ]
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    panel = make_panel(prices, universe)
    sym = panel.symbol
    fig, axes = plt.subplots(len(picks), 1, figsize=(12, 13))
    rng = np.random.default_rng(7)
    for ax, (title, pool) in zip(axes, picks):
        r = pool.iloc[int(rng.integers(len(pool)))]
        f = panel.sessions.get_loc(r.date)
        sl = slice(f - BEFORE, f + AFTER)
        e = r.entity
        o, h, l, c = (x[e].iloc[sl].to_numpy(float) for x in (panel.open, panel.high, panel.low, panel.close))
        dates = panel.sessions[sl]
        candles(ax, o, h, l, c)
        x0 = BEFORE
        ax.hlines(r.level, x0 - 20, x0 + AFTER - 1, color="#4575b4", linestyle="--", linewidth=1.2,
                  label=f"20-day high (buy-stop) {r.level:.1f}")
        ax.hlines(r.stop, x0, x0 + AFTER - 1, color="#d73027", linewidth=1.4, label=f"stop {r.stop:.1f} (-{r.risk_pct:.1f}%)")
        t3 = r.entry + 3 * (r.entry - r.stop)
        ax.hlines(t3, x0, x0 + AFTER - 1, color="#1a9850", linewidth=1.4, label=f"1:3 target {t3:.1f} (+{3 * r.risk_pct:.1f}%)")
        ax.hlines(r.entry * 1.05, x0, x0 + AFTER - 1, color="#fdae61", linestyle=":", linewidth=1.4, label="+5%")
        ax.scatter([x0], [r.entry], marker="^", s=140, color="black", zorder=5, label=f"entry {r.entry:.1f}")
        ax.axvspan(x0 + 20 - 0.5, x0 + 20 + 0.5, color="grey", alpha=0.15)
        ax.set_xticks(range(0, len(dates), 10))
        ax.set_xticklabels([dt.strftime("%d %b %y") for dt in dates[::10]], fontsize=8)
        ax.set_title(f"{sym.get(e, e)}, entry {r.date:%d %b %Y}: {title}", fontsize=11, loc="left")
        ax.legend(fontsize=8, loc="upper left")
        ax.grid(alpha=0.2)
    fig.suptitle("Strategy #3 entries: buy-stop at the 20-day high, stop below the swing low, 1:3 target, 20-session limit (grey)",
                 fontsize=11)
    fig.tight_layout()
    os.makedirs("data/charts", exist_ok=True)
    fig.savefig("data/charts/s_breakout_samples.png", dpi=110)
    print("saved data/charts/s_breakout_samples.png")


if __name__ == "__main__":
    main()
