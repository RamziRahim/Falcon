"""
Falcon -- momentum + 5-day dip (REV) vs momentum alone (MOM10), with/without the
Nifty 200-DMA filter, Step 3 of docs/pullback_diagnostics_preregistration.md (half A).

    python tests/run_mom_reversal.py [W1 ...] > data/mom_reversal.log
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd
import statsmodels.api as sm

from backtesting.mom_reversal import run_mom_reversal
from backtesting.pit_strategies import equal_weight_universe
from tests.half_a import load_half_a, report
from tests.run_mean_reversion import _nifty

PREREG = "docs/pullback_diagnostics_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31")}
ONLY = sys.argv[1:]


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    panel = load_half_a()
    nifty, src = _nifty()
    ix = pd.read_parquet("data/pit_sources/indices.parquet")
    n500 = ix[ix["Index"] == "NIFTY 500"].set_index("Date")["Close"].sort_index()
    n5 = n500.reindex(n500.index.union(panel.sessions)).ffill().reindex(panel.sessions).to_numpy(float)
    C = panel.close.to_numpy(float)
    cols = {e: j for j, e in enumerate(panel.close.columns)}
    out = open("data/mom_reversal_result.txt" if not ONLY else "data/mom_reversal_smoke.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; half A; Step 3\n")
    sig_lines = []
    for w, (a, b) in WINDOWS.items():
        if ONLY and w not in ONLY:
            continue
        a, b = pd.Timestamp(a), pd.Timestamp(b)
        ew = equal_weight_universe(panel, a, b)
        for mode in ("REV", "MOM10"):
            for flt in (True, False):
                code = f"{mode}_{'F' if flt else 'N'}"
                log = []
                eq, tr, st = run_mom_reversal(panel, a, b, nifty, mode, flt, picks_log=log)
                report(out, code, w, a, b, eq, tr, nifty, ew, st)
                if not flt:                                  # signal-level check, unfiltered picks
                    rows = []
                    for i, names in log:
                        if i + 21 >= len(C):
                            continue
                        for e in names:
                            j = cols[e]
                            r = C[i + 21, j] / C[i + 1, j] - 1 if np.isfinite(C[i + 1, j]) else np.nan
                            rows.append((panel.sessions[i], r - (n5[i + 21] / n5[i + 1] - 1)))
                    d = pd.DataFrame(rows, columns=["date", "x"]).dropna()
                    m = d.x.groupby(d.date.dt.to_period("M")).mean()
                    fit = sm.OLS(m.to_numpy(), np.ones(len(m))).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
                    sig_lines.append(f"  {mode:5s} {w:5s} picks {len(d):5d}  mean 20-day excess vs Nifty 500 "
                                     f"{d.x.mean() * 100:+.2f}%  (t {fit.tvalues[0]:+.2f}, {len(m)} months)  win {(d.x > 0).mean() * 100:.0f}%")
    out.write("\n=== signal-level: 20-day forward excess of the picks (next open to open+20) ===\n" + "\n".join(sig_lines) + "\n")
    print("\n".join(sig_lines))
    out.close()


if __name__ == "__main__":
    main()
