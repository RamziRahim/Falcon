"""
===============================================================================
Falcon AI Swing Trading Platform — Breakout-Day Entries (strategies S and F)
===============================================================================
Script      : breakout_entries.py
Package     : Backtesting

Implements docs/s_and_f_preregistration.md exactly. Both strategies enter
with a resting BUY-STOP order placed after a close and filled during the
next session(s) only if price trades up to the trigger -- the breakout
day itself, not a day late. Every triggered order counts, including false
breakouts.

  S  strong stock (126-session return top 20%, above 50/200-SMA) inside a
     strong co-movement peer group, with a Nifty 200-SMA switch; buy-stop at
     the 20-session high.
  F  Falcon's own pattern setups (analyze_ticker unchanged), buy-stop at
     Falcon's pivot, Falcon's two-low stop and measured-move target.

Shares the cash ledger, cost model and delisting rule with pit_strategies.
===============================================================================
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.mtm_portfolio import CostModel
from backtesting.pit_strategies import Ledger, Panel, _adv, _delisting_exits, _result

# ---- Strategy S (all from the pre-registration) -----------------------------
S_MOM_LEN, S_MOM_TOP, S_MOM_EXIT = 126, 0.80, 0.60
S_PEERS, S_CORR_LEN, S_CORR_MIN = 20, 252, 200
S_GROUP_STRONG, S_GROUP_TOP, S_GROUP_EXIT = 2 / 3, 0.90, 0.50
S_HIGH_LEN, S_MAX_GAP, S_ATR_MULT = 20, 0.03, 2.0
S_TIME_STOP, S_RISK, S_SLOTS = 30, 0.01, 10

# ---- Strategy F --------------------------------------------------------------
F_SCAN_EVERY, F_ORDER_DAYS, F_NEAR_PIVOT = 5, 5, 0.95
F_MAX_GAP, F_RISK, F_SLOTS = 0.03, 0.01, 5


def _pct_rank(values: pd.Series) -> pd.Series:
    return values.rank(pct=True)


def peer_strength(panel: Panel, mom: pd.DataFrame) -> dict:
    """month_end -> Series(entity -> percentile of peer-group strength) among
    that month's universe. Peers = the S_PEERS most correlated universe
    stocks over the previous S_CORR_LEN sessions (>= S_CORR_MIN of them)."""
    rets = panel.close.ffill(limit=5).pct_change(fill_method=None)
    sessions = panel.sessions
    out = {}
    for m, members in sorted(panel.universe.items()):
        pos = sessions.searchsorted(m)
        if pos < S_CORR_LEN or pos >= len(sessions):
            continue
        cols = [e for e in members if e in rets.columns]
        window = rets.iloc[pos + 1 - S_CORR_LEN: pos + 1][cols]
        cols = list(window.columns[window.notna().sum() >= S_CORR_MIN])
        if len(cols) <= S_PEERS:
            continue
        x = window[cols].to_numpy()
        x = (x - np.nanmean(x, axis=0)) / np.nanstd(x, axis=0)
        x = np.nan_to_num(x)
        corr = (x.T @ x) / len(x)
        np.fill_diagonal(corr, -np.inf)
        peers = np.argsort(-corr, axis=1)[:, :S_PEERS]
        m_now = mom.iloc[pos][cols].to_numpy()
        strength = np.nanmean(m_now[peers], axis=1)
        out[pd.Timestamp(m)] = _pct_rank(pd.Series(strength, index=cols))
    return out


def run_strategy_s(panel: Panel, start, end, nifty_close: pd.Series, cost: CostModel | None = None):
    ledger = Ledger(cost or CostModel())
    c, h, l = panel.close, panel.high, panel.low
    sma20 = c.rolling(20, min_periods=20).mean()
    sma50 = c.rolling(50, min_periods=50).mean()
    sma200 = c.rolling(200, min_periods=200).mean()
    tr = pd.concat([(h - l), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()]).groupby(level=0).max()
    atr = tr.rolling(14, min_periods=14).mean()
    mom = c / c.shift(S_MOM_LEN) - 1
    high20 = h.rolling(S_HIGH_LEN, min_periods=S_HIGH_LEN).max()
    groups = peer_strength(panel, mom)
    group_dates = np.array(sorted(groups))
    nifty = nifty_close.reindex(nifty_close.index.union(c.index)).ffill()
    market_ok = (nifty > nifty.rolling(200, min_periods=200).mean()).reindex(c.index).fillna(False)
    sessions = panel.sessions
    orders, queued_exits = [], {}

    def group_on(day):
        k = group_dates.searchsorted(np.datetime64(day), side="right") - 1
        return groups[pd.Timestamp(group_dates[k])] if k >= 0 else pd.Series(dtype=float)

    for i, day in enumerate(sessions):
        if day < start or day > end:
            continue
        _delisting_exits(panel, ledger, i, day)
        opens, highs, lows, closes = panel.open.iloc[i], h.iloc[i], l.iloc[i], c.iloc[i]
        for e, reason in list(queued_exits.items()):
            if e not in ledger.shares:
                queued_exits.pop(e)
                continue
            if np.isfinite(opens.get(e, np.nan)):
                ledger.sell(day, e, opens[e], _adv(panel, i, e), reason)
                queued_exits.pop(e)
        # buy-stop orders placed at yesterday's close
        for e, trig, a, risk in orders:
            if e in ledger.shares or len(ledger.shares) >= S_SLOTS:
                continue
            o, hi = opens.get(e, np.nan), highs.get(e, np.nan)
            if not (np.isfinite(o) and np.isfinite(hi)) or hi < trig or o > trig * (1 + S_MAX_GAP):
                continue
            fill = max(trig, o)
            stop = fill - S_ATR_MULT * a
            if stop <= 0:
                continue
            equity_now = ledger.cash + sum(ledger.value(x, opens) for x in ledger.shares)
            gross = sum(ledger.value(x, opens) for x in ledger.shares)
            value = min(risk * equity_now / ((fill - stop) / fill), max(equity_now - gross, 0.0))
            if value > 0:
                ledger.buy(day, e, fill, value, _adv(panel, i, e), {"stop": stop, "entry_idx": i})
        orders = []
        for e in list(ledger.shares):
            st, lo, o = ledger.meta[e]["stop"], lows.get(e, np.nan), opens.get(e, np.nan)
            if np.isfinite(lo) and lo <= st:
                ledger.sell(day, e, o if np.isfinite(o) and o < st and ledger.meta[e]["entry_idx"] < i else st,
                            _adv(panel, i, e), "STOP")
        ledger.mark(day, closes)
        if day >= end:
            continue
        members = [e for e in panel.universe_on(day) if e in c.columns]
        mom_rank = _pct_rank(mom.iloc[i][members].dropna())
        grp = group_on(day)
        is_month_end = i + 1 == len(sessions) or sessions[i + 1].month != day.month
        for e in ledger.shares:
            x = closes.get(e, np.nan)
            if np.isfinite(x) and np.isfinite(sma20.iloc[i].get(e, np.nan)) and x < sma20.iloc[i][e]:
                queued_exits[e] = "TREND_EXIT"
            elif mom_rank.get(e, 0.0) < S_MOM_EXIT:
                queued_exits[e] = "MOMENTUM_EXIT"
            elif is_month_end and grp.get(e, 0.0) < S_GROUP_EXIT:
                queued_exits[e] = "GROUP_EXIT"
            elif i - ledger.meta[e]["entry_idx"] + 1 >= S_TIME_STOP:
                queued_exits[e] = "TIME_STOP"
        healthy = bool(market_ok.iloc[i])
        need, risk = (S_GROUP_STRONG, S_RISK) if healthy else (S_GROUP_TOP, S_RISK / 2)
        cand = []
        for e in mom_rank[mom_rank >= S_MOM_TOP].index:
            if e in ledger.shares or grp.get(e, 0.0) < need:
                continue
            x, s50, s200 = closes.get(e, np.nan), sma50.iloc[i].get(e, np.nan), sma200.iloc[i].get(e, np.nan)
            trig, a = high20.iloc[i].get(e, np.nan), atr.iloc[i].get(e, np.nan)
            if all(np.isfinite(v) for v in (x, s50, s200, trig, a)) and x > s50 and x > s200:
                cand.append((mom.iloc[i][e], e, trig, a))
        orders = [(e, trig, a, risk) for _, e, trig, a in sorted(cand, reverse=True)]
    return _result(ledger)


# ---------------------------------------------------------------------------
# Strategy F
# ---------------------------------------------------------------------------
F_PATTERNS = (   # (detector key in analyze_ticker, setup flag, proximal low, structural low, Falcon field)
    ("vcp", "is_vcp_setup", "final_contraction_low", "first_contraction_low", "is_vcp_breakout"),
    ("triangle", "is_ascending_triangle_setup", "most_recent_rising_low", "earliest_rising_low", "is_ascending_triangle_breakout"),
    ("flat_base", "is_flat_base_setup", "recent_base_low", "base_low", "is_flat_base_breakout"),
    ("bull_flag", "is_bull_flag_setup", "flag_low", "flagpole_low", "is_bull_flag_breakout"),
)


def falcon_setup_from_analysis(analysis: dict, close: float, atr: float) -> dict | None:
    """First qualifying setup (Falcon's PATTERN_WEIGHTS order) with Falcon's
    own trade plan priced at the pivot, or None."""
    from config import MIN_REWARD_RISK
    from decision_engine.leadership_decision_engine import get_entry_target_stop

    for priority, (key, setup_flag, prox, struct, field) in enumerate(F_PATTERNS):
        r = analysis.get(key) or {}
        if not r.get(setup_flag) or r.get("is_breakout_confirmed"):
            continue
        pivot = r.get("pivot_level")
        if pivot is None or not np.isfinite(pivot) or not (F_NEAR_PIVOT * pivot <= close < pivot):
            continue
        plan = get_entry_target_stop({"Close": pivot, "ATR_14": atr}, field,
                                     {"pivot_level": pivot, "proximal_low": r.get(prox), "structural_low": r.get(struct)})
        stop, target = plan["stop_loss"], plan["target"]
        if not (stop < pivot < target):
            continue
        rr = (target - pivot) / (pivot - stop)
        if rr < MIN_REWARD_RISK:
            continue
        return {"pattern": field, "priority": priority, "pivot": float(pivot), "stop": float(stop),
                "target": float(target), "rr": float(rr), "distance": float(pivot / close - 1)}
    return None


def run_strategy_f(panel: Panel, setups: pd.DataFrame, start, end, cost: CostModel | None = None):
    """setups: entity_id, scan_date, priority, pivot, stop, target, distance
    (from tests/scan_falcon_setups.py). An order is live for the
    F_ORDER_DAYS sessions after its scan date."""
    from config import MAX_HOLDING_TRADING_DAYS

    ledger = Ledger(cost or CostModel())
    sessions = panel.sessions
    by_scan = {pd.Timestamp(d): g.sort_values(["priority", "distance"]) for d, g in setups.groupby("scan_date")}
    live, queued_exits = {}, set()
    for i, day in enumerate(sessions):
        if day < start or day > end:
            continue
        _delisting_exits(panel, ledger, i, day)
        opens, highs, lows, closes = panel.open.iloc[i], panel.high.iloc[i], panel.low.iloc[i], panel.close.iloc[i]
        # 1. time stops decided at yesterday's close, sold at today's open
        for e in list(queued_exits):
            if e not in ledger.shares:
                queued_exits.discard(e)
            elif np.isfinite(opens.get(e, np.nan)):
                ledger.sell(day, e, opens[e], _adv(panel, i, e), "TIME_STOP")
                queued_exits.discard(e)
        # 2. buy-stop fills, in priority order
        for e, od in sorted(live.items(), key=lambda kv: (kv[1]["priority"], kv[1]["distance"])):
            if e in ledger.shares or len(ledger.shares) >= F_SLOTS:
                continue
            o, hi = opens.get(e, np.nan), highs.get(e, np.nan)
            if not (np.isfinite(o) and np.isfinite(hi)) or hi < od["pivot"] or o > od["pivot"] * (1 + F_MAX_GAP):
                continue
            fill = max(od["pivot"], o)
            if fill <= od["stop"]:
                continue
            equity_now = ledger.cash + sum(ledger.value(x, opens) for x in ledger.shares)
            gross = sum(ledger.value(x, opens) for x in ledger.shares)
            value = min(F_RISK * equity_now / ((fill - od["stop"]) / fill), max(equity_now - gross, 0.0))
            if value > 0 and ledger.buy(day, e, fill, value, _adv(panel, i, e),
                                        {"stop": od["stop"], "target": od["target"], "entry_idx": i}):
                od["filled"] = True
        # 3. cancel filled, expired, or stopped-before-fill orders
        for e in list(live):
            od, lo = live[e], lows.get(e, np.nan)
            if od.get("filled") or i >= od["expires_idx"] or (np.isfinite(lo) and lo <= od["stop"]):
                live.pop(e)
        # 4. stop first, then target; a gap fills at the open (not on the fill day)
        for e in list(ledger.shares):
            m = ledger.meta[e]
            o, hi, lo = opens.get(e, np.nan), highs.get(e, np.nan), lows.get(e, np.nan)
            gap_ok = m["entry_idx"] < i and np.isfinite(o)
            if np.isfinite(lo) and lo <= m["stop"]:
                ledger.sell(day, e, o if gap_ok and o < m["stop"] else m["stop"], _adv(panel, i, e), "STOP")
            elif np.isfinite(hi) and hi >= m["target"]:
                ledger.sell(day, e, o if gap_ok and o > m["target"] else m["target"], _adv(panel, i, e), "TARGET")
        ledger.mark(day, closes)
        if day >= end:
            continue
        # 5. at the close: time stops and new orders from today's scan
        for e in ledger.shares:
            if i - ledger.meta[e]["entry_idx"] + 1 >= MAX_HOLDING_TRADING_DAYS:
                queued_exits.add(e)
        if day in by_scan:
            for _, s in by_scan[day].iterrows():
                if s["entity_id"] in ledger.shares or s["entity_id"] in live:
                    continue
                live[s["entity_id"]] = {"pivot": s["pivot"], "stop": s["stop"], "target": s["target"],
                                        "priority": s["priority"], "distance": s["distance"],
                                        "expires_idx": i + F_ORDER_DAYS}
    return _result(ledger)
