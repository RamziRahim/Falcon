"""
Falcon paper trading engine (docs/paper_trading_plan.md, frozen 2026-11-22).

Every run replays all tracks from day one over data/pit_v2 with the backtest functions
themselves (no separate paper logic), so a late or repeated run gives the same record.

    python paper/engine.py                 # through the last session in data/pit_v2
    python paper/engine.py 2026-12-15      # through a given session (replay / checks)

Writes, per track, paper/ledger/<track>/{equity,trades,positions}.csv; paper/orders/<date>.csv
(month-end momentum orders for the next open); paper/reports/<date>.md (the daily summary);
paper/state.json (last session, versions). Track 8 (IA's discretionary trades) is read from
paper/manual/track8_orders.csv.
"""
import sys
sys.path.insert(0, ".")

import json
import os
import subprocess
from datetime import datetime

import numpy as np
import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES
from backtesting.falcon_momentum_entries import run_fm_entries
from backtesting.falcon_salvage import run_setups_v2
from backtesting.pit_strategies import CostModel, Ledger, _adv, _result, make_panel, run_momentum
from backtesting.sector_strength import sector_strong
from backtesting.v3_scan import scan_setups
from backtesting.weekly_support import weekly_support_levels
from tests.run_falcon_v3_patterns import prep3
from tests.run_portfolio_combo import combine

PLAN = "docs/paper_trading_plan.md"
DATA = "data/pit_v2"
OUT = os.environ.get("PAPER_OUT", "paper")
# Day one per the frozen plan. PAPER_RANK_DAY / PAPER_DAY_ONE / PAPER_OUT exist only for the engine's
# own dry-run checks on past data (paper/check_engine.py); the live record never sets them.
RANK_DAY = pd.Timestamp(os.environ.get("PAPER_RANK_DAY", "2026-11-30"))   # first momentum ranking (close)
DAY_ONE = pd.Timestamp(os.environ.get("PAPER_DAY_ONE", "2026-12-01"))     # first fills
LOAD_FROM = pd.Timestamp("2022-01-01")     # history loaded for indicators (checked to reproduce full-history runs)
EXCLUSIONS = "data/pit_v2/ethical_exclusions.csv"
CLEARED = "paper/manual/new_listings_cleared.csv"   # IA-reviewed new listings: entity_id, excluded (true/false), note
TRACKS = {
    "T01_A10": "Monthly momentum (10% stop)",
    "T02_A10C": "Monthly momentum, no re-buy after a stop (shadow)",
    "T03_C_F_A": "Current mix, FM buys the confirming close",
    "T04_C_F_A_P3": "Three-way split, FM and patterns buy the confirming close",
    "T05_C_F_A_O": "Current mix, FM at the next open",
    "T06_C_F_A_P3O": "Three-way split, FM and patterns at the next open",
    "T07_C_F_A_H": "Current mix, FM on a buy-stop at the 20-day high",
    "T08_IA": "IA discretionary pullbacks (manual)",
    "T09_A10P": "Monthly momentum, half at open + half on the weekly pullback",
    "T10_M_SEC": "Monthly momentum + sector strength",
    "T11_A10_70": "Monthly momentum at 70% size",
}


def git_rev():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    except Exception:                                     # noqa: BLE001
        return "unknown"


def excluded_entities(universe: pd.DataFrame) -> tuple[set, list]:
    """Frozen ethical exclusions, plus every universe stock not in that list (a new listing)
    unless IA has cleared it in paper/manual/new_listings_cleared.csv."""
    exc = pd.read_csv(EXCLUSIONS)
    out = set(exc.loc[exc["excluded"], "entity_id"])
    known = set(exc["entity_id"])
    cleared = pd.read_csv(CLEARED) if os.path.exists(CLEARED) else pd.DataFrame(columns=["entity_id", "excluded"])
    cleared_ok = set(cleared.loc[~cleared["excluded"].astype(bool), "entity_id"])
    out |= set(cleared.loc[cleared["excluded"].astype(bool), "entity_id"])
    new = sorted(set(universe["entity_id"]) - known - set(cleared["entity_id"]))
    out |= set(new)
    out -= cleared_ok
    return out, new


def load(until=None):
    prices = pd.read_parquet(f"{DATA}/prices_adjusted.parquet", filters=[("Date", ">=", LOAD_FROM)])
    prices["Date"] = pd.to_datetime(prices["Date"])
    if until is not None:
        prices = prices[prices["Date"] <= until]
    uni = pd.read_parquet(f"{DATA}/universe_monthly.parquet")
    uni["month_end"] = pd.to_datetime(uni["month_end"])
    uni = uni[uni["month_end"] >= LOAD_FROM - pd.Timedelta(days=40)]
    if until is not None:
        uni = uni[uni["month_end"] <= until]
    excluded, new = excluded_entities(uni)
    uni_f = uni[~uni["entity_id"].isin(excluded)]
    panel = make_panel(prices, uni_f)
    ix = pd.read_parquet("data/pit_sources/indices_2000_2026.parquet")
    ix["Date"] = pd.to_datetime(ix["Date"])
    if until is not None:
        ix = ix[ix["Date"] <= until]
    nifty = ix[ix["Index"] == "NIFTY 50"].set_index("Date")["Close"].sort_index()
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    return panel, uni_f, nifty, indices, new


def last_trading_day_of_month(day: pd.Timestamp) -> bool:
    """True when no later weekday in the same month is an NSE trading day (paper/nse_holidays.csv)."""
    hol = set(pd.to_datetime(pd.read_csv("paper/nse_holidays.csv")["date"])) if os.path.exists("paper/nse_holidays.csv") else set()
    d = day + pd.Timedelta(days=1)
    while d.month == day.month:
        if d.weekday() < 5 and d not in hol:
            return False
        d += pd.Timedelta(days=1)
    return True


def run_tracks(panel, uni, nifty, indices, end):
    """All automatic tracks from day one to `end`, with the backtest functions. Momentum runs
    end one calendar day after the last session so that run_momentum also ranks at that
    session's close (its review needs day < end); no session lies in that extra day, so the
    record is unchanged, and the ranking is used only on a real month end."""
    out, st = {}, {}
    s = panel.sessions
    endm = end + pd.Timedelta(days=1)
    nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
    nifty_ok = (nf > nf.rolling(50, min_periods=50).mean()).to_numpy()
    st["A"] = {}
    A = run_momentum(panel, RANK_DAY, endm, stop_pct=0.10, stats=st["A"])
    out["T01_A10"] = A
    out["T02_A10C"] = run_momentum(panel, RANK_DAY, endm, stop_pct=0.10, skip_after_stop=True)
    out["T09_A10P"] = run_momentum(panel, RANK_DAY, endm, stop_pct=0.10, add_frac=0.5,
                                   add_level=weekly_support_levels(panel, ("S1",))["S1"])
    st["SEC"] = {}
    out["T10_M_SEC"] = run_momentum(panel, RANK_DAY, endm, stop_pct=0.10, allowed=sector_strong(panel, indices, nifty), stats=st["SEC"])
    st["A70"] = {}
    out["T11_A10_70"] = run_momentum(panel, RANK_DAY, endm, stop_pct=0.10, gauge_up=np.zeros(len(s), dtype=bool),
                                     down_level=0.7, stats=st["A70"])
    if end < DAY_ONE:                                    # the ranking day itself: FM / P3 start on day one
        for code in ("T03_C_F_A", "T04_C_F_A_P3", "T05_C_F_A_O", "T06_C_F_A_P3O", "T07_C_F_A_H"):
            out[code] = None
        return out, st, pd.DataFrame()
    fm, fmo, fmh = (run_fm_entries(panel, DAY_ONE, end, nifty, indices, mode, r_mult=3.0, **kw)[:2]
                    for mode, kw in (("closebuy", {}), ("closebuy", {"next_open": True}), ("high20", {})))
    setups = scan_setups(panel, uni, DAY_ONE, end)
    real = prep3(panel, setups)
    real = real[real.verdict == "REAL_PATTERN"] if len(real) else real
    p3, p3o = ((run_setups_v2(panel, real, DAY_ONE, end, nifty_ok, stop_rule="setup", **kw)[:2] if len(real) else None)
               for kw in ({}, {"entry": "next_open"}))
    empty = lambda: (pd.DataFrame({"equity": [1_000_000.0], "gross_exposure": [0.0]},
                                  index=pd.DatetimeIndex([DAY_ONE], name="Date")), pd.DataFrame())
    p3 = p3 or empty()
    p3o = p3o or empty()
    out["T03_C_F_A"] = combine({"F": fm, "A": A}, "FA", True)
    out["T04_C_F_A_P3"] = combine({"F": fm, "A": A, "P": p3}, "FAP", True)
    out["T05_C_F_A_O"] = combine({"F": fmo, "A": A}, "FA", True)
    out["T06_C_F_A_P3O"] = combine({"F": fmo, "A": A, "P": p3o}, "FAP", True)
    out["T07_C_F_A_H"] = combine({"F": fmh, "A": A}, "FA", True)
    return out, st, setups


def manual_track(panel, end):
    """Track 8: IA's logged orders (date, action BUY/SELL, symbol, limit, stop, target, note).
    An order without a limit fills at the next session's open; with a limit, at min(open, limit)
    if that session's low reaches it (else it lapses). Stops/targets checked daily like the backtests."""
    path = "paper/manual/track8_orders.csv"
    if not os.path.exists(path):
        return None
    od = pd.read_csv(path, parse_dates=["date"])
    if od.empty:
        return None
    sym2e = {v: k for k, v in panel.symbol.items()}
    ledger = Ledger(CostModel())
    s = panel.sessions
    for i, day in enumerate(s):
        if day < DAY_ONE or day > end:
            continue
        o, h, l = panel.open.iloc[i], panel.high.iloc[i], panel.low.iloc[i]
        prev = s[i - 1] if i else day
        for _, r in od[(od["date"] >= prev) & (od["date"] < day)].iterrows():
            e = sym2e.get(str(r["symbol"]).upper())
            if e is None or not np.isfinite(o.get(e, np.nan)):
                continue
            lim = r.get("limit")
            px = o[e] if pd.isna(lim) else (min(o[e], lim) if l.get(e, np.inf) <= lim else None)
            if px is None:
                continue
            if r["action"].upper() == "BUY" and e not in ledger.shares:
                eq = ledger.cash + sum(ledger.value(x, o) for x in ledger.shares)
                ledger.buy(day, e, px, min(eq / 10, ledger.cash * 0.999), _adv(panel, i, e),
                           {"stop": r.get("stop") if pd.notna(r.get("stop")) else None,
                            "target": r.get("target") if pd.notna(r.get("target")) else None, "entry_idx": i})
            elif r["action"].upper() == "SELL" and e in ledger.shares:
                ledger.sell(day, e, px, _adv(panel, i, e), "MANUAL")
        for e in list(ledger.shares):
            m = ledger.meta[e]
            if m.get("stop") is not None and l.get(e, np.inf) <= m["stop"]:
                gap = m["entry_idx"] < i and o.get(e, np.inf) < m["stop"]
                ledger.sell(day, e, o[e] if gap else m["stop"], _adv(panel, i, e), "STOP")
            elif m.get("target") is not None and h.get(e, -np.inf) >= m["target"]:
                gap = m["entry_idx"] < i and o.get(e, -np.inf) > m["target"]
                ledger.sell(day, e, o[e] if gap else m["target"], _adv(panel, i, e), "TARGET")
        ledger.mark(day, panel.close.iloc[i])
    return _result(ledger) if ledger.equity else None


def momentum_orders(panel, stats, results, last_i):
    """New buys / sells for the next open when the last session is a review day (month end)."""
    if not last_trading_day_of_month(panel.sessions[last_i]):
        return None
    tg = stats.get("targets", {}).get(last_i)
    if tg is None:
        return None
    _, tr = results
    held = set(tr.loc[tr["exit_reason"] == "OPEN_AT_END", "entity_id"]) if len(tr) else set()
    sym = panel.symbol
    rows = [{"action": "BUY", "symbol": sym.get(e, e), "entity_id": e} for e in sorted(tg - held, key=lambda x: sym.get(x, x))]
    rows += [{"action": "SELL", "symbol": sym.get(e, e), "entity_id": e} for e in sorted(held - tg, key=lambda x: sym.get(x, x))]
    return pd.DataFrame(rows)


def write(panel, out, nifty, end, st, new, setups):
    sym = panel.symbol
    day = end.date()
    os.makedirs(f"{OUT}/reports", exist_ok=True)
    os.makedirs(f"{OUT}/orders", exist_ok=True)
    lines = [f"# Falcon paper trading — {day}", "",
             f"Engine commit {git_rev()}; data through {day}; day one {DAY_ONE.date()}.", ""]
    n0 = nifty[nifty.index >= RANK_DAY]
    nret = (n0.iloc[-1] / n0.iloc[0] - 1) * 100 if len(n0) > 1 else 0.0
    lines += [f"Nifty 50 since the {RANK_DAY.date()} close: {nret:+.2f}%", "", "| Track | Equity (₹) | Since start | Open positions |",
              "| --- | --- | --- | --- |"]
    for code, res in out.items():
        if res is None:
            continue
        eq, tr = res
        d = f"{OUT}/ledger/{code}"
        os.makedirs(d, exist_ok=True)
        eq.to_csv(f"{d}/equity.csv")
        if len(tr):
            t = tr.copy()
            t.insert(1, "symbol", t["entity_id"].map(lambda e: sym.get(e, e)))
            t[t["exit_reason"] != "OPEN_AT_END"].to_csv(f"{d}/trades.csv", index=False)
            t[t["exit_reason"] == "OPEN_AT_END"].to_csv(f"{d}/positions.csv", index=False)
            n_open = int((t["exit_reason"] == "OPEN_AT_END").sum())
        else:
            n_open = 0
        e_last = float(eq["equity"].iloc[-1])
        lines.append(f"| {code} {TRACKS[code]} | {e_last:,.0f} | {100 * (e_last / 1_000_000 - 1):+.2f}% | {n_open} |")
    last_i = len(panel.sessions) - 1
    orders = []
    for code, key in (("T01_A10", "A"), ("T10_M_SEC", "SEC"), ("T11_A10_70", "A70")):
        o = momentum_orders(panel, st.get(key, {}), out[code], last_i)
        if o is not None and len(o):
            o.insert(0, "track", code)
            orders.append(o)
    if orders:
        od = pd.concat(orders, ignore_index=True)
        od.to_csv(f"{OUT}/orders/{day}.csv", index=False)
        lines += ["", f"## Month-end momentum orders for the next open ({len(od)})", ""]
        for code, g in od.groupby("track"):
            buys = ", ".join(g.loc[g.action == "BUY", "symbol"])
            sells = ", ".join(g.loc[g.action == "SELL", "symbol"])
            lines.append(f"- **{code}** buy: {buys or '—'}; sell: {sells or '—'}")
        lines.append("")
        lines.append("Tracks 2, 3–7 and 9 use the T01 momentum list (T02 skips names stopped this month; T09 buys half now).")
    if new:
        lines += ["", f"## New listings in the universe, not yet classified ({len(new)}) — unbuyable until reviewed", "",
                  ", ".join(sym.get(e, e) for e in new)]
    lines += ["", f"v3 setups scanned since day one: {len(setups)}"]
    with open(f"{OUT}/reports/{day}.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    with open(f"{OUT}/state.json", "w", encoding="utf-8") as fh:
        json.dump({"last_session": str(day), "engine_commit": git_rev(), "written": datetime.now().isoformat(timespec="seconds"),
                   "new_listings_unreviewed": len(new)}, fh, indent=1)
    return "\n".join(lines)


def main():
    if "**Status: FROZEN" not in open(PLAN, encoding="utf-8").read():
        raise SystemExit(f"{PLAN} is not frozen.")
    until = pd.Timestamp(sys.argv[1]) if len(sys.argv) > 1 else None
    panel, uni, nifty, indices, new = load(until)
    end = panel.sessions[-1]
    if end < RANK_DAY:
        raise SystemExit(f"data ends {end.date()}, before the first ranking day {RANK_DAY.date()}")
    out, st, setups = run_tracks(panel, uni, nifty, indices, end)
    out["T08_IA"] = manual_track(panel, end)
    print(write(panel, out, nifty, end, st, new, setups))


if __name__ == "__main__":
    main()
