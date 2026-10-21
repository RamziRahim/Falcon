"""
Falcon -- pre-registered backtest scorecard (written 2026-10-20, BEFORE run #5 results).

Run from the project root:
    python tests/evaluate_backtest_run.py data/backtest_results_run5_honest_fills.csv

The verdict rules below were fixed before run #5 finished and must not be
edited after seeing its results (see docs/run5_preregistration.md). The
script reports every number; the verdict is mechanical.

Scorecard (EXECUTE-only, the same policy as run #4's headline):
  * daily mark-to-market ledger (backtesting/mtm_portfolio.py): 5 slots,
    1% risk per trade, gross exposure capped at 100%, liquidity-aware costs
  * same-window benchmarks: Nifty buy-and-hold, equal-weight universe,
    top-20% 12-1 momentum basket (the last two share the backtest's
    universe and its survivorship bias)
  * factor regression of daily returns on market, size and momentum
  * per-trade statistics, profit concentration, and first-half vs
    second-half of the window
"""
import sys
sys.path.insert(0, ".")

import glob
import os
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from backtesting.episode_builder import build_episodes
from backtesting.mtm_portfolio import simulate_portfolio_mtm
from backtesting.portfolio_simulator import policy_hard_cap
from market_data.price_integrity import SERIES_FLIP, classify_price_series

# ---- pre-registered thresholds (do not change after results) -------------
MIN_EXCESS_VS_NIFTY_PP = 10.0      # total return must beat Nifty by >= 10 points
MIN_TRADE_T = 2.0                  # mean net return per taken trade, t-stat
MIN_ALPHA_T = 2.0                  # daily alpha vs market+size+momentum, HAC t-stat
MAX_TOP3_SHARE = 0.50              # top 3 trades < 50% of total profit
MIN_ACHIEVABLE_FILL_SHARE = 0.99   # >= 99% of taken entries inside the day's traded range
FILL_TOLERANCE = 0.005             # 0.5% slack for rounding/adjustment noise
# both halves of the window must be profitable after costs


def _load_prices(folder="data/technical"):
    prices = {}
    for path in glob.glob(os.path.join(folder, "*.parquet")):
        ticker = os.path.basename(path)[:-8]
        df = pd.read_parquet(path, columns=["Date", "Open", "High", "Low", "Close", "Volume"])
        df["Date"] = pd.to_datetime(df["Date"])
        if df["Date"].dt.tz is not None:
            df["Date"] = df["Date"].dt.tz_localize(None)
        df = df.sort_values("Date").drop_duplicates("Date").reset_index(drop=True)
        if len(df) >= 30 and classify_price_series(ticker, df).status != SERIES_FLIP:
            prices[ticker] = df
    return prices


def _nifty(path="data/raw/^NSEI.parquet"):
    n = pd.read_parquet(path)
    n["Date"] = pd.to_datetime(n["Date"])
    if n["Date"].dt.tz is not None:
        n["Date"] = n["Date"].dt.tz_localize(None)
    return n.set_index("Date")["Close"].sort_index()


def _factors(prices, nifty, days):
    closes = pd.DataFrame({t: h.set_index("Date")["Close"] for t, h in prices.items()}).sort_index()
    rets = closes.pct_change(fill_method=None)
    rets = rets.mask(rets.abs() > 0.4)                  # no >40% days without a corporate action
    ew = rets.reindex(days).mean(axis=1)
    mom, holding, prev = [], None, None
    for d in days:
        if holding is None or d.month != prev.month:
            past = closes.loc[:d]
            if len(past) > 260:
                m = (past.iloc[-22] / past.iloc[-253] - 1).dropna()
                holding = m[m >= m.quantile(0.8)].index
        prev = d
        mom.append(rets.loc[d, holding].mean() if holding is not None else np.nan)
    mkt = nifty.pct_change().reindex(days)
    return pd.DataFrame({"MKT": mkt, "SIZE": ew - mkt, "MOM": pd.Series(mom, index=days) - ew}), ew, pd.Series(mom, index=days)


def evaluate(raw_path: str) -> dict:
    raw = pd.read_csv(raw_path, low_memory=False)
    for col in ("entry_date", "exit_date"):
        raw[col] = pd.to_datetime(raw[col], format="mixed")
    episodes = build_episodes(raw)
    prices = _load_prices()
    nifty = _nifty()

    result = simulate_portfolio_mtm(episodes, policy_hard_cap, prices)
    eq, s, trades = result.equity_curve, result.summary, result.trades
    days = eq.index
    daily = eq.pct_change().fillna(0.0)

    factors, ew, mom = _factors(prices, nifty, days)
    tot = lambda r: ((1 + r.fillna(0)).prod() - 1) * 100
    nifty_ret = tot(nifty.pct_change().reindex(days))

    import statsmodels.api as sm
    X = factors.dropna()
    model = sm.OLS(daily.reindex(X.index), sm.add_constant(X)).fit(cov_type="HAC", cov_kwds={"maxlags": 5})

    trade_net = (
        trades["gross_return_pct"]
        - (trades["entry_cost"] + trades["exit_cost"].fillna(0)) / trades["position_value"] * 100
    ) if not trades.empty else pd.Series(dtype=float)
    # rupee P&L per trade for concentration
    pnl = trades["fraction_of_equity"] * trades["gross_return_pct"] / 100 if not trades.empty else pd.Series(dtype=float)
    profit = pnl[pnl > 0].sort_values(ascending=False)
    top3_share = float(profit.head(3).sum() / pnl.sum()) if pnl.sum() > 0 else float("inf")
    t_trade = trade_net.mean() / (trade_net.std() / np.sqrt(len(trade_net))) if len(trade_net) > 1 else float("nan")

    # Fill realism: the recorded entry must be a price that actually traded.
    # Signals are known at the signal-day close, so the fill day is the next
    # trading day (run #5 onwards); the signal day itself is also accepted so
    # older runs are judged generously. Run #4 fails this check.
    taken_keys = set(zip(trades["ticker"], pd.to_datetime(trades["entry_signal_date"]))) if not trades.empty else set()
    founders = raw[[(t, d) in taken_keys for t, d in zip(raw["ticker"], raw["entry_date"])]]
    achievable = []
    for _, row in founders.iterrows():
        h = prices.get(row["ticker"])
        if h is None:
            continue
        idx = h.index[h["Date"] == row["entry_date"]]
        if len(idx) == 0:
            continue
        bars = h.iloc[idx[0]: idx[0] + 2]
        ok = ((bars["Low"] * (1 - FILL_TOLERANCE) <= row["entry_price"]) &
              (row["entry_price"] <= bars["High"] * (1 + FILL_TOLERANCE))).any()
        achievable.append(bool(ok))
    achievable_share = float(np.mean(achievable)) if achievable else float("nan")

    mid = days[len(days) // 2]
    halves = {
        "first_half_return_pct": round((eq.loc[:mid].iloc[-1] / eq.iloc[0] - 1) * 100, 2),
        "second_half_return_pct": round((eq.iloc[-1] / eq.loc[:mid].iloc[-1] - 1) * 100, 2),
    }

    checks = {
        "beats Nifty by >= 10 points": s["total_return_pct"] - nifty_ret >= MIN_EXCESS_VS_NIFTY_PP,
        "mean net per trade t >= 2": bool(t_trade >= MIN_TRADE_T),
        "factor alpha t >= 2": bool(model.tvalues["const"] >= MIN_ALPHA_T),
        "top-3 trades < 50% of profit": top3_share < MAX_TOP3_SHARE,
        "both halves profitable": halves["first_half_return_pct"] > 0 and halves["second_half_return_pct"] > 0,
        "entries are achievable prices (>= 99%)": bool(achievable_share >= MIN_ACHIEVABLE_FILL_SHARE),
    }
    report = {
        **s, **halves,
        "nifty_return_pct": round(nifty_ret, 2), "ew_universe_return_pct": round(tot(ew), 2),
        "momentum_basket_return_pct": round(tot(mom), 2),
        "alpha_pct_per_year": round(model.params["const"] * 252 * 100, 2), "alpha_t": round(model.tvalues["const"], 2),
        "beta_mkt": round(model.params["MKT"], 2), "beta_size": round(model.params["SIZE"], 2), "beta_mom": round(model.params["MOM"], 2),
        "mean_net_per_trade_pct": round(trade_net.mean(), 2) if len(trade_net) else None,
        "trade_t": round(t_trade, 2), "win_rate_pct": round((trade_net > 0).mean() * 100, 1) if len(trade_net) else None,
        "top3_profit_share": round(top3_share, 2),
        "achievable_fill_share": round(achievable_share, 3),
        "checks": checks,
        "verdict": "EDGE DEMONSTRATED (in-sample; still needs paper trading)" if all(checks.values()) else "NO DEMONSTRATED EDGE",
    }
    return report


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/backtest_results_run5_honest_fills.csv"
    report = evaluate(path)
    print(f"\nScorecard for {path}\n" + "=" * 70)
    for key, value in report.items():
        if key != "checks":
            print(f"{key:32s} {value}")
    print("\nPre-registered checks:")
    for name, ok in report["checks"].items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
