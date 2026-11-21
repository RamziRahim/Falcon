"""
Falcon -- Falcon patterns audited and re-entered on half A, per docs/falcon_salvage_preregistration.md.

    python tests/run_falcon_salvage.py [W1] > data/falcon_salvage.log
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from backtesting.falcon_salvage import run_setups
from backtesting.pit_strategies import equal_weight_universe
from tests.half_a import load_half_a, report
from tests.run_mean_reversion import _nifty

PREREG = "docs/falcon_salvage_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31")}
VERSIONS = [("F_REF", False, "pivot_stop", "falcon", "falcon"), ("F_CC", False, "clean_close", "falcon", "falcon"),
            ("F_MOM", True, "pivot_stop", "falcon", "falcon"), ("F_MOM_CC", True, "clean_close", "falcon", "falcon"),
            ("F_CC_W", False, "clean_close", "atr3", "r3"), ("F_MOM_CC_W", True, "clean_close", "atr3", "r3")]
ONLY = sys.argv[1:]
PAT = {"is_vcp_breakout": "VCP", "is_ascending_triangle_breakout": "Asc. triangle",
       "is_flat_base_breakout": "Flat base", "is_bull_flag_breakout": "Bull flag"}


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    panel = load_half_a()
    nifty, src = _nifty()
    setups = pd.concat([pd.read_parquet("data/pit/falcon_setups_2008-01-01_2017-12-31.parquet"),
                        pd.read_parquet("data/pit/falcon_setups_2019-01-01_2026-10-30.parquet")])
    cols = {e: j for j, e in enumerate(panel.close.columns)}
    pos = {d: k for k, d in enumerate(panel.sessions)}
    setups = setups[setups.entity_id.isin(cols)].copy()
    setups["t"] = setups.scan_date.map(lambda d: pos.get(pd.Timestamp(d)))
    setups = setups.dropna(subset=["t"])
    setups["t"] = setups.t.astype(int)
    c = panel.close
    C, H, L = c.to_numpy(float), panel.high.to_numpy(float), panel.low.to_numpy(float)
    SMA50 = c.rolling(50, min_periods=50).mean().to_numpy(float)
    SMA200 = c.rolling(200, min_periods=200).mean().to_numpy(float)
    HI52 = panel.high.rolling(252, min_periods=200).max().to_numpy(float)
    MOM = (c / c.shift(126) - 1).to_numpy(float)
    # momentum rank among the universe on each scan date
    ranks = {}
    for t in setups.t.unique():
        mem = [cols[e] for e in panel.universe_on(panel.sessions[t]) if e in cols]
        m = pd.Series(MOM[t, mem], index=[c.columns[j] for j in mem]).dropna()
        ranks[t] = m.rank(pct=True)
    setups["mom_rank"] = [ranks[t].get(e, np.nan) for t, e in zip(setups.t, setups.entity_id)]
    setups["sort_key"] = setups.priority * 10 + setups.distance
    # sanity flags
    fl = {k: [] for k in ("N_UP", "PIV_X", "PIV_X3", "CRASH", "WIDE", "FAR")}
    for r in setups.itertuples():
        t, j = r.t, cols[r.entity_id]
        x = C[t, j]
        fl["N_UP"].append(not (x > SMA200[t, j] and SMA50[t, j] > SMA200[t, j]))
        fl["PIV_X"].append(bool(np.nanmax(H[t - 19: t + 1, j]) > r.pivot * 1.005))
        fl["PIV_X3"].append(bool(np.nanmax(H[t - 19: t + 1, j]) > r.pivot * 1.03))
        cc = C[t - 60: t + 1, j]
        dd = np.nanmin(cc / np.fmax.accumulate(np.nan_to_num(cc, nan=-np.inf)) - 1)
        fl["CRASH"].append(bool(dd < -0.25))
        fl["WIDE"].append(bool(np.nanmax(H[t - 19: t + 1, j]) / np.nanmin(L[t - 19: t + 1, j]) - 1 > 0.20))
        fl["FAR"].append(bool(x < 0.75 * HI52[t, j]))
    for k, v in fl.items():
        setups[k] = v
    setups["ANY"] = setups[[k for k in fl if k != "PIV_X3"]].any(axis=1)
    setups["pname"] = setups.pattern.map(PAT)
    setups.to_parquet("data/falcon_salvage_setups_halfA.parquet")
    aud = open("data/falcon_salvage_audit.txt", "w", encoding="utf-8")
    aud.write("=== Part 2: detection sanity flags (half A, all scan dates) ===\n")
    tab = setups.groupby("pname")[list(fl) + ["ANY"]].mean() * 100
    tab["detections"] = setups.groupby("pname").size()
    aud.write(tab.round(1).to_string() + "\n")
    allrow = setups[list(fl) + ["ANY"]].mean() * 100
    aud.write("ALL " + "  ".join(f"{k} {v:.1f}%" for k, v in allrow.items()) + f"  detections {len(setups)}\n")
    print(tab.round(1).to_string(), flush=True)

    out = open("data/falcon_salvage_result.txt" if not ONLY else "data/falcon_salvage_smoke.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; half A; Falcon setups re-entered\n")
    ref_info = []
    for code, mom, entry, sm, tm in VERSIONS:
        for w, (a, b) in WINDOWS.items():
            if ONLY and w not in ONLY:
                continue
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            su = setups[setups.mom_rank >= 0.80] if mom else setups
            info = []
            eq, tr, st = run_setups(panel, su, a, b, entry, sm, tm, info=info)
            tr.to_csv(f"data/falcon_salvage_trades_{code}_{w}.csv", index=False)
            report(out, code, w, a, b, eq, tr, nifty, equal_weight_universe(panel, a, b), st)
            if code == "F_REF":
                inf = pd.DataFrame(info)
                closed = tr[tr.exit_reason != "OPEN_AT_END"].copy()
                closed["entry_date"] = pd.to_datetime(closed.entry_date)
                inf["entry_date"] = pd.to_datetime(inf.entry_date)
                ref_info.append(closed.merge(inf, on=["entity_id", "entry_date"], how="inner").assign(W=w))
    out.close()
    if ref_info:
        d = pd.concat(ref_info)
        d["net"] = d.pnl / d.cost_basis
        d = d.merge(setups[["entity_id", "pivot", "ANY"] + list(fl)].drop_duplicates(["entity_id", "pivot"]),
                    on=["entity_id", "pivot"], how="left")
        aud.write("\n=== Part 1: wick fakeouts on F_REF fills (buy-stop at pivot) ===\n")
        for w, g in [("W1+W2", d), ("W1", d[d.W == "W1"]), ("W2", d[d.W == "W2"])]:
            if g.empty:
                continue
            for nm, x in (("wick (closed below pivot)", g[g.wick_fakeout]), ("closed above pivot", g[~g.wick_fakeout])):
                aud.write(f"  {w:6s} {nm:28s} n {len(x):4d} ({len(x) / len(g) * 100:4.1f}%)  win {(x.net > 0).mean() * 100:5.1f}%  "
                          f"net {x.net.mean() * 100:+.2f}%  stop exits {(x.exit_reason == 'STOP').mean() * 100:5.1f}%  "
                          f"target exits {(x.exit_reason == 'TARGET').mean() * 100:5.1f}%\n")
        aud.write("  share of wick fills by pattern: " + str((d.groupby("pattern").wick_fakeout.mean() * 100).round(1).to_dict()) + "\n")
        aud.write("\n=== Part 2b: F_REF outcomes, flagged vs clean detections (W1+W2) ===\n")
        for k in list(fl) + ["ANY"]:
            a_, b_ = d[d[k] == True], d[d[k] == False]
            aud.write(f"  {k:6s} flagged n {len(a_):4d} win {(a_.net > 0).mean() * 100:5.1f}% net {a_.net.mean() * 100:+.2f}%  |  "
                      f"clean n {len(b_):4d} win {(b_.net > 0).mean() * 100:5.1f}% net {b_.net.mean() * 100:+.2f}%\n")
    aud.close()
    print(open("data/falcon_salvage_audit.txt").read())


if __name__ == "__main__":
    main()
