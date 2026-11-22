"""
Falcon -- dynamic capital allocation across the ten automatic paper-trading tracks, per
docs/dynamic_allocation_preregistration.md. Data: data/pit_v2, no ethical filter.

    PYTHONHASHSEED=0 python tests/run_dynamic_allocation.py > data/dynamic_allocation.log
"""
import sys
sys.path.insert(0, ".")

import gc
import os

import numpy as np
import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES
from backtesting.falcon_momentum_entries import run_fm_entries
from backtesting.falcon_salvage import run_setups_v2
from backtesting.pit_strategies import _cagr, _max_dd, equal_weight_universe, run_momentum
from backtesting.sector_strength import sector_strong
from backtesting.weekly_support import weekly_support_levels
from tests.half_a import report
from tests.run_a_exposure import ref_numbers
from tests.run_ethical_filter_history import SETUPS, load
from tests.run_falcon_v3_patterns import prep3
from tests.run_portfolio_combo import combine

PREREG = "docs/dynamic_allocation_preregistration.md"
WINDOWS = {"H0": ("2001-01-01", "2006-12-31"), "W2": ("2008-01-01", "2017-12-31"), "W1": ("2019-01-01", "2026-10-30")}
JUDGED_WINDOWS = ("W2", "W1")
REF_FILE = "data/buystop_mix_result.txt"
REF_CODES = ("A10", "C_F_A", "C_F_A_O", "C_F_A_H")
SLEEVES = ("A10", "A10C", "A10P", "M_SEC", "A10_70", "C_F_A", "C_F_A_O", "C_F_A_H", "C_F_A_P3", "C_F_A_P3O")
LOOKBACK, MIN_HIST, DD_FLOOR, COST = 252, 126, 0.05, 0.0025
START = 1_000_000.0


def scores(hist: pd.DataFrame) -> pd.Series:
    """Reward per unit of risk over the look-back: max(return, 0) / max(max drawdown, 5%)."""
    h = hist.iloc[-(LOOKBACK + 1):]
    ret = h.iloc[-1] / h.iloc[0] - 1
    mdd = -(h / h.cummax() - 1).min()
    return ret.clip(lower=0) / mdd.clip(lower=DD_FLOOR)


def weights(rule: str, hist: pd.DataFrame) -> pd.Series:
    n = hist.shape[1]
    ew = pd.Series(1.0 / n, index=hist.columns)
    if len(hist) < MIN_HIST:
        return ew
    if rule == "EW":
        return ew
    if rule == "DA_IV":
        sd = hist.iloc[-(LOOKBACK + 1):].pct_change().std()
        inv = 1.0 / sd.replace(0, np.nan)
        return (inv / inv.sum()).fillna(0) if inv.notna().any() else ew
    sc = scores(hist)
    if sc.sum() <= 0:
        return ew
    if rule == "DA_RR":
        return 0.5 * ew + 0.5 * sc / sc.sum()
    if rule == "DA_TOP3":
        top = sc.sort_values(ascending=False, kind="mergesort").index[:3]
        return pd.Series(np.where(hist.columns.isin(top), 1 / 3, 0.0), index=hist.columns)
    raise ValueError(rule)


def allocate(curves: pd.DataFrame, rule: str):
    """Monthly re-split of one pot across the sleeves' equity curves. Weights set at the last session
    of each month from data up to that close; holdings drift in between; 0.25% on every rupee moved."""
    days = curves.index
    month_end = pd.Series(days.to_period("M"), index=days)
    is_me = (month_end != month_end.shift(-1)).to_numpy()
    w0 = weights(rule, curves.iloc[:1])
    units = w0 * START / curves.iloc[0]
    vals, moved, wsum, nreb = [], 0.0, pd.Series(0.0, index=curves.columns), 0
    for i, d in enumerate(days):
        px = curves.iloc[i]
        hold = units * px
        v = float(hold.sum())
        if is_me[i] and i < len(days) - 1:
            w = weights(rule, curves.iloc[: i + 1])
            target = w * v
            delta = float((target - hold).abs().sum())
            cost = COST * delta
            moved += delta / v
            v -= cost
            units = w * v / px
            wsum += w
            nreb += 1
        vals.append(v)
    eq = pd.Series(vals, index=days)
    years = (days[-1] - days[0]).days / 365.25
    return eq, moved / years, (wsum / max(nreb, 1))


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    ix = pd.read_parquet("data/pit_sources/indices_2000_2026.parquet")
    ix["Date"] = pd.to_datetime(ix["Date"])
    nifty = ix[ix["Index"] == "NIFTY 50"].set_index("Date")["Close"].sort_index()
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    setups = {w: pd.concat([pd.read_parquet(f) for f in SETUPS[w]]) for w in WINDOWS}
    out = open("data/dynamic_allocation_result.txt", "w", encoding="utf-8")
    out.write("Dynamic allocation across the ten automatic tracks (docs/dynamic_allocation_preregistration.md).\n"
              "Data data/pit_v2, no ethical filter. Sleeve blocks are CODE@SAMPLE; allocation rows follow each window.\n")
    res = {}
    for sample in ("ALL", "A", "B"):
        panel = load(sample, None)
        s = panel.sessions
        nf = nifty.reindex(nifty.index.union(s)).ffill().reindex(s)
        nifty_ok = (nf > nf.rolling(50, min_periods=50).mean()).to_numpy()
        allowed = sector_strong(panel, indices, nifty)
        s1 = weekly_support_levels(panel, ("S1",))["S1"]
        for w, (a, b) in WINDOWS.items():
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            s3 = prep3(panel, setups[w])
            real = s3[s3.verdict == "REAL_PATTERN"]
            ew_u = equal_weight_universe(panel, a, b)
            sl, rep, curves = {}, {}, {}

            def rec(code, eq, tr):
                rep[code] = report(out, f"{code}@{sample}", w, a, b, eq, tr, nifty, ew_u)
                curves[code] = eq["equity"]

            sl["A"] = run_momentum(panel, a, b, stop_pct=0.10)
            rec("A10", *sl["A"])
            rec("A10C", *run_momentum(panel, a, b, stop_pct=0.10, skip_after_stop=True))
            rec("A10P", *run_momentum(panel, a, b, stop_pct=0.10, add_frac=0.5, add_level=s1))
            rec("M_SEC", *run_momentum(panel, a, b, stop_pct=0.10, allowed=allowed))
            rec("A10_70", *run_momentum(panel, a, b, stop_pct=0.10, gauge_up=np.zeros(len(s), dtype=bool), down_level=0.7))
            f = run_fm_entries(panel, a, b, nifty, indices, "closebuy", r_mult=3.0)[:2]
            fo = run_fm_entries(panel, a, b, nifty, indices, "closebuy", r_mult=3.0, next_open=True)[:2]
            fh = run_fm_entries(panel, a, b, nifty, indices, "high20", r_mult=3.0)[:2]
            p = run_setups_v2(panel, real, a, b, nifty_ok, stop_rule="setup")[:2]
            po = run_setups_v2(panel, real, a, b, nifty_ok, stop_rule="setup", entry="next_open")[:2]
            rec("C_F_A", *combine({"F": f, "A": sl["A"]}, "FA", True))
            rec("C_F_A_O", *combine({"F": fo, "A": sl["A"]}, "FA", True))
            rec("C_F_A_H", *combine({"F": fh, "A": sl["A"]}, "FA", True))
            rec("C_F_A_P3", *combine({"F": f, "A": sl["A"], "P": p}, "FAP", True))
            rec("C_F_A_P3O", *combine({"F": fo, "A": sl["A"], "P": po}, "FAP", True))
            if sample == "ALL":
                for code in REF_CODES:
                    want = ref_numbers(REF_FILE, f"{code}@ALL", w)
                    got = (float(rep[code]["cagr_pct"]), float(rep[code]["max_drawdown_pct"]))
                    ok = all(abs(x - y) <= 0.05 for x, y in zip(want, got))
                    line = f"  reference check {code}@ALL {w}: file {want} run {got} -> {'MATCH' if ok else 'MISMATCH'}"
                    print(line, flush=True)
                    out.write(line + "\n")
                    if not ok:
                        out.close()
                        raise SystemExit(f"Reference {code} {w} does not reproduce {REF_FILE}; stopping.")
            cv = pd.DataFrame(curves)[list(SLEEVES)].sort_index().ffill().dropna()
            cv = cv.div(cv.iloc[0])
            out.write(f"\n--- ALLOCATION {sample} {w} {cv.index[0].date()} -> {cv.index[-1].date()} ---\n")
            for rule in ("EW", "DA_RR", "DA_IV", "DA_TOP3"):
                eq, turn, avgw = allocate(cv, rule)
                r = {"cagr_pct": round(_cagr(eq), 2), "max_drawdown_pct": round(_max_dd(eq), 2),
                     "grew_lakh": round(10 * eq.iloc[-1] / eq.iloc[0], 2), "turnover_pa": round(turn, 2)}
                res[(sample, w, rule)] = r
                out.write(f"  {rule:8s} CAGR {r['cagr_pct']:7.2f}  maxDD {r['max_drawdown_pct']:7.2f}  10L->{r['grew_lakh']:8.2f}L  "
                          f"moved/yr {r['turnover_pa']:.2f}x  avg weights "
                          + ", ".join(f"{k} {v * 100:.0f}%" for k, v in avgw.items()) + "\n")
            a10 = cv["A10"]
            res[(sample, w, "A10")] = {"cagr_pct": round(_cagr(a10), 2), "max_drawdown_pct": round(_max_dd(a10), 2),
                                       "grew_lakh": round(10 * a10.iloc[-1], 2), "turnover_pa": 0.0}
            out.flush()
            print(sample, w, {k: (res[(sample, w, k)]["cagr_pct"], res[(sample, w, k)]["max_drawdown_pct"])
                              for k in ("EW", "DA_RR", "DA_IV", "DA_TOP3", "A10")}, flush=True)
        del panel
        gc.collect()
    out.write(f"\n{'=' * 70}\nSUMMARY: CAGR % (max DD %)\n{'=' * 70}\n")
    for sample in ("ALL", "A", "B"):
        for rule in ("EW", "DA_RR", "DA_IV", "DA_TOP3", "A10"):
            parts = [f"{w} {res[(sample, w, rule)]['cagr_pct']:.2f} ({res[(sample, w, rule)]['max_drawdown_pct']:.1f})" for w in WINDOWS]
            out.write(f"  {rule + '@' + sample:14s} " + " | ".join(parts) + "\n")
    out.write("\nVERDICT (DA_RR vs EW, all stocks, W1 and W2: CAGR >= EW + 1.0pp AND max DD no more than 2.0 points deeper):\n")
    ok_all = True
    for w in JUDGED_WINDOWS:
        d, e = res[("ALL", w, "DA_RR")], res[("ALL", w, "EW")]
        gain = round(d["cagr_pct"] - e["cagr_pct"], 2)
        dd_worse = round(e["max_drawdown_pct"] - d["max_drawdown_pct"], 2)
        ok = gain >= 1.0 and dd_worse <= 2.0
        ok_all &= ok
        out.write(f"  {w}: CAGR gain {gain:+.2f}pp; drawdown deeper by {dd_worse:+.2f} points -> {'PASS' if ok else 'FAIL'}\n")
    out.write(f"  => {'DYNAMIC ALLOCATION HELPS' if ok_all else 'DOES NOT HELP (IA decides)'}\n")
    out.close()
    print("ALLDONE")


if __name__ == "__main__":
    main()
