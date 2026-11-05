"""
===============================================================================
Falcon AI Swing Trading Platform — #3 with a sector filter and exit variants
===============================================================================
Script      : s_sector.py
Package     : Backtesting

docs/s_sector_preregistration.md. Strategy #3 (S entries, 1% risk, 20-session
limit) with the Nifty-50-above-50-SMA filter replaced by a per-stock filter:

  the stock's NSE sector index (best 252-day return correlation >= 0.5, from
  backtesting.falcon_momentum.sector_maps) is above its 50-session SMA; if no
  sector index fits, the index of its size bucket by that month's universe
  rank: 1-100 Nifty 50, 101-250 our equal-weight mid-cap index, 251-500 our
  equal-weight small-cap index (built from the point-in-time universe).

Exit modes:
  "swing"  : stop below the swing low (skip if > 15%), target R x risk
  "fixed"  : stop entry x 0.95, target entry x 1.05 (1:1)
  half_at  : with "swing", sell half at entry x (1 + half_at) and move the stop
             on the rest to the entry from the next session
===============================================================================
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.exit_variants import PartialLedger, _result_partial
from backtesting.falcon_momentum import SECTOR_INDICES, sector_maps
from backtesting.mtm_portfolio import CostModel
from backtesting.pit_strategies import Panel, _adv, _delisting_exits
from backtesting.swing_risk import ATR_LEN, MAX_STOP_DIST, POS_CAP, RISK, SLOTS, pivot_lows, swing_stop

BUCKETS = ((100, "NIFTY 50"), (250, "EW MIDCAP"), (500, "EW SMALLCAP"))


def bucket_indices(panel: Panel, universe: pd.DataFrame) -> pd.DataFrame:
    """Equal-weight daily index of each month's rank 101-250 and 251-500 members."""
    rets = panel.close.ffill(limit=5).pct_change(fill_method=None).clip(-0.5, 1.0)
    s = panel.sessions
    me = sorted(universe["month_end"].unique())
    out = {"EW MIDCAP": pd.Series(np.nan, index=s), "EW SMALLCAP": pd.Series(np.nan, index=s)}
    for k, m in enumerate(me):
        start = s.searchsorted(m, side="right")
        stop = s.searchsorted(me[k + 1], side="right") if k + 1 < len(me) else len(s)
        u = universe[universe["month_end"] == m]
        for name, lo, hi in (("EW MIDCAP", 101, 250), ("EW SMALLCAP", 251, 500)):
            ids = [e for e in u.loc[(u["rank"] >= lo) & (u["rank"] <= hi), "entity_id"] if e in rets.columns]
            out[name].iloc[start:stop] = rets.iloc[start:stop][ids].mean(axis=1).to_numpy()
    return pd.DataFrame({n: (1 + r.fillna(0)).cumprod() for n, r in out.items()})


class SectorFilter:
    def __init__(self, panel: Panel, universe: pd.DataFrame, nifty: pd.Series, indices_long: pd.DataFrame,
                 fallback: str = "bucket"):
        """fallback: "bucket" (size-bucket index) or "nifty" (Nifty 50) when no sector index fits."""
        assert fallback in ("bucket", "nifty")
        self.fallback = fallback
        s = panel.sessions
        sect = indices_long[indices_long["Index"].isin(SECTOR_INDICES)].pivot_table(
            index="Date", columns="Index", values="Close").sort_index()
        self.smaps = sector_maps(panel, sect)
        self.sdates = np.array(sorted(self.smaps))
        allidx = sect.reindex(sect.index.union(s)).ffill().reindex(s)
        allidx["NIFTY 50"] = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
        allidx = allidx.join(bucket_indices(panel, universe))
        self.ok = (allidx > allidx.rolling(50, min_periods=50).mean())
        self.ranks = {pd.Timestamp(m): g.set_index("entity_id")["rank"] for m, g in universe.groupby("month_end")}
        self.rdates = np.array(sorted(self.ranks))
        self.used = {"sector": 0, "bucket": 0}

    def _latest(self, dates, store, day):
        k = dates.searchsorted(np.datetime64(day), side="right") - 1
        return store[pd.Timestamp(dates[k])] if k >= 0 else {}

    def allows(self, i, day, e) -> bool:
        name = self._latest(self.sdates, self.smaps, day).get(e)
        if name is not None:
            self.used["sector"] += 1
        elif self.fallback == "nifty":
            name = "NIFTY 50"
            self.used["bucket"] += 1
        else:
            r = self._latest(self.rdates, self.ranks, day)
            rank = r.get(e, 500) if hasattr(r, "get") else 500
            name = next(n for cut, n in BUCKETS if rank <= cut)
            self.used["bucket"] += 1
        return bool(self.ok[name].iloc[i])


def run_s_sector(panel: Panel, start, end, order_fn, flt: SectorFilter, *, mode: str = "swing",
                 r_multiple: float = 3.0, half_at: float | None = None, time_stop: int = 20,
                 cost: CostModel | None = None):
    assert mode in ("swing", "fixed")
    ledger = PartialLedger(cost or CostModel())
    sessions = panel.sessions
    piv = pivot_lows(panel)
    pc = panel.close.shift(1)
    tr = np.maximum(panel.high - panel.low, np.maximum((panel.high - pc).abs(), (panel.low - pc).abs()))
    atr = tr.rolling(ATR_LEN, min_periods=ATR_LEN).mean()
    live, queued_exits = [], set()
    st = {"no_swing_low": 0, "gap_below_stop": 0, "stop_too_wide": 0, "filtered_out": 0, "halves": 0}
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
        still_live = []
        for od in sorted(live, key=lambda o: o["priority"]):
            e = od["entity"]
            if e in ledger.shares:
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
                if mode == "fixed":
                    stop, target = fill * 0.95, fill * 1.05
                else:
                    stop = od["stop"]
                    if fill <= stop:
                        st["gap_below_stop"] += 1
                        continue
                    target = fill + r_multiple * (fill - stop)
                dist = (fill - stop) / fill
                if dist > MAX_STOP_DIST:
                    st["stop_too_wide"] += 1
                    continue
                equity_now = ledger.cash + sum(ledger.value(x, opens) for x in ledger.shares)
                value = min(RISK * equity_now / dist, POS_CAP * equity_now, ledger.cash * 0.999)
                if value > 0:
                    half = fill * (1 + half_at) if half_at is not None and fill * (1 + half_at) < target else None
                    ledger.buy(day, e, fill, value, _adv(panel, i, e),
                               {"stop": stop, "target": target, "entry_idx": i, "fill": fill, "half": half,
                                "be_from": None})
                continue
            if od["type"] == "stop" and i < od["expires_idx"] and not (
                    od.get("cancel_below") is not None and np.isfinite(lo) and lo <= od["cancel_below"]):
                still_live.append(od)
        live = still_live
        for e in list(ledger.shares):
            m = ledger.meta[e]
            o, hi, lo = opens.get(e, np.nan), highs.get(e, np.nan), lows.get(e, np.nan)
            adv = _adv(panel, i, e)
            gap_ok = m["entry_idx"] < i and np.isfinite(o)
            if m["be_from"] is not None and i >= m["be_from"]:
                m["stop"] = max(m["stop"], m["fill"])
            if np.isfinite(lo) and lo <= m["stop"]:
                ledger.sell(day, e, o if gap_ok and o < m["stop"] else m["stop"], adv,
                            "BREAKEVEN" if m["be_from"] is not None and m["stop"] >= m["fill"] else "STOP")
                continue
            if m["half"] is not None and m["be_from"] is None and np.isfinite(hi) and hi >= m["half"]:
                ledger.sell_half(e, o if gap_ok and o > m["half"] else m["half"], adv)
                m["be_from"] = i + 1
                st["halves"] += 1
            if np.isfinite(hi) and hi >= m["target"]:
                ledger.sell(day, e, o if gap_ok and o > m["target"] else m["target"], adv, "TARGET")
        ledger.mark(day, closes)
        if day >= end:
            continue
        for e in ledger.shares:
            if i - ledger.meta[e]["entry_idx"] + 1 >= time_stop:
                queued_exits.add(e)
        pending = {od["entity"] for od in live}
        for od in order_fn(i, day, set(ledger.shares) | pending):
            e = od[1]
            if not flt.allows(i, day, e):
                st["filtered_out"] += 1
                continue
            if od[0] == "market":
                _, e, ref, gap, pr = od
                rec = {"type": "market", "entity": e, "ref": ref, "max_gap": gap, "priority": pr}
            else:
                _, e, trig, gap, pr, valid, cancel = od
                rec = {"type": "stop", "entity": e, "ref": trig, "max_gap": gap, "priority": pr,
                       "expires_idx": i + valid, "cancel_below": cancel}
            if mode == "swing":
                stop = swing_stop(panel, piv, atr, i, e, min(rec["ref"], closes.get(e, np.nan)))
                if stop is None:
                    st["no_swing_low"] += 1
                    continue
                rec["stop"] = stop
            live.append(rec)
    eq, trades = _result_partial(ledger)
    return eq, trades, st
