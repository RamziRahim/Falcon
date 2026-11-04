"""
===============================================================================
Falcon AI Swing Trading Platform — FM: Falcon Momentum
===============================================================================
Script      : falcon_momentum.py
Package     : Backtesting

docs/falcon_momentum_preregistration.md: weekly volatility-adjusted momentum
rank (top 30), sector confirmation (NSE sector index if correlation >= 0.5,
else correlated peer group), crash protection (no entries with Nifty <=
200-SMA; 0.5% risk when Nifty <= 50-SMA, else 1%), stop = tighter of the
swing-low stop and fill - 3 ATR, target 3R, momentum exit (rank > 100),
time stop 40 (or 20) sessions.
===============================================================================
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.breakout_entries import peer_strength
from backtesting.mtm_portfolio import CostModel
from backtesting.pit_strategies import Ledger, Panel, _adv, _delisting_exits, _result
from backtesting.swing_risk import pivot_lows, swing_stop

TOP_N, EXIT_RANK, SLOTS, POS_CAP, MAX_GAP = 30, 100, 10, 0.25, 0.05
RISK_ON, RISK_SOFT, R_MULT, ATR_CAP = 0.01, 0.005, 3.0, 3.0
CORR_MIN, PEER_STRONG = 0.5, 2 / 3
SECTOR_INDICES = ["NIFTY AUTO", "NIFTY BANK", "NIFTY ENERGY", "NIFTY FINANCIAL SERVICES", "NIFTY FMCG",
                  "NIFTY IT", "NIFTY MEDIA", "NIFTY METAL", "NIFTY PHARMA", "NIFTY PSU BANK", "NIFTY REALTY"]


def momentum_score(panel: Panel) -> pd.DataFrame:
    c = panel.close
    rets = c.ffill(limit=5).pct_change(fill_method=None)
    vol = rets.rolling(252, min_periods=200).std() * np.sqrt(252)
    m6 = (c / c.shift(126) - 1) / vol
    m12 = (c / c.shift(252) - 1) / vol
    return m6, m12


def weekly_ranks(panel: Panel, start, end):
    """session index -> Series(entity -> rank, 1 = best) at each week's last session."""
    m6, m12 = momentum_score(panel)
    s = panel.sessions
    week = s.to_period("W")
    last_of_week = [i for i in range(len(s) - 1) if week[i] != week[i + 1]]
    out = {}
    for i in last_of_week:
        if s[i] < start or s[i] > end:
            continue
        members = [e for e in panel.universe_on(s[i]) if e in m6.columns]
        a, b = m6.iloc[i][members], m12.iloc[i][members]
        ok = a.notna() & b.notna() & np.isfinite(a) & np.isfinite(b)
        a, b = a[ok], b[ok]
        if len(a) < 50:
            continue
        z = ((a - a.mean()) / a.std() + (b - b.mean()) / b.std()) / 2
        out[i] = z.rank(ascending=False, method="first")
    return out


def sector_maps(panel: Panel, indices: pd.DataFrame):
    """month_end -> {entity: index name} for stocks whose best sector-index correlation >= CORR_MIN."""
    rets = panel.close.ffill(limit=5).pct_change(fill_method=None)
    idx_close = indices.reindex(indices.index.union(panel.sessions)).ffill().reindex(panel.sessions)
    idx_ret = idx_close.pct_change(fill_method=None)
    s = panel.sessions
    out = {}
    for m, members in sorted(panel.universe.items()):
        pos = s.searchsorted(m)
        if pos < 252 or pos >= len(s):
            continue
        cols = [e for e in members if e in rets.columns]
        x = rets.iloc[pos - 251: pos + 1][cols]
        y = idx_ret.iloc[pos - 251: pos + 1]
        y = y.loc[:, y.notna().sum() >= 200]
        if y.empty:
            continue
        good = x.notna().sum() >= 200
        x = x.loc[:, good]
        xs = ((x - x.mean()) / x.std()).fillna(0).to_numpy()
        ys = ((y - y.mean()) / y.std()).fillna(0).to_numpy()
        corr = xs.T @ ys / (len(xs) - 1)
        best = corr.argmax(axis=1)
        mapping = {}
        for k, e in enumerate(x.columns):
            if corr[k, best[k]] >= CORR_MIN:
                mapping[e] = y.columns[best[k]]
        out[pd.Timestamp(m)] = mapping
    return out


def run_fm(panel: Panel, start, end, nifty: pd.Series, indices: pd.DataFrame, time_stop: int,
           cost: CostModel | None = None, review_at: int | None = None, review_gain: float = 0.02,
           review_rank: int = 50):
    """review_at (docs/fm_review_preregistration.md): at the close of that many
    sessions held, sell at the next open unless the close is >= fill x (1 +
    review_gain) AND the latest weekly rank <= review_rank. None = off (FM as frozen)."""
    ledger = Ledger(cost or CostModel())
    s = panel.sessions
    c = panel.close
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
    piv = pivot_lows(panel)
    pc = c.shift(1)
    tr = np.maximum(panel.high - panel.low, np.maximum((panel.high - pc).abs(), (panel.low - pc).abs()))
    atr = tr.rolling(14, min_periods=14).mean()

    def latest(dates, store, day):
        k = dates.searchsorted(np.datetime64(day), side="right") - 1
        return store[pd.Timestamp(dates[k])] if k >= 0 else {}

    queued, queued_exits, last_rank = [], set(), {}
    stats = {"review_exits": 0, "review_kept": 0, "weeks": 0, "weeks_blocked_by_market": 0, "candidates": 0, "sector_rejected": 0,
             "by_index": 0, "by_peers": 0, "gap_skip": 0, "stop_skip": 0}
    for i, day in enumerate(s):
        if day < start or day > end:
            continue
        _delisting_exits(panel, ledger, i, day)
        opens, highs, lows, closes = panel.open.iloc[i], panel.high.iloc[i], panel.low.iloc[i], c.iloc[i]
        for e in list(queued_exits):
            if e not in ledger.shares:
                queued_exits.discard(e)
            elif np.isfinite(opens.get(e, np.nan)):
                ledger.sell(day, e, opens[e], _adv(panel, i, e), "MOMENTUM_EXIT" if ledger.meta[e].get("rank_exit")
                            else "REVIEW_EXIT" if ledger.meta[e].get("review_exit") else "TIME_STOP")
                queued_exits.discard(e)
        for od in queued:                                   # entries at the open, in rank order
            e = od["entity"]
            if e in ledger.shares or len(ledger.shares) >= SLOTS:
                continue
            o = opens.get(e, np.nan)
            if not np.isfinite(o):
                continue
            if o > od["ref"] * (1 + MAX_GAP):
                stats["gap_skip"] += 1
                continue
            stop = max(od["swing"] if od["swing"] is not None else -np.inf, o - ATR_CAP * od["atr"])
            if o <= stop:
                stats["stop_skip"] += 1
                continue
            dist = (o - stop) / o
            equity_now = ledger.cash + sum(ledger.value(x, opens) for x in ledger.shares)
            value = min(od["risk"] * equity_now / dist, POS_CAP * equity_now, ledger.cash * 0.999)
            if value > 0:
                ledger.buy(day, e, o, value, _adv(panel, i, e),
                           {"stop": stop, "target": o + R_MULT * (o - stop), "entry_idx": i, "fill": o})
        queued = []
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
        for e in ledger.shares:
            if i - ledger.meta[e]["entry_idx"] + 1 >= time_stop:
                queued_exits.add(e)
            elif review_at is not None and i - ledger.meta[e]["entry_idx"] + 1 == review_at:
                m = ledger.meta[e]
                px = closes.get(e, np.nan)
                keep = np.isfinite(px) and px >= m["fill"] * (1 + review_gain) and last_rank.get(e, np.inf) <= review_rank
                if keep:
                    stats["review_kept"] += 1
                else:
                    stats["review_exits"] += 1
                    m["review_exit"] = True
                    queued_exits.add(e)
        if i not in ranks:
            continue
        rk = ranks[i]
        last_rank = rk.to_dict()
        stats["weeks"] += 1
        for e in ledger.shares:                              # momentum exit
            if rk.get(e, np.inf) > EXIT_RANK:
                ledger.meta[e]["rank_exit"] = True
                queued_exits.add(e)
        if not (nf.iloc[i] > n200.iloc[i]):
            stats["weeks_blocked_by_market"] += 1
            continue
        risk = RISK_ON if nf.iloc[i] > n50.iloc[i] else RISK_SOFT
        smap, grp = latest(sdates, smaps, day), latest(gdates, groups, day)
        for e in rk[rk <= TOP_N].sort_values().index:
            if e in ledger.shares:
                continue
            stats["candidates"] += 1
            name = smap.get(e)
            if name is not None:
                ok = bool(idx_ok[name].iloc[i])
                stats["by_index"] += 1
            else:
                ok = grp.get(e, 0.0) >= PEER_STRONG
                stats["by_peers"] += 1
            if not ok:
                stats["sector_rejected"] += 1
                continue
            a = atr.iloc[i].get(e, np.nan)
            ref = closes.get(e, np.nan)
            if not (np.isfinite(a) and np.isfinite(ref)):
                continue
            queued.append({"entity": e, "ref": ref, "atr": a, "risk": risk,
                           "swing": swing_stop(panel, piv, atr, i, e, ref)})
    equity, trades = _result(ledger)
    return equity, trades, stats
