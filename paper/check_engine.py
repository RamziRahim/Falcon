"""
Falcon paper engine -- dry-run check on past data (docs/paper_trading_plan.md checklist: "replay
test matches the backtest exactly"). Pretends day one was CHECK_DAY_ONE, runs paper/engine.py's
track runner on its truncated history (from 2022), and runs the same backtest functions on the FULL
data/pit_v2 history with the same ethical exclusions. Every track's final equity and trade count
must match.

    PYTHONHASHSEED=0 python paper/check_engine.py 2026-08-31 2026-09-01 2026-11-20
"""
import sys
sys.path.insert(0, ".")

import os

rank_day, day_one, end = sys.argv[1:4]
os.environ["PAPER_RANK_DAY"], os.environ["PAPER_DAY_ONE"] = rank_day, day_one

import pandas as pd

import paper.engine as eng
from tests.run_ethical_filter_history import load as full_load

end = pd.Timestamp(end)
panel, uni, nifty, indices, new = eng.load(end)
mine, _, _ = eng.run_tracks(panel, uni, nifty, indices, panel.sessions[-1])
exc, _ = eng.excluded_entities(pd.read_parquet(f"{eng.DATA}/universe_monthly.parquet"))
fpanel = full_load("ALL", exc)
fpanel_cut = fpanel                                           # full history; runs end at `end`
uni_full = pd.read_parquet(f"{eng.DATA}/universe_monthly.parquet")
uni_full = uni_full[~uni_full["entity_id"].isin(exc)]
eng.LOAD_FROM = pd.Timestamp("2000-01-01")                    # same runner, full history
ref, _, _ = eng.run_tracks(fpanel, uni_full, nifty, indices, end)
bad = 0
for code in mine:
    a, b = mine[code], ref[code]
    if a is None and b is None:
        continue
    ea, eb = float(a[0]["equity"].loc[:end].iloc[-1]), float(b[0]["equity"].loc[:end].iloc[-1])
    na, nb = len(a[1]), len(b[1])
    ok = abs(ea - eb) < 1.0 and na == nb
    bad += not ok
    print(f"{code:16s} engine {ea:14,.2f} ({na} trades)  full-history {eb:14,.2f} ({nb} trades)  {'MATCH' if ok else 'MISMATCH'}")
print("ALL MATCH" if not bad else f"{bad} MISMATCH(ES)")
