"""
===============================================================================
Falcon AI Swing Trading Platform — FM with entry triggers (E1 breakout, E2 sweep, E3 FVG)
===============================================================================
Script      : falcon_momentum_entries.py
Package     : Backtesting

docs/falcon_momentum_entries_preregistration.md. The FM watch list (weekly
top-30 momentum rank, sector confirmation, Nifty > 200-SMA) is unchanged;
instead of buying at the next open, each qualifying stock is watched for
WATCH_DAYS sessions and bought only on its entry trigger:

  E1 breakout : IA's range breakout (tests/analyse_ia_breakout.py: break of the
                previous swing high, 5-30 session range <= 10% wide, close above
                the range on volume > 1.5 x 50-day average) -> buy next open;
                stop = range low - 0.25 ATR
  E2 sweep    : low_t < the last confirmed swing low (within 60 sessions) and
                close_t > it -> buy next open; stop = low_t - 0.25 ATR
  E3 FVG      : most recent unmitigated bullish FVG (Falcon's definition:
                candle-1 High < candle-3 Low; mitigated once a later Low reaches
                the gap bottom), formed within the last 20 sessions -> limit buy
                at the gap top on the next session; fill = min(open, top);
                stop = gap bottom - 0.25 ATR

Same as FM: 1% risk (0.5% when Nifty <= 50-SMA), no entries when Nifty <=
200-SMA, position <= 25% equity, <= 10 positions, target 3R, rank-100 exit,
40-session time stop, stop wins ties, skip if the stop is > 15% below the fill.
===============================================================================
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.breakout_entries import peer_strength
from backtesting.falcon_momentum import (EXIT_RANK, MAX_GAP, PEER_STRONG, POS_CAP, R_MULT, RISK_ON, RISK_SOFT, SLOTS,
                                         TOP_N, sector_maps, weekly_ranks)
from backtesting.mtm_portfolio import CostModel
from backtesting.pit_strategies import Ledger, Panel, _adv, _delisting_exits, _result
from backtesting.swing_risk import pivot_lows, swing_stop

WATCH_DAYS, BUFFER, MAX_STOP, FVG_LOOKBACK, SWEEP_LOOKBACK, PIVOT_W = 10, 0.25, 0.15, 20, 60, 3


def run_fm_entries(panel: Panel, start, end, nifty: pd.Series, indices: pd.DataFrame, mode: str,
                   breakouts: dict | None = None, time_stop: int = 40, cost: CostModel | None = None,
                   r_mult: float = R_MULT, fixed_stop: float | None = None, fixed_tgt: float | None = None,
                   be_at: float | None = None, range_max: float | None = None, vol_exit: float | None = None,
                   cooldown: int = 0, levels: list | None = None):
    """mode "high20" (docs/fm_high20_preregistration.md): while on the watch list, a
    one-session buy-stop at the 20-day high (fill = max(level, open), skipped if the open
    is > 3% above the level). Stop = FM's (higher of swing-low stop and fill - 3 ATR),
    or fill x (1 - fixed_stop); target r_mult x risk or fill x (1 + fixed_tgt); be_at:
    stop to the fill from the session after the high reaches fill x (1 + be_at)."""
    assert mode in ("breakout", "sweep", "fvg", "high20", "rangevol", "closebuy", "closebuy_vol")
    ledger = Ledger(cost or CostModel())
    s, c = panel.sessions, panel.close
    cols = {e: j for j, e in enumerate(c.columns)}
    H, L, C = panel.high.to_numpy(float), panel.low.to_numpy(float), c.to_numpy(float)
    nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
    n200, n50 = nf.rolling(200, min_periods=200).mean(), nf.rolling(50, min_periods=50).mean()
    n126 = nf / nf.shift(126) - 1
    idx = indices.reindex(indices.index.union(s)).ffill().reindex(s)
    idx_ok = (idx / idx.shift(126) - 1).gt(n126, axis=0) & (idx > idx.rolling(50, min_periods=50).mean())
    ranks = weekly_ranks(panel, start - pd.Timedelta(days=10), end)
    smaps = sector_maps(panel, indices)
    sdates = np.array(sorted(smaps))
    groups = peer_strength(panel, c / c.shift(126) - 1)
    gdates = np.array(sorted(groups))
    piv = pivot_lows(panel) if mode in ("sweep", "high20", "rangevol", "closebuy", "closebuy_vol") else None
    V = panel.volume.to_numpy(float)
    vavg = panel.volume.rolling(50, min_periods=50).mean().shift(1).to_numpy(float)
    high20 = panel.high.rolling(20, min_periods=20).max().to_numpy(float)
    pc = c.shift(1)
    tr = np.maximum(panel.high - panel.low, np.maximum((panel.high - pc).abs(), (panel.low - pc).abs()))
    atr_df = tr.rolling(14, min_periods=14).mean()
    atr = atr_df.to_numpy(float)

    def latest(dates, store, day):
        k = dates.searchsorted(np.datetime64(day), side="right") - 1
        return store[pd.Timestamp(dates[k])] if k >= 0 else {}

    def trigger(e, t):
        """Order for session t+1 from information up to the close of t, or None."""
        j = cols[e]
        a = atr[t, j]
        if not np.isfinite(a):
            return None
        if mode == "rangevol":                  # docs/range_volume_preregistration.md
            if t < 21:
                return None
            win = H[t - 20: t, j]
            if not np.isfinite(win).all():
                return None
            kk = int(np.argmax(win)) + t - 20
            lvl = H[kk, j]
            lo = np.nanmin(L[kk: t, j])
            if not (H[t, j] > lvl and np.isfinite(lo) and lvl / lo - 1 <= 0.10
                    and np.isfinite(vavg[t, j]) and V[t, j] >= 1.5 * vavg[t, j]):
                return None
            return {"type": "market", "ref": C[t, j], "atr": a, "fm_stop": True,
                    "swing": swing_stop(panel, piv, atr_df, t, e, C[t, j]), "stop": np.nan}
        if mode in ("closebuy", "closebuy_vol"):            # docs/close_entry_preregistration.md
            trig = high20[t, j]
            if not np.isfinite(trig):
                return None
            return {"type": "closebuy", "trig": trig, "atr": a, "ref": C[t, j],
                    "swing": swing_stop(panel, piv, atr_df, t, e, min(trig, C[t, j]))}
        if mode == "high20":
            trig = high20[t, j]
            if not np.isfinite(trig):
                return None
            return {"type": "buystop", "trig": trig, "atr": a, "ref": C[t, j],
                    "swing": swing_stop(panel, piv, atr_df, t, e, min(trig, C[t, j]))}
        if mode == "breakout":
            hit = breakouts.get((j, t))
            if hit is None:
                return None
            level, b = hit
            return {"type": "market", "stop": np.nanmin(L[b + 1: t, j]) - BUFFER * a, "ref": C[t, j]}
        if mode == "sweep":
            pv = piv.get(e)
            k = np.searchsorted(pv, t - PIVOT_W, side="right") - 1        # confirmed by t
            if k < 0 or pv[k] < t - SWEEP_LOOKBACK:
                return None
            sl = L[pv[k], j]
            if L[t, j] < sl < C[t, j]:
                return {"type": "market", "stop": L[t, j] - BUFFER * a, "ref": C[t, j]}
            return None
        # fvg: most recent unmitigated bullish gap whose third candle is <= t
        for k3 in range(t, max(t - FVG_LOOKBACK, 2) - 1, -1):
            bottom, top = H[k3 - 2, j], L[k3, j]
            if not (top > bottom) or not (top < C[t, j]):                  # price must sit above the gap
                continue
            later = L[k3 + 1: t + 1, j]
            if later.size and np.nanmin(later) <= bottom:
                continue                                                     # mitigated
            return {"type": "limit", "top": top, "stop": bottom - BUFFER * a, "ref": C[t, j]}
        return None

    watch, orders, queued_exits, blocked = {}, [], set(), {}
    stats = {"watch_added": 0, "triggers": 0, "filled": 0, "expired_unfilled": 0, "gap_skip": 0,
             "stop_skip": 0, "too_wide": 0, "blocked_market": 0, "range_skip": 0, "vol_exit": 0}
    for i, day in enumerate(s):
        if day < start or day > end:
            continue
        _delisting_exits(panel, ledger, i, day)
        opens, highs, lows, closes = panel.open.iloc[i], panel.high.iloc[i], panel.low.iloc[i], c.iloc[i]
        for e in list(queued_exits):
            if e not in ledger.shares:
                queued_exits.discard(e)
            elif np.isfinite(opens.get(e, np.nan)):
                ledger.sell(day, e, opens[e], _adv(panel, i, e),
                            "MOMENTUM_EXIT" if ledger.meta[e].get("rank_exit") else "TIME_STOP")
                queued_exits.discard(e)
        for od in sorted(orders, key=lambda o: o["priority"]):               # fills at today's prices
            e = od["entity"]
            if e in ledger.shares or len(ledger.shares) >= SLOTS:
                continue
            o, lo = opens.get(e, np.nan), lows.get(e, np.nan)
            if not np.isfinite(o):
                continue
            if od["type"] == "closebuy":
                hi, c_, j = highs.get(e, np.nan), closes.get(e, np.nan), cols[e]
                if not (np.isfinite(hi) and hi > od["trig"] and np.isfinite(c_) and np.isfinite(lo)):
                    continue
                rng = hi - lo
                clean = c_ >= od["trig"] and c_ >= o and rng > 0 and (hi - max(o, c_)) / rng < 0.5
                if clean and mode == "closebuy_vol":
                    clean = bool(np.isfinite(vavg[i, j]) and V[i, j] >= 1.5 * vavg[i, j])
                if not clean:
                    stats["candle_skip"] = stats.get("candle_skip", 0) + 1
                    continue
                fill = c_
                od["stop"] = max(od["swing"] if od["swing"] is not None else -np.inf, fill - 3.0 * od["atr"])
            elif od["type"] == "buystop":
                hi = highs.get(e, np.nan)
                if not (np.isfinite(hi) and hi >= od["trig"]):
                    continue
                if o > od["trig"] * 1.03:
                    stats["gap_skip"] += 1
                    continue
                if range_max is not None:                # docs/volume_exit_preregistration.md
                    j = cols[e]
                    win = H[i - 20: i, j]
                    kk = int(np.argmax(np.nan_to_num(win, nan=-np.inf))) + i - 20
                    lo_r = np.nanmin(L[kk: i, j])
                    if not (np.isfinite(lo_r) and H[kk, j] / lo_r - 1 <= range_max):
                        stats["range_skip"] += 1
                        continue
                fill = max(od["trig"], o)
                od["stop"] = (fill * (1 - fixed_stop) if fixed_stop is not None else
                              max(od["swing"] if od["swing"] is not None else -np.inf, fill - 3.0 * od["atr"]))
            elif od["type"] == "market":
                if o > od["ref"] * (1 + MAX_GAP):
                    stats["gap_skip"] += 1
                    continue
                fill = o
                if od.get("fm_stop"):
                    od["stop"] = (fill * (1 - fixed_stop) if fixed_stop is not None else
                                  max(od["swing"] if od["swing"] is not None else -np.inf, fill - 3.0 * od["atr"]))
            else:
                if not (np.isfinite(lo) and lo <= od["top"]):
                    continue
                fill = min(o, od["top"])
            stop = od["stop"]
            if fill <= stop:
                stats["stop_skip"] += 1
                continue
            dist = (fill - stop) / fill
            if dist > MAX_STOP:
                stats["too_wide"] += 1
                continue
            equity_now = ledger.cash + sum(ledger.value(x, opens) for x in ledger.shares)
            value = min(od["risk"] * equity_now / dist, POS_CAP * equity_now, ledger.cash * 0.999)
            if value > 0 and ledger.buy(day, e, fill, value, _adv(panel, i, e),
                                        {"stop": stop, "entry_idx": i, "fill": fill, "be_from": None,
                                         "at_close": od["type"] == "closebuy",
                                         "target": fill * (1 + fixed_tgt) if fixed_tgt is not None else fill + r_mult * (fill - stop),
                                         "be_at": be_at}):
                stats["filled"] += 1
                watch.pop(e, None)
                if levels is not None:
                    levels.append((e, day, fill, stop, ledger.meta[e]["target"]))
        orders = []
        for e in list(ledger.shares):
            m = ledger.meta[e]
            o, hi, lo = opens.get(e, np.nan), highs.get(e, np.nan), lows.get(e, np.nan)
            gap_ok = m["entry_idx"] < i and np.isfinite(o)
            if m.get("at_close") and m["entry_idx"] == i:
                continue
            if m.get("be_from") is not None and i >= m["be_from"]:
                m["stop"] = max(m["stop"], m["fill"])
            if np.isfinite(lo) and lo <= m["stop"]:
                ledger.sell(day, e, o if gap_ok and o < m["stop"] else m["stop"], _adv(panel, i, e),
                            "BREAKEVEN" if m.get("be_from") is not None and m["stop"] >= m["fill"] else "STOP")
            elif np.isfinite(hi) and hi >= m["target"]:
                ledger.sell(day, e, o if gap_ok and o > m["target"] else m["target"], _adv(panel, i, e), "TARGET")
            elif (m.get("be_at") is not None and m.get("be_from") is None and np.isfinite(hi)
                  and hi >= m["fill"] * (1 + m["be_at"]) and m["fill"] * (1 + m["be_at"]) < m["target"]):
                m["be_from"] = i + 1
            elif vol_exit is not None and m["entry_idx"] == i:
                j = cols[e]
                if np.isfinite(vavg[i, j]) and np.isfinite(V[i, j]) and V[i, j] < vol_exit * vavg[i, j] \
                        and np.isfinite(closes.get(e, np.nan)):
                    ledger.sell(day, e, closes[e], _adv(panel, i, e), "VOL_EXIT")
                    stats["vol_exit"] += 1
                    if cooldown:                         # docs/volume_cooldown_preregistration.md
                        blocked[e] = i + cooldown
        ledger.mark(day, closes)
        if day >= end:
            continue
        for e in ledger.shares:
            if i - ledger.meta[e]["entry_idx"] + 1 >= time_stop:
                queued_exits.add(e)
        if i in ranks:                                                       # weekly: rank exit + watch list
            rk = ranks[i]
            for e in ledger.shares:
                if rk.get(e, np.inf) > EXIT_RANK:
                    ledger.meta[e]["rank_exit"] = True
                    queued_exits.add(e)
            if nf.iloc[i] > n200.iloc[i]:
                smap, grp = latest(sdates, smaps, day), latest(gdates, groups, day)
                for e, r in rk[rk <= TOP_N].sort_values().items():
                    if e in ledger.shares:
                        continue
                    name = smap.get(e)
                    ok = bool(idx_ok[name].iloc[i]) if name is not None else grp.get(e, 0.0) >= PEER_STRONG
                    if ok:
                        if e not in watch:
                            stats["watch_added"] += 1
                        watch[e] = {"expires": i + WATCH_DAYS, "priority": float(r)}
        for e in list(watch):                                                # daily trigger check
            if i > watch[e]["expires"]:
                stats["expired_unfilled"] += 1
                del watch[e]
                continue
            if e in ledger.shares:
                del watch[e]
                continue
            if blocked.get(e, -1) >= i:
                continue
            od = trigger(e, i)
            if od is None:
                continue
            if not (nf.iloc[i] > n200.iloc[i]):
                stats["blocked_market"] += 1
                continue
            stats["triggers"] += 1
            od.update({"entity": e, "priority": watch[e]["priority"],
                       "risk": RISK_ON if nf.iloc[i] > n50.iloc[i] else RISK_SOFT})
            orders.append(od)
    equity, trades = _result(ledger)
    return equity, trades, stats
