"""
Falcon -- gate part 1 of docs/history_2001_2006_preregistration.md: A10 on data/pit_v2
must reproduce data/a_stop_result.txt (CAGR and max drawdown) within 0.50pp.

    PYTHONHASHSEED=0 python tests/check_pit_v2_gate.py
"""
import sys
sys.path.insert(0, ".")

import pandas as pd

from backtesting.pit_strategies import _cagr, _max_dd, make_panel, run_momentum

DD_W1, DD_W2 = -39.44, -59.05          # data/a_stop_result.txt, A10 max_drawdown_pct
REF = {"W1": ("2019-01-01", "2026-10-30", 26.36, DD_W1), "W2": ("2008-01-01", "2017-12-31", 13.16, DD_W2)}


def cagr(equity):
    e = equity["equity"]
    years = (e.index[-1] - e.index[0]).days / 365.25
    return ((e.iloc[-1] / e.iloc[0]) ** (1 / years) - 1) * 100


def main():
    prices = pd.read_parquet("data/pit_v2/prices_adjusted.parquet", filters=[("Date", ">=", pd.Timestamp("2006-01-01"))])
    panel = make_panel(prices, pd.read_parquet("data/pit_v2/universe_monthly.parquet"))
    ok = True
    for w, (a, b, ref, ref_dd) in REF.items():
        equity, _ = run_momentum(panel, pd.Timestamp(a), pd.Timestamp(b), stop_pct=0.10)
        c = _cagr(equity["equity"])
        dd = _max_dd(equity["equity"])
        passed = abs(c - ref) <= 0.50 and abs(dd - ref_dd) <= 0.50
        ok &= passed
        print(f"A10 {w}: CAGR {c:.2f}% vs {ref:.2f}%, max DD {dd:.2f}% vs {ref_dd:.2f}% {'PASS' if passed else 'FAIL'}", flush=True)
    print("GATE PART 1:", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    main()
