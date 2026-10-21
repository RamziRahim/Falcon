"""
===============================================================================
Falcon AI Swing Trading Platform — Mark-to-Market Portfolio Ledger
===============================================================================
Script      : mtm_portfolio.py
Package     : Backtesting

A cash-and-positions ledger, revalued every trading day, for judging a
backtest honestly. Added 2026-10-20 alongside (not replacing) the older
portfolio_simulator.simulate_portfolio(), which stays as-is so earlier
results remain reproducible. Three differences from that simulator:

1. Daily mark-to-market. The old equity curve only moves when a trade
   closes, so a position that sinks 8% and then recovers never shows up as
   a drawdown. Run #4's recorded trades: exit-only max drawdown -2.1%,
   daily mark-to-market -3.7%.

2. Gross exposure cap. Position size is risk / stop distance, so a tight
   stop means a large position; five of them can exceed the account. Sizes
   are scaled down to fit max_gross_exposure (default 100%, i.e. no
   leverage), and a signal is skipped if less than MIN_POSITION_FRACTION
   of the account is left.

3. Liquidity-aware costs. A flat 0.3% round trip treats a Rs 2 crore/day
   small-cap like a Rs 2,000 crore/day large-cap. Costs here are statutory
   charges plus a spread/slippage tier by the stock's 20-day average traded
   value, plus a market-impact term when the order is a meaningful share
   of that volume. All assumptions are in CostModel and easy to change.

Prices: each trade's path is revalued at daily closes between the signal
date and the exit date, then the final day is adjusted so the trade's total
gross move equals the episode's recorded gross_return_pct (which already
reflects the fill model and intraday stop/target exits). Costs are then
charged on top of that at entry and exit.
===============================================================================
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

RiskPolicy = Callable[[pd.Series], float]

MIN_POSITION_FRACTION = 0.02
ADV_WINDOW = 20


@dataclass
class CostModel:
    """Per-side costs as fractions of traded value (0.001 = 0.1%).

    statutory: STT on delivery (0.1% each side) plus exchange, SEBI, stamp
    duty and GST -- roughly 0.12-0.13% per side for delivery trades with a
    zero-brokerage broker.
    spread_tiers: (minimum 20-day average traded value in rupees, cost) --
    the first tier whose minimum the stock clears applies.
    impact_coeff: extra cost = impact_coeff * sqrt(order value / ADV value),
    a standard square-root impact shape; negligible for small orders,
    meaningful once an order is a few percent of a day's volume.
    """
    statutory: float = 0.00125
    spread_tiers: tuple = (
        (1_000_000_000, 0.0003),   # >= Rs 100 cr/day
        (200_000_000, 0.0008),     # Rs 20-100 cr
        (50_000_000, 0.0020),      # Rs 5-20 cr
        (0, 0.0050),               # < Rs 5 cr
    )
    impact_coeff: float = 0.01

    def per_side(self, order_value: float, adv_value: float | None) -> float:
        if adv_value is None or not np.isfinite(adv_value) or adv_value <= 0:
            spread = self.spread_tiers[-1][1]
            impact = 0.0
        else:
            spread = next(cost for minimum, cost in self.spread_tiers if adv_value >= minimum)
            impact = self.impact_coeff * np.sqrt(max(order_value, 0.0) / adv_value)
        return self.statutory + spread + impact


@dataclass
class _Position:
    ticker: str
    value: float
    exit_date: pd.Timestamp
    path: pd.Series          # daily returns to apply after entry, indexed by date
    adv_value: float | None
    entry_cost: float
    record: dict = field(default_factory=dict)


@dataclass
class MtmResult:
    equity_curve: pd.Series
    gross_exposure: pd.Series
    trades: pd.DataFrame
    summary: dict = field(default_factory=dict)


def _adv_value(history: pd.DataFrame, as_of: pd.Timestamp) -> float | None:
    if "Volume" not in history.columns:
        return None
    window = history[history["Date"] <= as_of].tail(ADV_WINDOW)
    if window.empty:
        return None
    return float((window["Close"] * window["Volume"]).mean())


def _trade_path(history: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, gross_return_pct: float) -> pd.Series:
    """Daily close-to-close returns after the signal date up to the exit
    date, rescaled on the last day so the cumulative move equals the
    recorded gross return."""
    closes = history.set_index("Date")["Close"].sort_index()
    segment = closes[(closes.index >= start) & (closes.index <= end)]
    returns = segment.pct_change().dropna()
    target = 1 + gross_return_pct / 100
    if returns.empty:
        later = closes.index[closes.index > start]
        day = later[0] if len(later) else start
        return pd.Series([target - 1], index=[day])
    realised = float((1 + returns).prod())
    returns.iloc[-1] = (1 + returns.iloc[-1]) * target / realised - 1
    return returns


def simulate_portfolio_mtm(
    episodes: pd.DataFrame,
    policy: RiskPolicy,
    price_histories: dict[str, pd.DataFrame],
    n_slots: int = 5,
    base_risk_pct: float = 1.0,
    starting_capital: float = 1_000_000.0,
    max_gross_exposure: float = 1.0,
    cost_model: CostModel | None = None,
) -> MtmResult:
    """Revalue a cash + positions ledger every trading day.

    episodes: episode_builder output (needs ticker, episode_start_date,
    episode_end_date, gross_return_pct, and r_multiple/net_return_pct or a
    stop_pct column). price_histories: ticker -> DataFrame with Date, Close
    and (for liquidity costs) Volume.
    """
    cost_model = cost_model or CostModel()
    working = episodes.copy()
    working["episode_start_date"] = pd.to_datetime(working["episode_start_date"])
    working["episode_end_date"] = pd.to_datetime(working["episode_end_date"])
    working["risk_fraction"] = working.apply(policy, axis=1)
    if "stop_pct" not in working.columns:
        working["stop_pct"] = working["net_return_pct"] / working["r_multiple"]
    working = working[(working["risk_fraction"] > 0) & (working["stop_pct"] > 0) & working["stop_pct"].notna()]
    working = working[working["ticker"].isin(price_histories.keys())]
    working = working.sort_values("episode_start_date").reset_index(drop=True)

    if working.empty:
        empty = pd.Series(dtype=float)
        return MtmResult(empty, empty, pd.DataFrame(), {"n_taken": 0})

    start = working["episode_start_date"].min()
    end = working["episode_end_date"].max()
    all_dates = sorted({d for h in price_histories.values() for d in h["Date"] if start <= d <= end})
    by_start = {d: g for d, g in working.groupby("episode_start_date")}

    cash = starting_capital
    open_positions: list[_Position] = []
    equity_rows, exposure_rows, trade_rows = [], [], []
    missed_slots = missed_exposure = scaled_down = 0

    for day in all_dates:
        # 1. revalue open positions with today's move
        for pos in open_positions:
            if day in pos.path.index:
                pos.value *= 1 + float(pos.path.loc[day])

        # 2. close positions whose exit is today
        still_open = []
        for pos in open_positions:
            if day >= pos.exit_date:
                exit_cost = pos.value * cost_model.per_side(pos.value, pos.adv_value)
                cash += pos.value - exit_cost
                pos.record["exit_cost"] = exit_cost
            else:
                still_open.append(pos)
        open_positions = still_open

        equity = cash + sum(p.value for p in open_positions)

        # 3. open new positions signalled at today's close
        for _, ep in by_start.get(day, pd.DataFrame()).iterrows():
            if len(open_positions) >= n_slots:
                missed_slots += 1
                continue
            history = price_histories[ep["ticker"]]
            wanted = (base_risk_pct / 100) * ep["risk_fraction"] / (ep["stop_pct"] / 100)
            used = sum(p.value for p in open_positions) / equity if equity > 0 else 1.0
            room = max_gross_exposure - used
            if room < MIN_POSITION_FRACTION:
                missed_exposure += 1
                continue
            fraction = min(wanted, room)
            scaled_down += fraction < wanted
            value = fraction * equity
            adv = _adv_value(history, day)
            entry_cost = value * cost_model.per_side(value, adv)
            path = _trade_path(history, day, ep["episode_end_date"], ep["gross_return_pct"])
            record = {
                "ticker": ep["ticker"], "entry_signal_date": day,
                "exit_date": ep["episode_end_date"], "fraction_of_equity": fraction,
                "wanted_fraction": wanted, "gross_return_pct": ep["gross_return_pct"],
                "adv_value": adv, "participation_pct": (value / adv * 100) if adv else None,
                "position_value": value, "entry_cost": entry_cost, "exit_cost": None,
            }
            trade_rows.append(record)
            open_positions.append(_Position(ep["ticker"], value - entry_cost, ep["episode_end_date"], path, adv, entry_cost, record))
            cash -= value

        equity = cash + sum(p.value for p in open_positions)
        equity_rows.append((day, equity))
        exposure_rows.append((day, sum(p.value for p in open_positions) / equity if equity > 0 else 0.0))

    equity_curve = pd.Series(dict(equity_rows)).sort_index()
    gross_exposure = pd.Series(dict(exposure_rows)).sort_index()
    trades = pd.DataFrame(trade_rows) if trade_rows else pd.DataFrame()

    total_return = (equity_curve.iloc[-1] / starting_capital - 1) * 100
    drawdown = (equity_curve / equity_curve.cummax() - 1).min() * 100
    years = max((equity_curve.index[-1] - equity_curve.index[0]).days / 365.25, 1e-9)
    cagr = ((equity_curve.iloc[-1] / starting_capital) ** (1 / years) - 1) * 100
    total_costs = float(trades["entry_cost"].sum() + trades["exit_cost"].fillna(0).sum()) if not trades.empty else 0.0

    summary = {
        "total_return_pct": round(total_return, 2),
        "max_drawdown_pct": round(drawdown, 2),
        "cagr_pct": round(cagr, 2),
        "calmar": round(cagr / abs(drawdown), 2) if drawdown < 0 else None,
        "n_taken": len(trades),
        "n_missed_slots": missed_slots,
        "n_missed_exposure_cap": missed_exposure,
        "n_scaled_down_by_cap": int(scaled_down),
        "avg_gross_exposure_pct": round(gross_exposure.mean() * 100, 1),
        "max_gross_exposure_pct": round(gross_exposure.max() * 100, 1),
        "total_costs_pct_of_start": round(total_costs / starting_capital * 100, 2),
        "max_participation_pct": round(trades["participation_pct"].max(), 3) if not trades.empty and trades["participation_pct"].notna().any() else None,
    }
    return MtmResult(equity_curve, gross_exposure, trades, summary)
