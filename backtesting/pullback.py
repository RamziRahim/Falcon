"""
===============================================================================
Falcon AI Swing Trading Platform — Leader pullback strategy (IA, 2026-11-09)
===============================================================================
Script      : pullback.py
Package     : Backtesting

docs/pullback_preregistration.md. Buy a leading stock after a short, quiet
dip, when it closes above the previous day's high; stop under the pullback
low; half off at +2R, trail the rest on a close below the 20-EMA; time stops
at day 8 (no +1R yet) and day 20.

Signals and the entry both use session t's close (an order near 3:20 pm).
Exits that trigger on a close (20-EMA trail, time stops) sell at the next
open. Stop and +2R are intraday levels; a gap through either fills at the open.
===============================================================================
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.exit_variants import PartialLedger, _result_partial
from backtesting.mtm_portfolio import CostModel
from backtesting.pit_strategies import Panel, _adv, _delisting_exits

SLOTS, PER_SECTOR, POS_CAP = 6, 2, 0.25
MAX_STOP = 0.08
SWING_LOOKBACK = 12            # swing high searched in the 12 sessions before t
DIP_MIN, DIP_MAX = 3, 8        # sessions from the swing high to t-1
DEPTH_MIN, DEPTH_MAX = 0.05, 0.12
NEAR_MA = 0.01                 # pullback low within 1% of (or below) the 20-EMA or 50-DMA
RSI_FLOOR, RSI_CEIL = 35.0, 50.0
TIME_1R, TIME_ALL = 8, 20


def _rsi(close: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn)


def run_pullback(panel: Panel, start, end, nifty: pd.Series, sector_of, risk: float = 0.01,
                 breadth: bool = False, cost: CostModel | None = None):
    """sector_of(day) -> {entity: sector index name}; stocks without one are uncapped."""
    ledger = PartialLedger(cost or CostModel())
    s = panel.sessions
    O, H, L, C, V, TO = (x.to_numpy(float) for x in (panel.open, panel.high, panel.low, panel.close,
                                                     panel.volume, panel.turnover))
    c = panel.close
    EMA20 = c.ewm(span=20, adjust=False, min_periods=20).mean().to_numpy(float)
    SMA50 = c.rolling(50, min_periods=50).mean().to_numpy(float)
    SMA200 = c.rolling(200, min_periods=200).mean().to_numpy(float)
    HI52 = panel.high.rolling(252, min_periods=200).max().to_numpy(float)
    RSI = _rsi(c).to_numpy(float)
    pc = c.shift(1)
    tr = np.maximum(panel.high - panel.low, np.maximum((panel.high - pc).abs(), (panel.low - pc).abs()))
    ATR = tr.rolling(14, min_periods=14).mean().to_numpy(float)
    VAVG = panel.volume.rolling(50, min_periods=50).mean().shift(1).to_numpy(float)
    TV20 = panel.turnover.rolling(20, min_periods=15).mean().shift(1).to_numpy(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        RAW = TO / V                                                    # traded (unadjusted) price
        MOM = c.shift(10).to_numpy(float) / c.shift(126).to_numpy(float) - 1
    cols = {e: j for j, e in enumerate(c.columns)}
    nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
    n50, n200 = nf.rolling(50, min_periods=50).mean(), nf.rolling(200, min_periods=200).mean()
    mkt = ((nf > n200) & (n50 > n50.shift(5))).to_numpy()
    st = {"signals": 0, "filled": 0, "too_wide": 0, "slots_full": 0, "sector_cap": 0,
          "market_off_days": 0, "breadth_off_days": 0}
    queued = {}                                                          # entity -> reason, sold at next open
    for i, day in enumerate(s):
        if day < start or day > end:
            continue
        _delisting_exits(panel, ledger, i, day)
        opens, closes = panel.open.iloc[i], panel.close.iloc[i]
        for e, why in list(queued.items()):
            if e not in ledger.shares:
                queued.pop(e)
            elif np.isfinite(O[i, cols[e]]):
                ledger.sell(day, e, O[i, cols[e]], _adv(panel, i, e), why)
                queued.pop(e)
        # intraday exits for positions bought on earlier sessions
        for e in list(ledger.shares):
            m = ledger.meta[e]
            if m["entry_idx"] >= i:
                continue
            j = cols[e]
            o, hi, lo = O[i, j], H[i, j], L[i, j]
            if np.isfinite(lo) and lo <= m["stop"]:
                ledger.sell(day, e, o if np.isfinite(o) and o < m["stop"] else m["stop"], _adv(panel, i, e), "STOP")
                queued.pop(e, None)
                continue
            if not m["half"] and np.isfinite(hi) and hi >= m["t2r"]:
                ledger.sell_half(e, o if np.isfinite(o) and o > m["t2r"] else m["t2r"], _adv(panel, i, e))
                m["half"] = True
            if np.isfinite(hi):
                m["max_hi"] = max(m["max_hi"], hi)
        ledger.mark(day, closes)
        if day >= end:
            continue
        # close-based exits, sold at the next open
        for e in list(ledger.shares):
            m = ledger.meta[e]
            j = cols[e]
            held = i - m["entry_idx"]
            if held >= TIME_ALL:
                queued[e] = "TIME_20"
            elif held >= TIME_1R and not m["reached_1r"] and m["max_hi"] < m["t1r"]:
                queued[e] = "TIME_8_NO_1R"
            elif m["half"] and np.isfinite(C[i, j]) and np.isfinite(EMA20[i, j]) and C[i, j] < EMA20[i, j]:
                queued[e] = "TRAIL_20EMA"
            if m["max_hi"] >= m["t1r"]:
                m["reached_1r"] = True
        # new entries at today's close
        if not mkt[i]:
            st["market_off_days"] += 1
            continue
        members = [e for e in panel.universe_on(day) if e in cols]
        if breadth:
            idx = [cols[e] for e in members]
            above = C[i, idx] > SMA200[i, idx]
            valid = np.isfinite(C[i, idx]) & np.isfinite(SMA200[i, idx])
            if valid.sum() == 0 or above[valid].mean() <= 0.5:
                st["breadth_off_days"] += 1
                continue
        mom = pd.Series({e: MOM[i, cols[e]] for e in members}).dropna()
        rank = mom.rank(pct=True)
        sec = sector_of(day)
        held_sec = pd.Series([sec.get(e) for e in ledger.shares if sec.get(e)]).value_counts().to_dict()
        cands = []
        for e in rank[rank >= 0.80].index:
            if e in ledger.shares:
                continue
            j = cols[e]
            x = C[i, j]
            if not (np.isfinite(x) and RAW[i, j] > 100 and TV20[i, j] > 1e8):
                continue
            if not (x >= 0.85 * HI52[i, j] and x > SMA50[i, j] and x > SMA200[i, j]
                    and SMA50[i, j] > SMA50[i - 10, j] and SMA200[i, j] > SMA200[i - 10, j]):
                continue
            if not x > H[i - 1, j]:                                     # trigger: close above yesterday's high
                continue
            win = H[i - SWING_LOOKBACK: i, j]
            if not np.isfinite(win).all():
                continue
            h = int(np.argmax(win)) + i - SWING_LOOKBACK
            dip = i - 1 - h                                             # sessions h+1 .. i-1
            if not (DIP_MIN <= dip <= DIP_MAX):
                continue
            seg = slice(h + 1, i + 1)
            pl = np.nanmin(L[seg, j])
            k = h + 1 + int(np.nanargmin(L[seg, j]))
            depth = 1 - pl / H[h, j]
            if not (DEPTH_MIN <= depth <= DEPTH_MAX):
                continue
            if not (pl <= EMA20[k, j] * (1 + NEAR_MA) or pl <= SMA50[k, j] * (1 + NEAR_MA)):
                continue
            if not (np.nanmean(V[h + 1: i, j]) < VAVG[h, j]):           # volume shrinks in the dip
                continue
            rmin = np.nanmin(RSI[h + 1: i, j])
            if not (RSI_FLOOR <= rmin <= RSI_CEIL):
                continue
            stop = pl - 0.5 * ATR[i, j]
            if not (np.isfinite(stop) and stop < x):
                continue
            if (x - stop) / x > MAX_STOP:
                st["too_wide"] += 1
                continue
            cands.append((-rank[e], e, x, stop))
        st["signals"] += len(cands)
        for _, e, x, stop in sorted(cands):
            if len(ledger.shares) >= SLOTS:
                st["slots_full"] += 1
                continue
            name = sec.get(e)
            if name and held_sec.get(name, 0) >= PER_SECTOR:
                st["sector_cap"] += 1
                continue
            dist = (x - stop) / x
            equity_now = ledger.cash + sum(ledger.value(y, closes) for y in ledger.shares)
            value = min(risk * equity_now / dist, POS_CAP * equity_now, ledger.cash * 0.999)
            r = x - stop
            if value > 0 and ledger.buy(day, e, x, value, _adv(panel, i, e),
                                        {"stop": stop, "entry_idx": i, "t1r": x + r, "t2r": x + 2 * r,
                                         "half": False, "max_hi": x, "reached_1r": False}):
                st["filled"] += 1
                if name:
                    held_sec[name] = held_sec.get(name, 0) + 1
    eq, trades = _result_partial(ledger)
    return eq, trades, st


def run_signal_hold(panel: Panel, start, end, signals: pd.DataFrame, sector_of, hold: int = 20,
                    atr_stop: float = 2.5, risk: float = 0.01, cost: CostModel | None = None):
    """docs/pullback_diagnostics_preregistration.md Step 1b: buy at the signal close
    (signals: t, entity_id, rank, atr, close), stop = entry - atr_stop x ATR, sell at
    the open after `hold` sessions. 6 slots, <= 2 per sector, priority by rank."""
    from backtesting.pit_strategies import Ledger, _result
    ledger = Ledger(cost or CostModel())
    s = panel.sessions
    O, L = panel.open.to_numpy(float), panel.low.to_numpy(float)
    cols = {e: j for j, e in enumerate(panel.close.columns)}
    by_t = {t: g.sort_values("rank", ascending=False) for t, g in signals.groupby("t")}
    queued = set()
    for i, day in enumerate(s):
        if day < start or day > end:
            continue
        _delisting_exits(panel, ledger, i, day)
        closes = panel.close.iloc[i]
        for e in list(queued):
            if e not in ledger.shares:
                queued.discard(e)
            elif np.isfinite(O[i, cols[e]]):
                ledger.sell(day, e, O[i, cols[e]], _adv(panel, i, e), "TIME")
                queued.discard(e)
        for e in list(ledger.shares):
            m = ledger.meta[e]
            j = cols[e]
            if m["entry_idx"] < i and np.isfinite(L[i, j]) and L[i, j] <= m["stop"]:
                o = O[i, j]
                ledger.sell(day, e, o if np.isfinite(o) and o < m["stop"] else m["stop"], _adv(panel, i, e), "STOP")
        ledger.mark(day, closes)
        if day >= end:
            continue
        for e in ledger.shares:
            if i - ledger.meta[e]["entry_idx"] >= hold:
                queued.add(e)
        g = by_t.get(i)
        if g is None:
            continue
        sec = sector_of(day)
        held_sec = pd.Series([sec.get(e) for e in ledger.shares if sec.get(e)]).value_counts().to_dict()
        for r in g.itertuples():
            e = r.entity_id
            if e in ledger.shares or len(ledger.shares) >= SLOTS:
                continue
            name = sec.get(e)
            if name and held_sec.get(name, 0) >= PER_SECTOR:
                continue
            x, stop = r.close, r.close - atr_stop * r.atr
            if not (np.isfinite(stop) and 0 < stop < x):
                continue
            dist = (x - stop) / x
            equity_now = ledger.cash + sum(ledger.value(y, closes) for y in ledger.shares)
            value = min(risk * equity_now / dist, POS_CAP * equity_now, ledger.cash * 0.999)
            if value > 0 and ledger.buy(day, e, x, value, _adv(panel, i, e), {"stop": stop, "entry_idx": i}):
                if name:
                    held_sec[name] = held_sec.get(name, 0) + 1
    eq, trades = _result(ledger)
    return eq, trades, {}
