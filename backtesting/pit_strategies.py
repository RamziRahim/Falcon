"""
===============================================================================
Falcon AI Swing Trading Platform — Redesign Strategies on Point-in-Time Data
===============================================================================
Script      : pit_strategies.py
Package     : Backtesting

Implements exactly the two strategies and the judgement in
docs/redesign_preregistration.md, on the survivorship-free data built by
market_data/pit_universe.py. Nothing here is tuned. Every number below
comes from that document.

Both strategies run on one daily cash + positions ledger:
  * trades fill at a session's OPEN (signals are known at a close);
  * positions are marked at each close (last known close if a stock skips a
    day);
  * costs come from mtm_portfolio.CostModel, using the stock's 20-session
    average traded value;
  * a stock that stops trading is sold at its last close minus
    DELIST_HAIRCUT on the first session after its last trading day.
===============================================================================
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from backtesting.mtm_portfolio import CostModel

DELIST_HAIRCUT = 0.05
START_CAPITAL = 1_000_000.0

# Strategy A
MOM_LOOKBACK, MOM_SKIP, MOM_HOLD = 252, 21, 20
# Strategy B
BO_HIGH_LOOKBACK, BO_VOL_MULT, BO_VOL_LEN = 252, 1.5, 50
BO_SMA_FAST, BO_SMA_SLOW, BO_ATR_LEN, BO_ATR_MULT = 50, 200, 14, 2.0
BO_MAX_GAP, BO_TIME_STOP, BO_RISK, BO_SLOTS = 0.05, 60, 0.01, 10
# Strategy C (dated addendum, docs/redesign_preregistration.md)
PB_MOM_LEN, PB_MOM_TOP = 126, 0.30
PB_DIP_LEN, PB_DIP = 3, -0.03
PB_SMA_SHORT, PB_SMA_FAST, PB_SMA_SLOW = 10, 50, 200
PB_ATR_LEN, PB_ATR_MULT, PB_REWARD_MULT = 14, 2.0, 2.0
PB_TIME_STOP, PB_RISK, PB_SLOTS = 20, 0.01, 10
PB_MIN_TURNOVER = 2e8                    # Rs 20 crore median daily traded value (20 sessions)
PB_MARKET_SMA = 200
# Strategy MR (docs/mean_reversion_preregistration.md)
MR_RSI_LEN, MR_RSI_MAX, MR_TREND_SMA, MR_EXIT_SMA = 2, 5.0, 200, 5
MR_TIME_STOP, MR_POSITION, MR_SLOTS, MR_MARKET_SMA = 10, 0.10, 10, 200


@dataclass
class Panel:
    """Wide Date x entity frames plus the monthly universe."""
    open: pd.DataFrame
    high: pd.DataFrame
    low: pd.DataFrame
    close: pd.DataFrame
    volume: pd.DataFrame
    turnover: pd.DataFrame
    universe: dict                       # month_end Timestamp -> set(entity_id)
    last_date: pd.Series                 # entity_id -> last trading date
    symbol: pd.Series                    # entity_id -> current symbol

    @property
    def sessions(self) -> pd.DatetimeIndex:
        return self.close.index

    def universe_on(self, day: pd.Timestamp) -> set:
        ends = [m for m in self.universe if m <= day]
        return self.universe[max(ends)] if ends else set()


def make_panel(prices: pd.DataFrame, universe: pd.DataFrame) -> Panel:
    # Only stocks that are ever in the given universe can be traded or held,
    # so the wide frames are limited to them (memory: ~1,600 of ~4,600
    # entities over 2007-2026; results are unchanged).
    prices = prices[prices["entity_id"].isin(set(universe["entity_id"]))]
    wide = {c: prices.pivot_table(index="Date", columns="entity_id", values=c, aggfunc="first")
            for c in ("Open", "High", "Low", "Close", "Volume", "Turnover")}
    uni = {pd.Timestamp(m): set(g["entity_id"]) for m, g in universe.groupby("month_end")}
    return Panel(wide["Open"], wide["High"], wide["Low"], wide["Close"], wide["Volume"], wide["Turnover"], uni,
                 prices.groupby("entity_id")["Date"].max(),
                 prices.sort_values("Date").groupby("entity_id")["current_symbol"].last())


@dataclass
class Ledger:
    cost: CostModel
    cash: float = START_CAPITAL
    shares: dict = field(default_factory=dict)          # entity -> shares
    meta: dict = field(default_factory=dict)            # entity -> per-position info
    trades: list = field(default_factory=list)          # closed positions
    equity: list = field(default_factory=list)          # (date, equity, gross exposure)

    def value(self, entity, marks) -> float:
        px = marks.get(entity, np.nan)
        return self.shares[entity] * (px if np.isfinite(px) else self.meta[entity]["last_mark"])

    def buy(self, day, entity, price, value, adv, extra=None):
        if value <= 0 or not np.isfinite(price) or price <= 0:
            return False
        cost = value * self.cost.per_side(value, adv)
        if value + cost > self.cash:
            value = max(self.cash / (1 + self.cost.per_side(value, adv)), 0.0)
            cost = value * self.cost.per_side(value, adv)
        if value <= 0:
            return False
        self.cash -= value + cost
        self.shares[entity] = self.shares.get(entity, 0.0) + value / price
        info = self.meta.setdefault(entity, {"entry_date": day, "cost_basis": 0.0, "costs": 0.0, "last_mark": price})
        info["cost_basis"] += value
        info["costs"] += cost
        if extra:
            info.update(extra)
        return True

    def sell(self, day, entity, price, adv, reason):
        qty = self.shares.pop(entity)
        info = self.meta.pop(entity)
        proceeds = qty * price
        cost = proceeds * self.cost.per_side(proceeds, adv)
        self.cash += proceeds - cost
        proceeds += info.get("trim_proceeds", 0.0)       # earlier trims of this position (0 unless trim() was used)
        self.trades.append({"entity_id": entity, "entry_date": info["entry_date"], "exit_date": day,
                            "cost_basis": info["cost_basis"], "proceeds": proceeds,
                            "pnl": proceeds - cost - info["cost_basis"] - info["costs"], "exit_reason": reason})

    def trim(self, entity, price, value, adv):
        """Sell `value` worth of a holding without closing it; the cash flow and cost are
        folded into the position's single trade record (docs/a_exposure_preregistration.md)."""
        qty = min(value / price, self.shares[entity])
        proceeds = qty * price
        cost = proceeds * self.cost.per_side(proceeds, adv)
        self.cash += proceeds - cost
        self.shares[entity] -= qty
        info = self.meta[entity]
        info["costs"] += cost
        info["trim_proceeds"] = info.get("trim_proceeds", 0.0) + proceeds

    def mark(self, day, closes):
        for e in self.shares:
            px = closes.get(e, np.nan)
            if np.isfinite(px):
                self.meta[e]["last_mark"] = px
        held = sum(self.shares[e] * self.meta[e]["last_mark"] for e in self.shares)
        eq = self.cash + held
        self.equity.append((day, eq, held / eq if eq > 0 else 0.0))
        return eq


def _adv(panel: Panel, day_idx: int, entity) -> float | None:
    window = panel.turnover[entity].iloc[max(0, day_idx - 20): day_idx]
    v = window.mean()
    return float(v) if np.isfinite(v) else None


def _delisting_exits(panel, ledger, day_idx, day):
    for e in list(ledger.shares):
        last = panel.last_date.get(e)
        if last is not None and last < day:
            ledger.sell(day, e, ledger.meta[e]["last_mark"] * (1 - DELIST_HAIRCUT), _adv(panel, day_idx, e), "DELISTED")


def run_momentum(panel: Panel, start: pd.Timestamp, end: pd.Timestamp, cost: CostModel | None = None,
                 stop_pct: float | None = None, hold: int = MOM_HOLD,
                 gauge_up=None, down_level: float = 1.0, stats: dict | None = None,
                 skip_after_stop: bool = False, score: str = "raw",
                 support: pd.DataFrame | None = None, support_fallback: str = "BA",
                 add_frac: float | None = None, add_level: pd.DataFrame | None = None, add_fallback: bool = True,
                 review: str = "month", lookback: int | None = None, skip: int | None = None, buffer: int | None = None,
                 allowed: pd.DataFrame | None = None, stop_mode: str = "pct", pwl: pd.DataFrame | None = None,
                 target_r: float | None = None, half_at_r: float | None = None, half_be: bool = False,
                 trail_step: float | None = None):
    """half_at_r / half_be / trail_step (docs/momentum_tight_stops_preregistration.md): when the
    high reaches buy + half_at_r x (buy - stop), sell half there (or at the open if it gaps above,
    after the buy day); stops are checked first. half_be: from the next session the rest's stop
    is the buy price. trail_step: after the half, once the high reaches that 1:1 level + k x
    trail_step x buy, the stop is buy x (1 + k x trail_step), live from the next session; stops
    never move down. Defaults = unchanged behaviour.

    allowed / stop_mode / pwl / target_r (docs/momentum_sector_exits_preregistration.md):
    allowed = boolean frame (sessions x entities); at a review only allowed stocks are ranked.
    stop_mode="pwl": the stop is the previous calendar week's low (pwl frame, sessions x
    entities), unless it is >= the fill or more than 15% below it (then fill x (1 - stop_pct)).
    target_r: sell when the high reaches fill + target_r x (fill - stop), at the target (or the
    open if it gaps above, after the fill day); stops are checked first. Defaults = unchanged.

    review / lookback / skip / buffer (docs/weekly_momentum_preregistration.md): review="week"
    ranks at the close of the last session of each calendar week (else month); the score is
    close[t-skip] / close[t-lookback] - 1 (defaults MOM_SKIP, MOM_LOOKBACK = A10's 12-1);
    buffer=N keeps a holding while it ranks in the top N and fills free places from the top of
    the list. Defaults = unchanged behaviour. All order/stop/support/add logic is the same at a
    weekly review as at a monthly one ("next rebalance" = the next weekly review).

    add_frac / add_level / add_fallback (docs/pullback_two_ways_preregistration.md, A10P): a new
    name gets add_frac of its slot at the rebalance open (stop = 10% below that fill, for the
    whole position); the rest is a limit add at add_level (sessions x entities), active from the
    next session while the position is held, filled at min(open, level) when the low reaches it.
    At the next rebalance an unfilled add on a name still held is bought at the open
    (add_fallback=True) or left working (False). Sold or stopped = add cancelled. None (default)
    = unchanged behaviour.

    support / support_fallback (docs/momentum_weekly_support_preregistration.md): support is
    a DataFrame (sessions x entities) of weekly support levels (backtesting.weekly_support).
    A new top-list name is not bought at the rebalance open: it gets a limit order at its
    level, active from that open until the next rebalance; it fills in a session whose low
    is at or below the level, at min(open, level); no level that session = no order that
    session. Stop = fill x (1 - stop_pct). At the next rebalance an unfilled name still in the
    list is bought at the open ("BA") or gets a fresh order ("CASH"); otherwise cancelled.
    None (default) = unchanged behaviour.

    score (docs/a_volrank_preregistration.md): "raw" = 12-1 return (unchanged);
    "vol" = 12-1 return / annualised 252-session volatility; "z" = mean of the z-scores of
    (6-1 return / vol) and (12-1 return / vol) across the list.

    skip_after_stop (docs/a_stop_width_preregistration.md, A10C): a stock stopped since
    the previous rebalance is not bought at the next one; nothing replaces it.

    gauge_up / down_level (docs/a_exposure_preregistration.md): gauge_up is a boolean
    array over panel.sessions. At each month-end close the exposure level is 1.0 if the
    gauge is up, else down_level; slots are equity x level / hold. When the level changes,
    survivors are set to exactly the new slot at the rebalance open (after the leavers are
    sold, before the new names are bought). gauge_up=None = unchanged behaviour.

    stop_pct (docs/a_stop_preregistration.md): sell a holding whose low reaches
    fill x (1 - stop_pct) -- at the stop, or at the open if it gaps through after the
    fill day. It is not re-bought before the next month-end rebalance. None = test A as frozen."""
    ledger = Ledger(cost or CostModel())
    sessions = panel.sessions
    closes_ff = panel.close.ffill(limit=5)
    pending_target = None
    level, pending_level = 1.0, 1.0
    vol_df = None
    if score != "raw":
        vol_df = closes_ff.pct_change(fill_method=None).rolling(252, min_periods=200).std() * np.sqrt(252)
    stopped = set()
    sup_orders = {}                                   # entity -> {"from": i, "open0": first-session open}
    adds = {}                                         # A10P: entity -> {"value", "from", "first"}
    if add_frac is not None:
        assert support is None and add_level is not None and stop_pct is not None
        alv = add_level.reindex(columns=panel.close.columns).to_numpy(float)
        acol = {e: j for j, e in enumerate(panel.close.columns)}
        ast = stats if stats is not None else {}
        for k in ("adds_total", "adds_support", "adds_fallback", "adds_cancelled", "cash_share_sum", "cash_share_n"):
            ast.setdefault(k, 0)
        ast.setdefault("add_vs_first", [])
    if support is not None:
        assert support_fallback in ("BA", "CASH")
        sup = support.reindex(columns=panel.close.columns).to_numpy(float)
        scol = {e: j for j, e in enumerate(panel.close.columns)}
        sst = stats if stats is not None else {}
        for k in ("orders", "filled_support", "fallback_buys", "cancelled", "cash_share_sum", "cash_share_n"):
            sst.setdefault(k, 0)
        sst.setdefault("days_to_fill", [])
        sst.setdefault("entry_vs_open0", [])
        sst.setdefault("fallback_vs_open0", [])
    for i, day in enumerate(sessions):
        if day < start or day > end:
            continue
        _delisting_exits(panel, ledger, i, day)
        opens = panel.open.iloc[i]
        if pending_target is not None and support is not None:
            for e in [e for e in ledger.shares if e not in pending_target]:
                if np.isfinite(opens.get(e, np.nan)):
                    ledger.sell(day, e, opens[e], _adv(panel, i, e), "REBALANCE")
            carried = {e: od for e, od in sup_orders.items() if e in pending_target and e not in ledger.shares}
            sst["cancelled"] += len(sup_orders) - len(carried)
            sup_orders = {}
            fb = []
            if support_fallback == "BA":
                fb = [e for e in carried if np.isfinite(opens.get(e, np.nan))]
            else:
                sup_orders.update({e: {"from": i, "open0": opens.get(e, np.nan)} for e in carried})
                sst["orders"] += len(carried)
            equity_now = ledger.cash + sum(ledger.value(e, opens) for e in ledger.shares)
            per_name = min(equity_now * level / hold, ledger.cash / max(len(fb), 1) * 0.995)
            for e in fb:
                if ledger.buy(day, e, opens[e], per_name, _adv(panel, i, e), {"stop": opens[e] * (1 - stop_pct), "entry_idx": i}):
                    sst["fallback_buys"] += 1
                    o0 = carried[e]["open0"]
                    if np.isfinite(o0) and o0 > 0:
                        sst.setdefault("fallback_vs_open0", []).append(opens[e] / o0 - 1)
            for e in pending_target:
                if e not in ledger.shares and e not in sup_orders and e not in carried:
                    sup_orders[e] = {"from": i, "open0": opens.get(e, np.nan)}
                    sst["orders"] += 1
            pending_target = None
        if support is not None and sup_orders:
            lows_ = panel.low.iloc[i]
            fills = []
            for e, od in list(sup_orders.items()):
                lv, o, lo = sup[i, scol[e]], opens.get(e, np.nan), lows_.get(e, np.nan)
                if not (np.isfinite(lv) and np.isfinite(o) and np.isfinite(lo)) or lo > lv:
                    continue
                fills.append((e, min(o, lv)))
            if fills:
                equity_now = ledger.cash + sum(ledger.value(x, opens) for x in ledger.shares)
                per_name = min(equity_now * level / hold, ledger.cash / len(fills) * 0.995)
                for e, px in fills:
                    od = sup_orders.pop(e)
                    if ledger.buy(day, e, px, per_name, _adv(panel, i, e), {"stop": px * (1 - stop_pct), "entry_idx": i}):
                        sst["filled_support"] += 1
                        sst["days_to_fill"].append(i - od["from"])
                        if np.isfinite(od["open0"]) and od["open0"] > 0:
                            sst["entry_vs_open0"].append(px / od["open0"] - 1)
        if pending_target is not None:
            for e in [e for e in ledger.shares if e not in pending_target]:
                if np.isfinite(opens.get(e, np.nan)):
                    ledger.sell(day, e, opens[e], _adv(panel, i, e), "REBALANCE")
            if add_frac is not None:
                for e in [e for e in adds if e not in ledger.shares]:
                    adds.pop(e)
                    ast["adds_cancelled"] += 1
                if add_fallback:
                    for e in [e for e in adds if np.isfinite(opens.get(e, np.nan))]:
                        od = adds.pop(e)
                        if ledger.buy(day, e, opens[e], min(od["value"], ledger.cash * 0.995), _adv(panel, i, e)):
                            ast["adds_fallback"] += 1
                            ast["add_vs_first"].append(opens[e] / od["first"] - 1)
            if gauge_up is not None and pending_level != level:
                equity_now = ledger.cash + sum(ledger.value(e, opens) for e in ledger.shares)
                slot = equity_now * pending_level / hold
                held = [e for e in ledger.shares if np.isfinite(opens.get(e, np.nan))]
                for e in held:                                   # trims first, so top-ups have cash
                    if pending_level == 0:
                        ledger.sell(day, e, opens[e], _adv(panel, i, e), "EXPOSURE")
                    elif ledger.value(e, opens) > slot:
                        ledger.trim(e, opens[e], ledger.value(e, opens) - slot, _adv(panel, i, e))
                for e in held:
                    if e in ledger.shares and ledger.value(e, opens) < slot:
                        ledger.buy(day, e, opens[e], slot - ledger.value(e, opens), _adv(panel, i, e))
                level = pending_level
                if stats is not None:
                    stats["level_changes"] = stats.get("level_changes", 0) + 1
            new = [e for e in pending_target if e not in ledger.shares and np.isfinite(opens.get(e, np.nan))]
            if skip_after_stop:
                new = [e for e in new if e not in stopped]
                stopped = set()
            equity_now = ledger.cash + sum(ledger.value(e, opens) for e in ledger.shares)
            # equal slots of equity/MOM_HOLD, limited by the cash on hand
            # (split evenly across the new names before any is bought)
            per_name = min(equity_now * level / hold, ledger.cash / max(len(new), 1) * 0.995)
            for e in new:
                first = per_name if add_frac is None else per_name * add_frac
                meta_e = None
                if stop_pct is not None:
                    stp = opens[e] * (1 - stop_pct)
                    if stop_mode == "pwl":
                        lw = pwl.iloc[i].get(e, np.nan)
                        if np.isfinite(lw) and lw < opens[e] and (opens[e] - lw) / opens[e] <= 0.15:
                            stp = lw
                        elif stats is not None:
                            stats["pwl_fallback"] = stats.get("pwl_fallback", 0) + 1
                    meta_e = {"stop": stp, "entry_idx": i, "entry_px": opens[e]}
                    if half_at_r is not None:
                        meta_e["half_level"] = opens[e] + half_at_r * (opens[e] - stp)
                    if target_r is not None:
                        meta_e["target"] = opens[e] + target_r * (opens[e] - stp)
                ok = ledger.buy(day, e, opens[e], first, _adv(panel, i, e), meta_e)
                if ok and add_frac is not None and add_frac < 1:
                    adds[e] = {"value": per_name * (1 - add_frac), "from": i + 1, "first": opens[e]}
                    ast["adds_total"] += 1
            pending_target = None
        if add_frac is not None and adds:
            lows_ = panel.low.iloc[i]
            for e in list(adds):
                od = adds[e]
                if od["from"] > i or e not in ledger.shares:
                    continue
                lv, o, lo = alv[i, acol[e]], opens.get(e, np.nan), lows_.get(e, np.nan)
                if np.isfinite(lv) and np.isfinite(o) and np.isfinite(lo) and lo <= lv:
                    px = min(o, lv)
                    if ledger.buy(day, e, px, min(od["value"], ledger.cash * 0.995), _adv(panel, i, e)):
                        adds.pop(e)
                        ast["adds_support"] += 1
                        ast["add_vs_first"].append(px / od["first"] - 1)
        if stop_pct is not None:
            lows = panel.low.iloc[i]
            if half_at_r is not None:                    # stop raises decided on earlier sessions go live today
                for e in ledger.shares:
                    m = ledger.meta.get(e) or {}
                    if m.get("pending_stop") is not None and m.get("pending_from", i + 1) <= i:
                        m["stop"] = max(m["stop"], m.pop("pending_stop"))
                        m.pop("pending_from", None)
            for e in list(ledger.shares):
                m = ledger.meta.get(e) or {}
                st, lo, o = m.get("stop"), lows.get(e, np.nan), opens.get(e, np.nan)
                if st is not None and np.isfinite(lo) and lo <= st:
                    gap = m["entry_idx"] < i and np.isfinite(o) and o < st
                    ledger.sell(day, e, o if gap else st, _adv(panel, i, e), "STOP")
                    stopped.add(e)
            if target_r is not None:
                highs = panel.high.iloc[i]
                for e in list(ledger.shares):
                    m = ledger.meta.get(e) or {}
                    tg, hi, o = m.get("target"), highs.get(e, np.nan), opens.get(e, np.nan)
                    if tg is not None and np.isfinite(hi) and hi >= tg:
                        gap = m["entry_idx"] < i and np.isfinite(o) and o > tg
                        ledger.sell(day, e, o if gap else tg, _adv(panel, i, e), "TARGET")
            if half_at_r is not None:
                highs = panel.high.iloc[i]
                for e in list(ledger.shares):
                    m = ledger.meta.get(e) or {}
                    hl, hi, o, px0 = m.get("half_level"), highs.get(e, np.nan), opens.get(e, np.nan), m.get("entry_px")
                    if hl is None or not np.isfinite(hi):
                        continue
                    new_stop = None
                    if not m.get("half_done") and hi >= hl:
                        px = o if (m["entry_idx"] < i and np.isfinite(o) and o > hl) else hl
                        ledger.trim(e, px, ledger.shares[e] * px / 2, _adv(panel, i, e))
                        m["half_done"] = True
                        if stats is not None:
                            stats["half_exits"] = stats.get("half_exits", 0) + 1
                        if half_be or trail_step is not None:
                            new_stop = px0
                    if m.get("half_done") and trail_step is not None:
                        k = int(np.floor((hi - hl) / (trail_step * px0) + 1e-9))
                        if k >= 1:
                            new_stop = max(new_stop or 0.0, px0 * (1 + k * trail_step))
                    if new_stop is not None and new_stop > max(m["stop"], m.get("pending_stop") or 0.0):
                        m["pending_stop"], m["pending_from"] = new_stop, i + 1
        ledger.mark(day, panel.close.iloc[i])
        if add_frac is not None:
            for e in [e for e in adds if e not in ledger.shares]:
                adds.pop(e)
                ast["adds_cancelled"] += 1
            eq_now = ledger.cash + sum(ledger.value(x, panel.close.iloc[i]) for x in ledger.shares)
            if eq_now > 0:
                ast["cash_share_sum"] += ledger.cash / eq_now
                ast["cash_share_n"] += 1
        if support is not None:
            eq_now = ledger.cash + sum(ledger.value(x, panel.close.iloc[i]) for x in ledger.shares)
            if eq_now > 0:
                sst["cash_share_sum"] += ledger.cash / eq_now
                sst["cash_share_n"] += 1
        if review == "week":
            is_month_end = i + 1 == len(sessions) or (sessions[i + 1].isocalendar()[:2] != day.isocalendar()[:2])
        else:
            is_month_end = i + 1 == len(sessions) or sessions[i + 1].month != day.month
        lb = MOM_LOOKBACK if lookback is None else lookback
        sk = MOM_SKIP if skip is None else skip
        if is_month_end and i >= lb and day < end:
            members = [e for e in panel.universe_on(day) if e in closes_ff.columns]
            if allowed is not None:
                arow = allowed.iloc[i]
                if stats is not None:
                    pb = closes_ff.iloc[i - sk][members] / closes_ff.iloc[i - lb][members] - 1
                    top_all = list(pb.dropna().sort_values(ascending=False).head(hold).index)
                    stats["top_candidates"] = stats.get("top_candidates", 0) + len(top_all)
                    stats["top_rejected_by_sector"] = stats.get("top_rejected_by_sector", 0) + sum(not bool(arow.get(e, False)) for e in top_all)
                members = [e for e in members if bool(arow.get(e, False))]
            past = closes_ff.iloc[i - sk][members]
            base = closes_ff.iloc[i - lb][members]
            mom = (past / base - 1).dropna()
            if score != "raw":
                v = vol_df.iloc[i][members]
                m12 = (past / base - 1) / v
                if score == "vol":
                    mom = m12[np.isfinite(m12) & (v > 0)]
                else:
                    m6 = (past / closes_ff.iloc[i - 126][members] - 1) / v
                    ok = np.isfinite(m6) & np.isfinite(m12) & (v > 0)
                    m6, m12 = m6[ok], m12[ok]
                    mom = ((m6 - m6.mean()) / m6.std() + (m12 - m12.mean()) / m12.std()) / 2
            if buffer is None:
                pending_target = set(mom.sort_values(ascending=False).head(hold).index)
            else:
                ranked = list(mom.sort_values(ascending=False).index)
                keep = [e for e in ranked[:buffer] if e in ledger.shares]
                fill = [e for e in ranked if e not in keep][:max(hold - len(keep), 0)]
                pending_target = set(keep) | set(fill)
            if stats is not None:
                stats.setdefault("targets", {})[i] = pending_target
                if vol_df is not None:
                    stats.setdefault("hold_vol", []).append(float(vol_df.iloc[i][list(pending_target)].mean()))
            if gauge_up is not None:
                pending_level = 1.0 if gauge_up[i] else down_level
                if stats is not None:
                    stats["months"] = stats.get("months", 0) + 1
                    stats["months_down"] = stats.get("months_down", 0) + (0 if gauge_up[i] else 1)
    return _result(ledger)


def breakout_signals(panel: Panel) -> dict:
    c, h, l, v = panel.close, panel.high, panel.low, panel.volume
    prior_high = c.shift(1).rolling(BO_HIGH_LOOKBACK, min_periods=BO_HIGH_LOOKBACK).max()
    vol_avg = v.shift(1).rolling(BO_VOL_LEN, min_periods=BO_VOL_LEN).mean()
    sma_f = c.rolling(BO_SMA_FAST, min_periods=BO_SMA_FAST).mean()
    sma_s = c.rolling(BO_SMA_SLOW, min_periods=BO_SMA_SLOW).mean()
    tr = pd.concat([(h - l), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()]).groupby(level=0).max()
    atr = tr.rolling(BO_ATR_LEN, min_periods=BO_ATR_LEN).mean()
    signal = (c > prior_high) & (v >= BO_VOL_MULT * vol_avg) & (c > sma_f) & (sma_f > sma_s)
    return {"signal": signal, "vol_ratio": v / vol_avg, "sma_fast": sma_f, "atr": atr}


def run_breakout(panel: Panel, start: pd.Timestamp, end: pd.Timestamp, cost: CostModel | None = None):
    ledger = Ledger(cost or CostModel())
    ind = breakout_signals(panel)
    sessions = panel.sessions
    queued_entries, queued_exits = [], {}
    for i, day in enumerate(sessions):
        if day < start or day > end:
            continue
        _delisting_exits(panel, ledger, i, day)
        opens, lows, closes = panel.open.iloc[i], panel.low.iloc[i], panel.close.iloc[i]
        # 1. exits decided at yesterday's close, at today's open
        for e, reason in list(queued_exits.items()):
            if e not in ledger.shares:            # already stopped out / delisted
                queued_exits.pop(e)
                continue
            if np.isfinite(opens.get(e, np.nan)):
                ledger.sell(day, e, opens[e], _adv(panel, i, e), reason)
                queued_exits.pop(e)
        # 2. entries signalled at yesterday's close, at today's open
        for e, signal_close, atr in queued_entries:
            if e in ledger.shares or len(ledger.shares) >= BO_SLOTS:
                continue
            o = opens.get(e, np.nan)
            if not np.isfinite(o) or o >= signal_close * (1 + BO_MAX_GAP):
                continue
            stop = o - BO_ATR_MULT * atr
            if stop <= 0:
                continue
            equity_now = ledger.cash + sum(ledger.value(x, opens) for x in ledger.shares)
            gross = sum(ledger.value(x, opens) for x in ledger.shares)
            wanted = BO_RISK * equity_now / ((o - stop) / o)
            value = min(wanted, max(equity_now - gross, 0.0))
            if value > 0:
                ledger.buy(day, e, o, value, _adv(panel, i, e), {"stop": stop, "entry_idx": i})
        queued_entries = []
        # 3. stops during the day (a gap below the stop fills at the open)
        for e in list(ledger.shares):
            stop, lo, o = ledger.meta[e]["stop"], lows.get(e, np.nan), opens.get(e, np.nan)
            if np.isfinite(lo) and lo <= stop:
                px = o if np.isfinite(o) and o < stop else stop
                ledger.sell(day, e, px, _adv(panel, i, e), "STOP")
        ledger.mark(day, closes)
        if day >= end:
            continue
        # 4. at the close: queue trend / time exits and tomorrow's entries
        for e in ledger.shares:
            sma = ind["sma_fast"].iloc[i].get(e, np.nan)
            if np.isfinite(closes.get(e, np.nan)) and np.isfinite(sma) and closes[e] < sma:
                queued_exits[e] = "TREND_EXIT"
            elif i - ledger.meta[e]["entry_idx"] + 1 >= BO_TIME_STOP:
                queued_exits[e] = "TIME_STOP"
        members = panel.universe_on(day)
        today = ind["signal"].iloc[i]
        hits = [e for e in today[today.fillna(False)].index if e in members and e not in ledger.shares]
        hits.sort(key=lambda e: -ind["vol_ratio"].iloc[i][e])
        queued_entries = [(e, closes[e], ind["atr"].iloc[i][e]) for e in hits if np.isfinite(ind["atr"].iloc[i][e])]
    return _result(ledger)


def pullback_signals(panel: Panel, nifty_close: pd.Series) -> dict:
    c, h, l = panel.close, panel.high, panel.low
    sma_short = c.rolling(PB_SMA_SHORT, min_periods=PB_SMA_SHORT).mean()
    sma_f = c.rolling(PB_SMA_FAST, min_periods=PB_SMA_FAST).mean()
    sma_s = c.rolling(PB_SMA_SLOW, min_periods=PB_SMA_SLOW).mean()
    tr = pd.concat([(h - l), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()]).groupby(level=0).max()
    atr = tr.rolling(PB_ATR_LEN, min_periods=PB_ATR_LEN).mean()
    mom = c / c.shift(PB_MOM_LEN) - 1
    dip = c / c.shift(PB_DIP_LEN) - 1
    med_tv = panel.turnover.rolling(20, min_periods=15).median()
    nifty = nifty_close.reindex(c.index).ffill()
    market_ok = nifty > nifty.rolling(PB_MARKET_SMA, min_periods=PB_MARKET_SMA).mean()
    setup = (c > sma_s) & (sma_f > sma_s) & (c > sma_f) & (c < sma_short) & (dip <= PB_DIP) & (med_tv >= PB_MIN_TURNOVER)
    return {"setup": setup, "mom": mom, "atr": atr, "market_ok": market_ok}


def run_pullback(panel: Panel, start: pd.Timestamp, end: pd.Timestamp, nifty_close: pd.Series,
                 cost: CostModel | None = None):
    """Strategy C: buy a short dip in a strong, liquid stock in an uptrend,
    only while the Nifty is above its 200-session average."""
    ledger = Ledger(cost or CostModel())
    ind = pullback_signals(panel, nifty_close)
    sessions = panel.sessions
    queued_entries, queued_exits = [], {}
    for i, day in enumerate(sessions):
        if day < start or day > end:
            continue
        _delisting_exits(panel, ledger, i, day)
        opens, highs, lows, closes = panel.open.iloc[i], panel.high.iloc[i], panel.low.iloc[i], panel.close.iloc[i]
        for e, reason in list(queued_exits.items()):
            if e not in ledger.shares:
                queued_exits.pop(e)
                continue
            if np.isfinite(opens.get(e, np.nan)):
                ledger.sell(day, e, opens[e], _adv(panel, i, e), reason)
                queued_exits.pop(e)
        for e, atr in queued_entries:
            if e in ledger.shares or len(ledger.shares) >= PB_SLOTS:
                continue
            o = opens.get(e, np.nan)
            if not np.isfinite(o):
                continue
            stop = o - PB_ATR_MULT * atr
            if stop <= 0:
                continue
            target = o + PB_REWARD_MULT * (o - stop)
            equity_now = ledger.cash + sum(ledger.value(x, opens) for x in ledger.shares)
            gross = sum(ledger.value(x, opens) for x in ledger.shares)
            value = min(PB_RISK * equity_now / ((o - stop) / o), max(equity_now - gross, 0.0))
            if value > 0:
                ledger.buy(day, e, o, value, _adv(panel, i, e), {"stop": stop, "target": target, "entry_idx": i})
        queued_entries = []
        # stop first (wins a same-day tie), then target; gaps fill at the open
        for e in list(ledger.shares):
            m = ledger.meta[e]
            lo, hi, o = lows.get(e, np.nan), highs.get(e, np.nan), opens.get(e, np.nan)
            if np.isfinite(lo) and lo <= m["stop"]:
                ledger.sell(day, e, o if np.isfinite(o) and o < m["stop"] else m["stop"], _adv(panel, i, e), "STOP")
            elif np.isfinite(hi) and hi >= m["target"]:
                ledger.sell(day, e, o if np.isfinite(o) and o > m["target"] else m["target"], _adv(panel, i, e), "TARGET")
        ledger.mark(day, closes)
        if day >= end:
            continue
        for e in ledger.shares:
            if i - ledger.meta[e]["entry_idx"] + 1 >= PB_TIME_STOP:
                queued_exits[e] = "TIME_STOP"
        if not bool(ind["market_ok"].iloc[i]):
            continue
        members = [e for e in panel.universe_on(day) if e in panel.close.columns]
        mom_today = ind["mom"].iloc[i][members].dropna()
        if mom_today.empty:
            continue
        leaders = set(mom_today[mom_today >= mom_today.quantile(1 - PB_MOM_TOP)].index)
        today = ind["setup"].iloc[i]
        hits = [e for e in today[today.fillna(False)].index
                if e in leaders and e not in ledger.shares and np.isfinite(ind["atr"].iloc[i][e])]
        hits.sort(key=lambda e: -mom_today[e])
        queued_entries = [(e, ind["atr"].iloc[i][e]) for e in hits]
    return _result(ledger)


def wilder_rsi(close: pd.DataFrame, length: int) -> pd.DataFrame:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / length, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / length, adjust=False).mean()
    rs = gain / loss
    return 100 - 100 / (1 + rs)


def run_mean_reversion(panel: Panel, start: pd.Timestamp, end: pd.Timestamp, nifty_close: pd.Series,
                       cost: CostModel | None = None, stop_atr_mult: float | None = None):
    """Strategy MR: classic Connors RSI-2 on the liquid universe. The
    panel's universe should already be the top-100 subset."""
    ledger = Ledger(cost or CostModel())
    c, h, l = panel.close, panel.high, panel.low
    rsi = wilder_rsi(c, MR_RSI_LEN)
    trend = c.rolling(MR_TREND_SMA, min_periods=MR_TREND_SMA).mean()
    exit_sma = c.rolling(MR_EXIT_SMA, min_periods=MR_EXIT_SMA).mean()
    tr = pd.concat([(h - l), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()]).groupby(level=0).max()
    atr = tr.rolling(14, min_periods=14).mean()
    nifty = nifty_close.reindex(nifty_close.index.union(c.index)).ffill()
    market_ok = (nifty > nifty.rolling(MR_MARKET_SMA, min_periods=MR_MARKET_SMA).mean()).reindex(c.index).fillna(False)
    sessions = panel.sessions
    queued_entries, queued_exits = [], {}
    for i, day in enumerate(sessions):
        if day < start or day > end:
            continue
        _delisting_exits(panel, ledger, i, day)
        opens, lows, closes = panel.open.iloc[i], panel.low.iloc[i], panel.close.iloc[i]
        for e, reason in list(queued_exits.items()):
            if e not in ledger.shares:
                queued_exits.pop(e)
                continue
            if np.isfinite(opens.get(e, np.nan)):
                ledger.sell(day, e, opens[e], _adv(panel, i, e), reason)
                queued_exits.pop(e)
        for e, a in queued_entries:
            if e in ledger.shares or len(ledger.shares) >= MR_SLOTS:
                continue
            o = opens.get(e, np.nan)
            if not np.isfinite(o):
                continue
            equity_now = ledger.cash + sum(ledger.value(x, opens) for x in ledger.shares)
            stop = o - stop_atr_mult * a if stop_atr_mult and np.isfinite(a) else -np.inf
            ledger.buy(day, e, o, min(MR_POSITION * equity_now, ledger.cash * 0.999), _adv(panel, i, e),
                       {"stop": stop, "entry_idx": i})
        queued_entries = []
        if stop_atr_mult:
            for e in list(ledger.shares):
                st, lo, o = ledger.meta[e]["stop"], lows.get(e, np.nan), opens.get(e, np.nan)
                if np.isfinite(lo) and lo <= st:
                    ledger.sell(day, e, o if np.isfinite(o) and o < st else st, _adv(panel, i, e), "STOP")
        ledger.mark(day, closes)
        if day >= end:
            continue
        for e in ledger.shares:
            x, sma = closes.get(e, np.nan), exit_sma.iloc[i].get(e, np.nan)
            if np.isfinite(x) and np.isfinite(sma) and x > sma:
                queued_exits[e] = "BOUNCE_EXIT"
            elif i - ledger.meta[e]["entry_idx"] + 1 >= MR_TIME_STOP:
                queued_exits[e] = "TIME_STOP"
        if not bool(market_ok.iloc[i]):
            continue
        members = [e for e in panel.universe_on(day) if e in c.columns]
        r, tdy, tnd = rsi.iloc[i][members], closes[members], trend.iloc[i][members]
        hits = r[(r < MR_RSI_MAX) & (tdy > tnd)].dropna().sort_values()
        queued_entries = [(e, atr.iloc[i][e]) for e in hits.index if e not in ledger.shares]
    return _result(ledger)


def judge_mean_reversion(equity: pd.DataFrame, trades: pd.DataFrame, nifty_close: pd.Series) -> dict:
    strat = equity["equity"]
    days = strat.index
    nifty = nifty_close.reindex(nifty_close.index.union(days)).ffill().reindex(days)
    closed = trades[trades["exit_reason"] != "OPEN_AT_END"] if not trades.empty else trades
    net = (closed["pnl"] / closed["cost_basis"]) if not closed.empty else pd.Series(dtype=float)
    t_stat = net.mean() / (net.std() / np.sqrt(len(net))) if len(net) > 1 else float("nan")
    sharpe = lambda x: float(x.pct_change().mean() / x.pct_change().std() * np.sqrt(252))
    yearly_pnl = closed.groupby(pd.to_datetime(closed["exit_date"]).dt.year)["pnl"].sum() if not closed.empty else pd.Series(dtype=float)
    years = sorted(set(days.year))
    profitable_years = sum(yearly_pnl.get(y, 0.0) > 0 for y in years)
    pnl = trades["pnl"] if not trades.empty else pd.Series(dtype=float)
    top3 = float(pnl.sort_values(ascending=False).head(3).sum() / pnl.sum()) if pnl.sum() > 0 else float("inf")
    held = (pd.to_datetime(closed["exit_date"]) - pd.to_datetime(closed["entry_date"])).dt.days if not closed.empty else pd.Series(dtype=float)
    report = {
        "cagr_pct": round(_cagr(strat), 2), "nifty_cagr_pct": round(_cagr(nifty), 2),
        "sharpe": round(sharpe(strat), 2), "nifty_sharpe": round(sharpe(nifty), 2),
        "max_drawdown_pct": round(_max_dd(strat), 2), "nifty_max_drawdown_pct": round(_max_dd(nifty), 2),
        "n_trades": len(closed), "trades_per_year": round(len(closed) / max(len(years), 1), 1),
        "win_rate_pct": round(float((net > 0).mean() * 100), 1) if len(net) else None,
        "mean_net_per_trade_pct": round(float(net.mean() * 100), 3) if len(net) else None,
        "trade_t": round(float(t_stat), 2),
        "avg_calendar_days_held": round(float(held.mean()), 1) if len(held) else None,
        "years_profitable": f"{profitable_years}/{len(years)}",
        "top3_profit_share": round(top3, 3),
        "avg_gross_exposure_pct": round(equity["gross_exposure"].mean() * 100, 1),
    }
    checks = {
        "mean net per trade > 0 with t >= 2": bool(len(net) > 1 and net.mean() > 0 and t_stat >= 2),
        "win rate after costs >= 55%": bool(len(net) and (net > 0).mean() >= 0.55),
        "Sharpe > Nifty Sharpe": report["sharpe"] > report["nifty_sharpe"],
        "max drawdown no worse than Nifty": report["max_drawdown_pct"] >= report["nifty_max_drawdown_pct"],
        "profitable in >= 70% of calendar years": profitable_years >= 0.7 * len(years),
        "top-3 trades < 20% of profit": top3 < 0.2,
    }
    report["checks"] = checks
    report["verdict"] = "PASS" if all(checks.values()) else "FAIL"
    return report


def _result(ledger: Ledger):
    """Equity curve and positions. Positions still open at the end are
    included (exit_reason OPEN_AT_END, valued at their last close, no exit
    cost) so profit concentration counts every position, not only closed
    ones -- added 2026-11-02 after the confirmation run showed nearly all of
    a window's profit can sit in one open position."""
    eq = pd.DataFrame(ledger.equity, columns=["Date", "equity", "gross_exposure"]).set_index("Date")
    end = eq.index[-1] if len(eq) else None
    open_rows = [{"entity_id": e, "entry_date": m["entry_date"], "exit_date": end, "cost_basis": m["cost_basis"],
                  "proceeds": ledger.shares[e] * m["last_mark"] + m.get("trim_proceeds", 0.0),
                  "pnl": ledger.shares[e] * m["last_mark"] + m.get("trim_proceeds", 0.0) - m["cost_basis"] - m["costs"],
                  "exit_reason": "OPEN_AT_END"}
                 for e, m in ledger.meta.items() if e in ledger.shares]
    return eq, pd.DataFrame(ledger.trades + open_rows)


def equal_weight_universe(panel: Panel, start, end) -> pd.Series:
    """Daily return of an equal-weight portfolio of the current month's
    universe (close to close); a stock's return is skipped on days it
    doesn't trade."""
    rets = panel.close.ffill(limit=5).pct_change(fill_method=None)
    days = [d for d in panel.sessions if start <= d <= end]
    out = []
    for d in days:
        members = [e for e in panel.universe_on(d - pd.Timedelta(days=1)) if e in rets.columns]
        out.append(rets.loc[d, members].mean() if members else 0.0)
    return pd.Series(out, index=days).fillna(0.0)


# ---------------------------------------------------------------------------
# Judgement (docs/redesign_preregistration.md)
# ---------------------------------------------------------------------------
MIN_CAGR_EXCESS_NIFTY_PP = 5.0
MIN_EXCESS_T = 2.0
MIN_POSITIVE_YEARS = 4
DRAWDOWN_TOLERANCE_PP = 10.0
MAX_TOP3_SHARE = 0.5


def _cagr(curve: pd.Series) -> float:
    years = (curve.index[-1] - curve.index[0]).days / 365.25
    return ((curve.iloc[-1] / curve.iloc[0]) ** (1 / years) - 1) * 100


def _max_dd(curve: pd.Series) -> float:
    return float((curve / curve.cummax() - 1).min() * 100)


def judge(equity: pd.DataFrame, trades: pd.DataFrame, nifty_close: pd.Series, ew_returns: pd.Series) -> dict:
    import statsmodels.api as sm

    strat = equity["equity"]
    days = strat.index
    # last Nifty close on or before each session (Yahoo's ^NSEI skips a few NSE sessions, e.g. 2019-01-01)
    nifty = nifty_close.reindex(nifty_close.index.union(days)).ffill().reindex(days)
    ew = (1 + ew_returns.reindex(days).fillna(0)).cumprod()
    m_s, m_n = strat.resample("ME").last().pct_change().dropna(), nifty.resample("ME").last().pct_change().dropna()
    excess = (m_s - m_n).dropna()
    nw = sm.OLS(excess.to_numpy(), np.ones(len(excess))).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
    yearly = pd.DataFrame({"s": strat.resample("YE").last(), "n": nifty.resample("YE").last()})
    yearly = yearly.pct_change()
    yearly.iloc[0] = [strat.resample("YE").last().iloc[0] / strat.iloc[0] - 1,
                      nifty.resample("YE").last().iloc[0] / nifty.iloc[0] - 1]
    positive_years = int((yearly["s"] > yearly["n"]).sum())
    profit = trades.loc[trades["pnl"] > 0, "pnl"].sort_values(ascending=False) if not trades.empty else pd.Series(dtype=float)
    total = trades["pnl"].sum() if not trades.empty else 0.0
    top3 = float(profit.head(3).sum() / total) if total > 0 else float("inf")

    report = {
        "cagr_pct": round(_cagr(strat), 2), "nifty_cagr_pct": round(_cagr(nifty), 2),
        "ew_universe_cagr_pct": round(_cagr(ew), 2),
        "max_drawdown_pct": round(_max_dd(strat), 2), "nifty_max_drawdown_pct": round(_max_dd(nifty), 2),
        "monthly_excess_mean_pct": round(excess.mean() * 100, 3), "monthly_excess_t_nw3": round(float(nw.tvalues[0]), 2),
        "years_beating_nifty": f"{positive_years}/{len(yearly)}",
        "n_closed_positions": len(trades), "top3_profit_share": round(top3, 2),
        "avg_gross_exposure_pct": round(equity["gross_exposure"].mean() * 100, 1),
        "total_return_pct": round((strat.iloc[-1] / strat.iloc[0] - 1) * 100, 1),
    }
    checks = {
        "CAGR beats Nifty by >= 5 pp/yr": report["cagr_pct"] - report["nifty_cagr_pct"] >= MIN_CAGR_EXCESS_NIFTY_PP,
        "CAGR beats PIT equal-weight universe": report["cagr_pct"] > report["ew_universe_cagr_pct"],
        "monthly excess t (NW3) >= 2": report["monthly_excess_t_nw3"] >= MIN_EXCESS_T,
        "beats Nifty in >= 4 calendar years": positive_years >= MIN_POSITIVE_YEARS,
        "max drawdown within Nifty's - 10 pp": report["max_drawdown_pct"] >= report["nifty_max_drawdown_pct"] - DRAWDOWN_TOLERANCE_PP,
        "top-3 positions < 50% of profit": top3 < MAX_TOP3_SHARE,
    }
    report["checks"] = checks
    report["verdict"] = "EDGE DEMONSTRATED (provisional; next is paper trading)" if all(checks.values()) else "NO DEMONSTRATED EDGE"
    return report
