"""
Falcon -- does a volume-profile + delivery conviction score pick out the better trades?
Per docs/conviction_sizing_preregistration.md. Refuses to run until that file is frozen.

    python tests/download_delivery.py           # once, on a machine that can reach NSE
    python tests/run_conviction_sizing.py > data/conviction_sizing.log

Part 1 (judged): A10 and FM_C3, re-run with their frozen code on half A, then half B;
every closed trade scored at the close before its entry; bucket checks per window.
Part 2 (reported only): the 25 committed trade logs with the highest mean net per trade
over W1 + W2, scored the same way.
"""
import sys
sys.path.insert(0, ".")

import gc
import glob
import os
import re

import numpy as np
import pandas as pd

from backtesting.falcon_momentum import SECTOR_INDICES
from backtesting.falcon_momentum_entries import run_fm_entries
from backtesting.pit_strategies import _cagr, _max_dd, make_panel, run_momentum
from scoring.conviction import judge_buckets, make_conviction_data, score_trades
from tests.run_a_exposure import ref_numbers

PREREG = "docs/conviction_sizing_preregistration.md"
DELIVERY = "data/delivery/delivery_equity.parquet"
PRICES, UNIVERSE = "data/pit_v2/prices_adjusted.parquet", "data/pit_v2/universe_monthly.parquet"
REF_FILE = "data/buystop_mix_result.txt"   # pit_v2 reference numbers for A10 and FM_C3
WINDOWS = {"W1": ("2019-01-01", "2026-10-30"), "W2": ("2008-01-01", "2017-12-31"), "Y2018": ("2018-01-01", "2018-12-31")}
JUDGED = ("W1", "W2")
TOP_N = 25
OUT = "data/conviction_sizing_result.txt"


def _block(out, title, res):
    tab = res["table"]
    out.write(f"\n{title}\n")
    for b, r in tab.iterrows():
        n = 0 if pd.isna(r["trades"]) else int(r["trades"])
        out.write(f"    score {b:4s} trades {n:5d}   mean net {r['mean_net_pct']:+7.2f}%   win {r['win_pct']:5.1f}%\n")
    out.write(f"    spread 2-3 vs 0 {res['spread_pp']:+.2f}pp   Welch t {res['welch_t']:.2f}   "
              f"mean net {res['mean_net_pct']:+.2f}% -> sized {res['sized_mean_net_pct']:+.2f}%   "
              f"no delivery {res['delivery_missing_pct']:.1f}%   no profile {res['vp_missing_pct']:.1f}%\n")
    for c, ok in res["checks"].items():
        out.write(f"      [{'PASS' if ok else 'FAIL'}] {c}\n")


def _half_panel(prices, uni, half, which):
    u = uni[uni["entity_id"].isin(set(half[half == which].index))]
    return make_panel(prices, u)


def part1(out, prices, uni, delivery, half, nifty, indices):
    verdict = {}
    for which in ("A", "B"):
        panel = _half_panel(prices, uni, half, which)
        data = make_conviction_data(panel, prices, delivery)
        out.write(f"\n{'#' * 70}\nHalf {which}: {panel.close.shape[1]} stocks\n{'#' * 70}\n")
        for code in ("A10", "FM_C3"):
            for w, (a, b) in WINDOWS.items():
                a, b = pd.Timestamp(a), pd.Timestamp(b)
                if code == "A10":
                    eq, trades = run_momentum(panel, a, b, stop_pct=0.10)
                else:
                    eq, trades, _ = run_fm_entries(panel, a, b, nifty, indices, "closebuy", r_mult=3.0)
                if w in JUDGED:                       # the strategies must be the frozen ones
                    want = ref_numbers(REF_FILE, f"{code}@{which}", w)
                    got = (round(_cagr(eq["equity"]), 2), round(_max_dd(eq["equity"]), 2))
                    ok = all(abs(x - y) <= 0.05 for x, y in zip(want, got))
                    out.write(f"  reference check {code}@{which} {w}: file {want} run {got} -> {'MATCH' if ok else 'MISMATCH'}\n")
                    if not ok:
                        raise SystemExit(f"{code}@{which} {w} does not reproduce {REF_FILE}; stopping.")
                scored = score_trades(data, trades)
                scored.to_csv(f"data/conviction_scores_{code}_{which}_{w}.csv", index=False)
                res = judge_buckets(scored)
                _block(out, f"{code}  half {which}  {w} {a.date()} -> {b.date()}"
                            f"{'' if w in JUDGED else '  (reported only)'}", res)
                if w in JUDGED:
                    verdict[(code, which, w)] = res["passed"]
                out.flush()
                print(f"{code} {which} {w}: passed {res['passed']} spread {res['spread_pp']:+.2f}pp", flush=True)
        del panel, data
        gc.collect()
    out.write(f"\n{'=' * 70}\nVERDICT (primary: both halves, W1 and W2, all four checks)\n{'=' * 70}\n")
    for code in ("A10", "FM_C3"):
        dev = all(verdict[(code, "A", w)] for w in JUDGED)
        conf = all(verdict[(code, "B", w)] for w in JUDGED)
        state = "PASSED -> eligible for a separately registered sized simulation" if dev and conf else "FAILED"
        out.write(f"  {code}: half A {'pass' if dev else 'fail'}, half B {'pass' if conf else 'fail'} -> {state}\n")


def top_logs(n=TOP_N):
    pairs = []
    for f in glob.glob("data/*_W1.csv"):
        prefix = f[:-len("_W1.csv")]
        if not os.path.exists(prefix + "_W2.csv") or "conviction_scores" in prefix:
            continue
        t = pd.concat([pd.read_csv(prefix + "_W1.csv"), pd.read_csv(prefix + "_W2.csv")])
        if not {"entity_id", "entry_date", "pnl", "cost_basis", "exit_reason"} <= set(t.columns):
            continue
        t = t[t["exit_reason"] != "OPEN_AT_END"]
        if len(t) >= 100:
            pairs.append((float((t["pnl"] / t["cost_basis"]).mean()), prefix))
    return [p for _, p in sorted(pairs, reverse=True)[:n]]


def part2(out, prices, uni, delivery):
    # memory (2026-11-28: the first run was OOM-killed here): part 2 trades start in 2008 and
    # delivery in 2007, so earlier prices and non-EQ delivery rows are not needed.
    prices = prices[prices["Date"] >= pd.Timestamp("2006-06-01")]
    delivery = delivery[delivery["Series"].astype(str).str.strip() == "EQ"]
    gc.collect()
    panel = make_panel(prices, uni)
    data = make_conviction_data(panel, prices, delivery)
    out.write(f"\n{'#' * 70}\nPart 2 (reported only): top {TOP_N} committed trade logs by mean net per trade\n{'#' * 70}\n")
    out.write(f"  {'log':52s} {'W1 0/1/2-3 mean net %':>26s} {'W2 0/1/2-3 mean net %':>26s}  rises W1/W2\n")
    rising = 0
    for prefix in top_logs():
        cells, ups = [], []
        for w in JUDGED:
            res = judge_buckets(score_trades(data, pd.read_csv(f"{prefix}_{w}.csv")))
            m = res["table"]["mean_net_pct"]
            cells.append("/".join(f"{x:+.1f}" if np.isfinite(x) else "  - " for x in m))
            ups.append(res["checks"]["mean net rises 0 <= 1 <= 2-3"])
        rising += all(ups)
        name = re.sub(r"^data[\\/]", "", prefix)
        out.write(f"  {name:52s} {cells[0]:>26s} {cells[1]:>26s}  {'y' if ups[0] else 'n'}/{'y' if ups[1] else 'n'}\n")
    out.write(f"\n  logs where mean net rises with the score in both W1 and W2: {rising} of {TOP_N}\n")


def main():
    if "**Status: FROZEN" not in open(PREREG, encoding="utf-8").read():
        raise SystemExit(f"{PREREG} is not frozen.")
    if not os.path.exists(DELIVERY):
        raise SystemExit(f"{DELIVERY} missing: run tests/download_delivery.py first.")
    delivery = pd.read_parquet(DELIVERY)
    prices = pd.read_parquet(PRICES)
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Run with PYTHONHASHSEED=0.")
    uni = pd.read_parquet(UNIVERSE)
    half = pd.read_csv("data/holdout_split.csv", index_col=0)["half"]
    ix = pd.read_parquet("data/pit_sources/indices_2000_2026.parquet")
    ix["Date"] = pd.to_datetime(ix["Date"])
    nifty = ix[ix["Index"] == "NIFTY 50"].set_index("Date")["Close"].sort_index()
    src = "NSE NIFTY 50 (data/pit_sources/indices_2000_2026.parquet)"
    indices = ix[ix["Index"].isin(SECTOR_INDICES)].pivot_table(index="Date", columns="Index", values="Close").sort_index()
    with open(OUT, "w", encoding="utf-8") as out:
        out.write(f"Conviction sizing test ({PREREG}); benchmark {src}\n")
        out.write(f"Delivery data: {len(delivery):,} rows, {delivery['Date'].min()} -> {delivery['Date'].max()}\n")
        part1(out, prices, uni, delivery, half, nifty, indices)
        out.flush()
        prices = prices[prices["Date"] >= pd.Timestamp("2006-06-01")]
        delivery = delivery[delivery["Series"].astype(str).str.strip() == "EQ"][["Date", "Symbol", "Series", "DelivPct"]]
        del half
        gc.collect()
        part2(out, prices, uni, delivery)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
