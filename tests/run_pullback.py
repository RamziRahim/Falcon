"""
Falcon -- IA's leader pullback strategy on half A, per docs/pullback_preregistration.md.

    python tests/run_pullback.py [W1 ...] > data/pullback.log
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES, sector_maps
from backtesting.pit_strategies import equal_weight_universe
from backtesting.pullback import run_pullback
from tests.half_a import load_half_a, report
from tests.run_mean_reversion import _nifty

PREREG = "docs/pullback_preregistration.md"
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31")}
VERSIONS = [("PB10", 0.01, False), ("PB075", 0.0075, False), ("PBB10", 0.01, True), ("PBB075", 0.0075, True)]
ONLY = sys.argv[1:]


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    panel = load_half_a()
    nifty, src = _nifty()
    ix = pd.read_parquet("data/pit_sources/indices.parquet")
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    smaps = sector_maps(panel, indices)
    sdates = np.array(sorted(smaps))

    def sector_of(day):
        k = sdates.searchsorted(np.datetime64(day), side="right") - 1
        return smaps[pd.Timestamp(sdates[k])] if k >= 0 else {}

    out = open("data/pullback_result.txt" if not ONLY else "data/pullback_smoke.txt", "w", encoding="utf-8")
    out.write(f"Benchmark: {src}; half A only; leader pullback\n")
    for code, rk, br in VERSIONS:
        for w, (a, b) in WINDOWS.items():
            if ONLY and w not in ONLY:
                continue
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            eq, tr, st = run_pullback(panel, a, b, nifty, sector_of, risk=rk, breadth=br)
            tr.to_csv(f"data/pullback_trades_{code}_{w}.csv", index=False)
            report(out, code, w, a, b, eq, tr, nifty, equal_weight_universe(panel, a, b), st)
    out.close()


if __name__ == "__main__":
    main()
