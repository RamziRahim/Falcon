"""
===============================================================================
Falcon AI Swing Trading Platform — Conviction score for position sizing
===============================================================================
Script      : conviction.py
Package     : Scoring

Implements the 0-3 conviction score in docs/conviction_sizing_preregistration.md.
Nothing here is tuned; every number comes from that document.

Point in time: a trade bought on `entry_date` is scored with data up to and
including the LAST SESSION BEFORE `entry_date` (called t0). That is the
latest data known both for next-open entries (signal at the t0 close) and for
clean-close entries (decided at ~3:20 pm on entry_date, before that day's
volume and NSE's delivery file exist).

Points (each 0 or 1):
  VP   volume profile of the 60 sessions to t0 (turnover-weighted, 50 bins,
       70% value area): close(t0) above the value-area high AND at most 10% of
       the profile's turnover lies in (close, 1.10 x close]  ("clear air").
  DLV  delivery % on t0 >= 1.3 x its mean over the 20 sessions before t0.
  ACC  over the 10 sessions to t0, delivered value on up-close days exceeds
       delivered value on down-close days.

Buckets and size multiplier on the strategy's normal size: score 0 -> 0.75,
1 -> 1.0, 2-3 -> 1.5.
===============================================================================
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

VP_SESSIONS, VP_BINS, VP_VALUE_AREA = 60, 50, 0.70
VP_CLEAR_BAND, VP_CLEAR_MAX_SHARE = 0.10, 0.10
DLV_LEN, DLV_MULT, DLV_MIN_VALID = 20, 1.3, 15
ACC_LEN, ACC_MIN_VALID = 10, 7
MULTIPLIER = {0: 0.75, 1: 1.0, 2: 1.5, 3: 1.5}
BUCKETS = {0: "0", 1: "1", 2: "2-3", 3: "2-3"}


# --------------------------------------------------------------------------- volume profile
@dataclass
class Profile:
    edges: np.ndarray          # VP_BINS + 1 bin edges
    weight: np.ndarray         # turnover per bin
    poc: float                 # mid-price of the heaviest bin
    val: float                 # value-area low (lower edge)
    vah: float                 # value-area high (upper edge)


def volume_profile(high, low, weight, bins: int = VP_BINS, value_area: float = VP_VALUE_AREA) -> Profile | None:
    """Spread each session's weight evenly over its high-low range, then find the
    point of control and the value area (grown one bin at a time from the point of
    control, always taking the heavier neighbour, until it holds `value_area`)."""
    h, l, w = (np.asarray(x, float) for x in (high, low, weight))
    ok = np.isfinite(h) & np.isfinite(l) & np.isfinite(w) & (w > 0) & (h >= l)
    h, l, w = h[ok], l[ok], w[ok]
    if len(w) == 0:
        return None
    lo, hi = l.min(), h.max()
    if not hi > lo:
        return None
    edges = np.linspace(lo, hi, bins + 1)
    out = np.zeros(bins)
    for hh, ll, ww in zip(h, l, w):
        if hh == ll:
            out[min(np.searchsorted(edges, ll, side="right") - 1, bins - 1)] += ww
            continue
        overlap = np.clip(np.minimum(edges[1:], hh) - np.maximum(edges[:-1], ll), 0, None)
        out += ww * overlap / (hh - ll)
    poc = int(np.argmax(out))
    a = b = poc
    need, have = value_area * out.sum(), out[poc]
    while have < need and (a > 0 or b < bins - 1):
        below = out[a - 1] if a > 0 else -1.0
        above = out[b + 1] if b < bins - 1 else -1.0
        if above >= below:
            b += 1
            have += above
        else:
            a -= 1
            have += below
    return Profile(edges, out, (edges[poc] + edges[poc + 1]) / 2, edges[a], edges[b + 1])


def share_between(p: Profile, lo: float, hi: float) -> float:
    """Share of the profile's weight in the price band (lo, hi], prorated within bins."""
    total = p.weight.sum()
    if total <= 0 or hi <= lo:
        return 0.0
    width = p.edges[1:] - p.edges[:-1]
    overlap = np.clip(np.minimum(p.edges[1:], hi) - np.maximum(p.edges[:-1], lo), 0, None)
    return float((p.weight * overlap / width).sum() / total)


# --------------------------------------------------------------------------- points
def vp_point(high, low, close, turnover) -> tuple[int, dict]:
    """Inputs are the VP_SESSIONS sessions ending at t0 (last value = t0)."""
    prof = volume_profile(high, low, turnover)
    c = float(np.asarray(close, float)[-1])
    if prof is None or not np.isfinite(c):
        return 0, {"vp_ok": False}
    above = c > prof.vah
    overhead = share_between(prof, c, c * (1 + VP_CLEAR_BAND))
    clear = overhead <= VP_CLEAR_MAX_SHARE
    return int(above and clear), {"vp_ok": True, "poc": prof.poc, "vah": prof.vah, "above_value": bool(above),
                                  "overhead_share": overhead}


def delivery_point(deliv_pct) -> tuple[int, dict]:
    """Input: delivery % for the DLV_LEN sessions before t0 followed by t0 (length DLV_LEN + 1)."""
    d = np.asarray(deliv_pct, float)
    today, prior = d[-1], d[:-1][-DLV_LEN:]
    valid = np.isfinite(prior).sum()
    if not np.isfinite(today) or valid < DLV_MIN_VALID:
        return 0, {"dlv_ok": False}
    base = np.nanmean(prior)
    return int(base > 0 and today >= DLV_MULT * base), {"dlv_ok": True, "deliv_pct": today, "deliv_base": base}


def accumulation_point(close_prev_and_window, deliv_pct, turnover) -> tuple[int, dict]:
    """Inputs: closes for ACC_LEN + 1 sessions (one before the window, then the window),
    delivery % and turnover for the ACC_LEN sessions of the window (ending at t0)."""
    c = np.asarray(close_prev_and_window, float)
    chg = c[1:] - c[:-1]
    dv = np.asarray(deliv_pct, float) / 100.0 * np.asarray(turnover, float)
    ok = np.isfinite(chg) & np.isfinite(dv) & (chg != 0)
    if ok.sum() < ACC_MIN_VALID:
        return 0, {"acc_ok": False}
    up, down = dv[ok & (chg > 0)].sum(), dv[ok & (chg < 0)].sum()
    return int(up > down), {"acc_ok": True, "acc_up": up, "acc_down": down}


def multiplier(score: int) -> float:
    return MULTIPLIER[int(score)]


# --------------------------------------------------------------------------- panel scoring
@dataclass
class ConvictionData:
    """Wide Date x entity frames on one session calendar."""
    high: pd.DataFrame
    low: pd.DataFrame
    close: pd.DataFrame
    turnover: pd.DataFrame
    deliv_pct: pd.DataFrame          # NaN where no delivery figure (non-EQ series, missing file)

    @property
    def sessions(self) -> pd.DatetimeIndex:
        return self.close.index


def delivery_wide(prices: pd.DataFrame, delivery: pd.DataFrame, sessions: pd.DatetimeIndex, entities) -> pd.DataFrame:
    """Map NSE delivery rows (Date, Symbol, Series, DelivPct) to entity_id through the
    price rows' own (Date, Symbol). Only EQ-series delivery counts: BE/BZ are
    trade-for-trade (always ~100% delivery) and would fake the signal."""
    d = delivery[delivery["Series"].astype(str).str.strip() == "EQ"][["Date", "Symbol", "DelivPct"]].copy()
    d["Date"] = pd.to_datetime(d["Date"])
    d["Symbol"] = d["Symbol"].astype(str).str.strip()
    p = prices[["Date", "Symbol", "entity_id"]].copy()
    p["Date"] = pd.to_datetime(p["Date"])
    if "Series" in prices.columns:
        p = p[prices["Series"].astype(str).str.strip() == "EQ"]
    m = p.merge(d, on=["Date", "Symbol"], how="inner")
    m = m[m["entity_id"].isin(set(entities))]
    wide = m.pivot_table(index="Date", columns="entity_id", values="DelivPct", aggfunc="first")
    return wide.reindex(index=sessions, columns=list(entities))


def make_conviction_data(panel, prices: pd.DataFrame, delivery: pd.DataFrame | None) -> ConvictionData:
    """`panel` is a backtesting.pit_strategies.Panel; `prices` the long prices_adjusted frame."""
    ents = list(panel.close.columns)
    if delivery is None or delivery.empty:
        dw = pd.DataFrame(np.nan, index=panel.sessions, columns=ents)
    else:
        dw = delivery_wide(prices, delivery, panel.sessions, ents)
    return ConvictionData(panel.high, panel.low, panel.close, panel.turnover, dw)


def score_asof(data: ConvictionData, entity, t0_idx: int) -> dict:
    """Score `entity` with data up to and including session index t0_idx."""
    if entity not in data.close.columns or t0_idx < 1:
        return {"score": 0, "vp": 0, "dlv": 0, "acc": 0, "vp_ok": False, "dlv_ok": False, "acc_ok": False}
    j = data.close.columns.get_loc(entity)

    def col(frame, a, b):
        return frame.iloc[max(0, a): b + 1, j].to_numpy(float)

    # VP: last VP_SESSIONS sessions where the stock traded, ending at t0
    hi_all = col(data.high, 0, t0_idx)
    traded = np.where(np.isfinite(hi_all))[0]
    sel = traded[-VP_SESSIONS:]
    if len(sel) >= VP_SESSIONS and sel[-1] == t0_idx:
        vp, vinfo = vp_point(hi_all[sel], col(data.low, 0, t0_idx)[sel], col(data.close, 0, t0_idx)[sel],
                             col(data.turnover, 0, t0_idx)[sel])
    else:
        vp, vinfo = 0, {"vp_ok": False}
    dlv, dinfo = delivery_point(col(data.deliv_pct, t0_idx - DLV_LEN, t0_idx))
    acc, ainfo = accumulation_point(col(data.close, t0_idx - ACC_LEN, t0_idx),
                                    col(data.deliv_pct, t0_idx - ACC_LEN + 1, t0_idx),
                                    col(data.turnover, t0_idx - ACC_LEN + 1, t0_idx))
    score = vp + dlv + acc
    return {"score": score, "vp": vp, "dlv": dlv, "acc": acc, **vinfo, **dinfo, **ainfo}


def score_trades(data: ConvictionData, trades: pd.DataFrame) -> pd.DataFrame:
    """One row per closed trade: net return after costs, the three points, score, bucket
    and size multiplier. t0 = last session strictly before entry_date."""
    if trades.empty:
        return pd.DataFrame()
    t = trades[trades["exit_reason"] != "OPEN_AT_END"].copy()
    t["entry_date"] = pd.to_datetime(t["entry_date"])
    t["net"] = t["pnl"] / t["cost_basis"]
    idx = data.sessions.searchsorted(t["entry_date"].to_numpy(), side="left") - 1
    rows = [score_asof(data, e, int(i)) for e, i in zip(t["entity_id"], idx)]
    s = pd.DataFrame(rows, index=t.index)
    out = pd.concat([t[["entity_id", "entry_date", "exit_date", "exit_reason", "cost_basis", "pnl", "net"]],
                     s[["score", "vp", "dlv", "acc", "vp_ok", "dlv_ok", "acc_ok"]]], axis=1)
    out["t0"] = [data.sessions[i] if i >= 0 else pd.NaT for i in idx]
    out["bucket"] = out["score"].map(BUCKETS)
    out["mult"] = out["score"].map(MULTIPLIER)
    return out.reset_index(drop=True)


# --------------------------------------------------------------------------- judgement
MIN_SPREAD_PP, MIN_TOP_TRADES, MIN_WELCH_T = 1.0, 30, 1.5


def bucket_table(scored: pd.DataFrame) -> pd.DataFrame:
    g = scored.groupby("bucket")["net"]
    tab = pd.DataFrame({"trades": g.size(), "mean_net_pct": g.mean() * 100, "win_pct": g.apply(lambda x: (x > 0).mean() * 100)})
    return tab.reindex(["0", "1", "2-3"])


def welch_t(a: pd.Series, b: pd.Series) -> float:
    a, b = a.dropna(), b.dropna()
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return float((a.mean() - b.mean()) / se) if se > 0 else float("nan")


def judge_buckets(scored: pd.DataFrame) -> dict:
    """The four checks of the pre-registration for one engine, sample and window."""
    tab = bucket_table(scored)
    m = tab["mean_net_pct"]
    n_top = int(tab.loc["2-3", "trades"]) if np.isfinite(tab.loc["2-3", "trades"]) else 0
    spread = m.loc["2-3"] - m.loc["0"]
    top = scored["bucket"] == "2-3"
    t = welch_t(scored.loc[top, "net"], scored.loc[~top, "net"])
    checks = {
        "mean net rises 0 <= 1 <= 2-3": bool(np.isfinite(m).all() and m.loc["0"] <= m.loc["1"] <= m.loc["2-3"]),
        f"bucket 2-3 beats 0 by >= {MIN_SPREAD_PP:.1f}pp a trade": bool(np.isfinite(spread) and spread >= MIN_SPREAD_PP),
        f"bucket 2-3 has >= {MIN_TOP_TRADES} trades": n_top >= MIN_TOP_TRADES,
        f"Welch t (2-3 vs rest) >= {MIN_WELCH_T}": bool(np.isfinite(t) and t >= MIN_WELCH_T),
    }
    w = scored["mult"]
    return {"table": tab, "spread_pp": spread, "welch_t": t, "checks": checks, "passed": all(checks.values()),
            "mean_net_pct": scored["net"].mean() * 100,
            "sized_mean_net_pct": float((scored["net"] * w).sum() / w.sum() * 100) if len(scored) else float("nan"),
            "delivery_missing_pct": float((~scored["dlv_ok"]).mean() * 100) if len(scored) else float("nan"),
            "vp_missing_pct": float((~scored["vp_ok"]).mean() * 100) if len(scored) else float("nan")}
