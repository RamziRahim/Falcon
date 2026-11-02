"""
Falcon -- strategy A (monthly momentum) on the later window, judged by
docs/momentum_confirmation_preregistration.md.

    python tests/run_momentum_confirmation.py > data/momentum_confirmation_result.txt

Needs data/pit/ rebuilt with the 2025-2026 bhavcopies.
"""
import sys
sys.path.insert(0, ".")

import pandas as pd

from backtesting.pit_strategies import equal_weight_universe, judge, make_panel, run_momentum

PREREG = "docs/momentum_confirmation_preregistration.md"
START = pd.Timestamp("2024-08-01")
DRAWDOWN_TOLERANCE_PP = 15.0


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    prices = pd.read_parquet("data/pit/prices_adjusted.parquet")
    universe = pd.read_parquet("data/pit/universe_monthly.parquet")
    end = prices["Date"].max()
    if end < pd.Timestamp("2025-06-30"):
        raise SystemExit(f"data/pit/ only reaches {end.date()} -- rebuild it with the 2025-2026 bhavcopies first.")
    panel = make_panel(prices, universe)
    nifty = pd.read_parquet("data/raw/^NSEI.parquet")
    nifty["Date"] = pd.to_datetime(nifty["Date"])
    if nifty["Date"].dt.tz is not None:
        nifty["Date"] = nifty["Date"].dt.tz_localize(None)
    nifty = nifty.set_index("Date")["Close"].sort_index()
    nifty.index = nifty.index.normalize()
    if nifty.index.max() < end - pd.Timedelta(days=10):
        raise SystemExit(f"^NSEI only reaches {nifty.index.max().date()}, data/pit/ reaches {end.date()} -- refresh the benchmark.")

    equity, trades = run_momentum(panel, START, end)
    trades.to_csv("data/momentum_confirmation_trades.csv", index=False)
    report = judge(equity, trades, nifty, equal_weight_universe(panel, START, end))
    checks = {
        "CAGR beats Nifty": report["cagr_pct"] > report["nifty_cagr_pct"],
        "CAGR beats PIT equal-weight universe": report["cagr_pct"] > report["ew_universe_cagr_pct"],
        "max drawdown within Nifty's - 15 pp": report["max_drawdown_pct"] >= report["nifty_max_drawdown_pct"] - DRAWDOWN_TOLERANCE_PP,
        "top-3 positions < 50% of profit": report["top3_profit_share"] < 0.5,
    }
    print(f"Strategy A, confirmation window {START.date()} -> {end.date()}\n" + "=" * 70)
    for k, v in report.items():
        if k not in ("checks", "verdict"):
            print(f"  {k:28s} {v}")
    print("  (monthly excess t is reported only; not a criterion for this window)")
    print("  Pre-registered confirmation checks:")
    for name, ok in checks.items():
        print(f"    [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\nVERDICT: {'CONFIRMED on the later window' if all(checks.values()) else 'NOT CONFIRMED on the later window'}")
    print("\nCalendar-period returns (strategy vs Nifty):")
    nif = nifty.reindex(nifty.index.union(equity.index)).ffill().reindex(equity.index)
    for y in sorted(set(equity.index.year)):
        s = equity["equity"][equity.index.year == y]
        n = nif[nif.index.year == y]
        prev_s = equity["equity"][equity.index.year < y]
        prev_n = nif[nif.index.year < y]
        s0 = prev_s.iloc[-1] if len(prev_s) else s.iloc[0]
        n0 = prev_n.iloc[-1] if len(prev_n) else n.iloc[0]
        print(f"  {y}: strategy {s.iloc[-1] / s0 - 1:+.1%}   Nifty {n.iloc[-1] / n0 - 1:+.1%}")


if __name__ == "__main__":
    main()
