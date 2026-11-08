"""
===============================================================================
Falcon AI Swing Trading Platform — Fixed 1:3 Bracket on Existing Entries
===============================================================================
Script      : fixed_bracket.py
Package     : Backtesting

docs/fixed_rr_preregistration.md: the entry signals of F, S, B and MR are
reused exactly; only the exits and sizing change to a fixed bracket --
stop = fill x 0.98, target = fill x 1.06, 20-session time stop -- with 5
positions of 20% of equity each.

Order types an entry generator can return for the next session:
  ("market", entity, ref_close, max_gap, priority)            buy at the open
  ("stop",   entity, trigger,   max_gap, priority, valid_days, cancel_below)
===============================================================================
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.mtm_portfolio import CostModel
from backtesting.pit_strategies import Ledger, Panel, _adv, _delisting_exits, _result, wilder_rsi

STOP_PCT, TARGET_PCT, TIME_STOP, POSITION, SLOTS = 0.02, 0.06, 20, 0.20, 5


def run_bracket(panel: Panel, start, end, order_fn, cost: CostModel | None = None,
                optimistic_stop_fill_day: bool = False):
    """order_fn(i, day, held:set) -> list of orders placed at day's close.

    optimistic_stop_fill_day (SENSITIVITY ONLY, never the verdict): for a
    position entered by a BUY-STOP, assume the fill day's low came before
    the breakout, so on that day the stop counts only if the CLOSE is at or
    below it. Market-open entries are unaffected (any low after the open is
    after the fill)."""
    ledger = Ledger(cost or CostModel())
    sessions = panel.sessions
    live, queued_exits = [], set()
    for i, day in enumerate(sessions):
        if day < start or day > end:
            continue
        _delisting_exits(panel, ledger, i, day)
        opens, highs, lows, closes = panel.open.iloc[i], panel.high.iloc[i], panel.low.iloc[i], panel.close.iloc[i]
        for e in list(queued_exits):
            if e not in ledger.shares:
                queued_exits.discard(e)
            elif np.isfinite(opens.get(e, np.nan)):
                ledger.sell(day, e, opens[e], _adv(panel, i, e), "TIME_STOP")
                queued_exits.discard(e)
        # fills, in priority order
        still_live = []
        for od in sorted(live, key=lambda o: o["priority"]):
            e = od["entity"]
            if e in ledger.shares or od.get("done"):
                continue
            o, hi, lo = opens.get(e, np.nan), highs.get(e, np.nan), lows.get(e, np.nan)
            fill = None
            if np.isfinite(o) and len(ledger.shares) < SLOTS:
                if od["type"] == "market":
                    if o <= od["ref"] * (1 + od["max_gap"]):
                        fill = o
                elif np.isfinite(hi) and hi >= od["ref"] and o <= od["ref"] * (1 + od["max_gap"]):
                    fill = max(od["ref"], o)
            if fill is not None:
                equity_now = ledger.cash + sum(ledger.value(x, opens) for x in ledger.shares)
                value = min(POSITION * equity_now, ledger.cash * 0.999)
                if value > 0:
                    ledger.buy(day, e, fill, value, _adv(panel, i, e),
                               {"stop": fill * (1 - STOP_PCT), "target": fill * (1 + TARGET_PCT), "entry_idx": i,
                                "via_stop": od["type"] == "stop"})
                continue
            # unfilled: market orders last one session; stop orders until expiry / cancel level
            if od["type"] == "stop" and i < od["expires_idx"] and not (
                    od.get("cancel_below") is not None and np.isfinite(lo) and lo <= od["cancel_below"]):
                still_live.append(od)
        live = still_live
        # bracket exits: stop first, target second; gaps fill at the open after the fill day
        for e in list(ledger.shares):
            m = ledger.meta[e]
            o, hi, lo = opens.get(e, np.nan), highs.get(e, np.nan), lows.get(e, np.nan)
            gap_ok = m["entry_idx"] < i and np.isfinite(o)
            if optimistic_stop_fill_day and m.get("via_stop") and m["entry_idx"] == i:
                lo = closes.get(e, np.nan)
            if np.isfinite(lo) and lo <= m["stop"]:
                ledger.sell(day, e, o if gap_ok and o < m["stop"] else m["stop"], _adv(panel, i, e), "STOP")
            elif np.isfinite(hi) and hi >= m["target"]:
                ledger.sell(day, e, o if gap_ok and o > m["target"] else m["target"], _adv(panel, i, e), "TARGET")
        ledger.mark(day, closes)
        if day >= end:
            continue
        for e in ledger.shares:
            if i - ledger.meta[e]["entry_idx"] + 1 >= TIME_STOP:
                queued_exits.add(e)
        pending = {od["entity"] for od in live}
        for od in order_fn(i, day, set(ledger.shares) | pending):
            if od[0] == "market":
                _, e, ref, gap, pr = od
                live.append({"type": "market", "entity": e, "ref": ref, "max_gap": gap, "priority": pr})
            else:
                _, e, trig, gap, pr, valid, cancel = od
                live.append({"type": "stop", "entity": e, "ref": trig, "max_gap": gap, "priority": pr,
                             "expires_idx": i + valid, "cancel_below": cancel})
    return _result(ledger)


# ---------------------------------------------------------------------------
# Entry generators (identical signal rules to the frozen strategies)
# ---------------------------------------------------------------------------

def entries_b(panel: Panel):
    from backtesting.pit_strategies import breakout_signals, BO_MAX_GAP
    ind = breakout_signals(panel)

    def fn(i, day, busy):
        members = panel.universe_on(day)
        today = ind["signal"].iloc[i]
        hits = [e for e in today[today.fillna(False)].index if e in members and e not in busy]
        vr = ind["vol_ratio"].iloc[i]
        closes = panel.close.iloc[i]
        return [("market", e, closes[e], BO_MAX_GAP, -vr[e]) for e in hits]
    return fn


def entries_mr(panel: Panel, nifty_close: pd.Series):
    from backtesting.pit_strategies import MR_MARKET_SMA, MR_RSI_LEN, MR_RSI_MAX, MR_TREND_SMA
    c = panel.close
    rsi = wilder_rsi(c, MR_RSI_LEN)
    trend = c.rolling(MR_TREND_SMA, min_periods=MR_TREND_SMA).mean()
    nifty = nifty_close.reindex(nifty_close.index.union(c.index)).ffill()
    market_ok = (nifty > nifty.rolling(MR_MARKET_SMA, min_periods=MR_MARKET_SMA).mean()).reindex(c.index).fillna(False)

    def fn(i, day, busy):
        if not bool(market_ok.iloc[i]):
            return []
        members = [e for e in panel.universe_on(day) if e in c.columns]
        r, tdy, tnd = rsi.iloc[i][members], c.iloc[i][members], trend.iloc[i][members]
        hits = r[(r < MR_RSI_MAX) & (tdy > tnd)].dropna()
        return [("market", e, tdy[e], 10.0, float(v)) for e, v in hits.items() if e not in busy]
    return fn


def entries_s(panel: Panel, nifty_close: pd.Series):
    import backtesting.breakout_entries as be
    c, h = panel.close, panel.high
    sma50 = c.rolling(50, min_periods=50).mean()
    sma200 = c.rolling(200, min_periods=200).mean()
    mom = c / c.shift(be.S_MOM_LEN) - 1
    high20 = h.rolling(be.S_HIGH_LEN, min_periods=be.S_HIGH_LEN).max()
    groups = be.peer_strength(panel, mom)
    gdates = np.array(sorted(groups))
    nifty = nifty_close.reindex(nifty_close.index.union(c.index)).ffill()
    market_ok = (nifty > nifty.rolling(200, min_periods=200).mean()).reindex(c.index).fillna(False)

    def fn(i, day, busy):
        k = gdates.searchsorted(np.datetime64(day), side="right") - 1
        grp = groups[pd.Timestamp(gdates[k])] if k >= 0 else pd.Series(dtype=float)
        members = [e for e in panel.universe_on(day) if e in c.columns]
        rank = mom.iloc[i][members].dropna().rank(pct=True)
        need = be.S_GROUP_STRONG if bool(market_ok.iloc[i]) else be.S_GROUP_TOP
        out = []
        for e in rank[rank >= be.S_MOM_TOP].index:
            if e in busy or grp.get(e, 0.0) < need:
                continue
            x, a, b, t = c.iloc[i][e], sma50.iloc[i].get(e, np.nan), sma200.iloc[i].get(e, np.nan), high20.iloc[i].get(e, np.nan)
            if all(np.isfinite(v) for v in (x, a, b, t)) and x > a and x > b:
                out.append(("stop", e, t, be.S_MAX_GAP, -mom.iloc[i][e], 1, None))
        return out
    return fn


def entries_f(panel: Panel, setups: pd.DataFrame):
    import backtesting.breakout_entries as be
    by_scan = {pd.Timestamp(d): g for d, g in setups.groupby("scan_date")}

    def fn(i, day, busy):
        g = by_scan.get(pd.Timestamp(day))
        if g is None:
            return []
        return [("stop", s.entity_id, s.pivot, be.F_MAX_GAP, s.priority + s.distance, be.F_ORDER_DAYS, s.stop)
                for s in g.itertuples() if s.entity_id not in busy]
    return fn


def entries_s_quality(panel: Panel, nifty_close: pd.Series, base_min: int = 5, base_width: float = 0.10,
                      vol_mult: float = 1.5):
    """#3's stock filters (as entries_s) with a quality breakout on day i
    (docs/s_quality_preregistration.md): close_i above the prior 20-day high L
    (max High of i-20..i-1); that high was set >= base_min sessions before i;
    from that day to i-1 the range (max High / min Low - 1) is <= base_width;
    volume_i >= vol_mult x the prior 50-day average. Buy at the next open
    (market order, skipped if > 3% above close_i)."""
    import backtesting.breakout_entries as be
    c, h = panel.close, panel.high
    H, L, V = panel.high.to_numpy(float), panel.low.to_numpy(float), panel.volume.to_numpy(float)
    C = c.to_numpy(float)
    cols = {e: j for j, e in enumerate(c.columns)}
    sma50 = c.rolling(50, min_periods=50).mean()
    sma200 = c.rolling(200, min_periods=200).mean()
    mom = c / c.shift(be.S_MOM_LEN) - 1
    vavg = panel.volume.rolling(50, min_periods=50).mean().shift(1).to_numpy(float)
    groups = be.peer_strength(panel, mom)
    gdates = np.array(sorted(groups))
    nifty = nifty_close.reindex(nifty_close.index.union(c.index)).ffill()
    market_ok = (nifty > nifty.rolling(200, min_periods=200).mean()).reindex(c.index).fillna(False)

    def fn(i, day, busy):
        if i < 21:
            return []
        k = gdates.searchsorted(np.datetime64(day), side="right") - 1
        grp = groups[pd.Timestamp(gdates[k])] if k >= 0 else pd.Series(dtype=float)
        members = [e for e in panel.universe_on(day) if e in c.columns]
        rank = mom.iloc[i][members].dropna().rank(pct=True)
        need = be.S_GROUP_STRONG if bool(market_ok.iloc[i]) else be.S_GROUP_TOP
        out = []
        for e in rank[rank >= be.S_MOM_TOP].index:
            if e in busy or grp.get(e, 0.0) < need:
                continue
            j = cols[e]
            x, a, b = C[i, j], sma50.iloc[i].get(e, np.nan), sma200.iloc[i].get(e, np.nan)
            if not (all(np.isfinite(v) for v in (x, a, b)) and x > a and x > b):
                continue
            win = H[i - 20: i, j]
            if not np.isfinite(win).all():
                continue
            kk = int(np.argmax(win)) + i - 20                      # day of the prior 20-day high
            lvl = H[kk, j]
            if not (x > lvl and i - kk >= base_min):
                continue
            lo = np.nanmin(L[kk: i, j])
            if not (np.isfinite(lo) and lvl / lo - 1 <= base_width):
                continue
            if not (np.isfinite(vavg[i, j]) and V[i, j] >= vol_mult * vavg[i, j]):
                continue
            out.append(("market", e, x, 0.03, -mom.iloc[i][e]))
        return out
    return fn
