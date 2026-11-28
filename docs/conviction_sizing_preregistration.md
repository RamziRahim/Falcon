# Pre-registration: conviction score (volume profile + delivery) for sizing up entries

**Status: DRAFT, written 2026-11-28. NOT FROZEN.** (Updated 2026-11-28 in the cloud session,
before freezing: data paths moved from `data/pit` to `data/pit_v2`, and a reference check
added.) Code written and unit-tested; no
returns measured. IA to confirm or change the score, the buckets and the bar, then replace
this line with "FROZEN on <date, time>" before any run. After that: never edit; add dated
notes.

## Question

Do the trades of Falcon's best strategies that enter with (a) price above its own recent
value area with little supply overhead, (b) unusually high delivery, and (c) delivery-
backed accumulation do better than the others, by enough to justify putting more money
into them? This test only asks whether the score **sorts** trades. Sizing money by it is a
later, separately registered simulation, and only if this passes.

Footprint charts, CVD and order flow are **not** part of the score: there is no historical
tick data, so they cannot be tested. They may be shown live as information only, like the
VWAP-reclaim flag.

## Data

- Prices: `data/pit_v2/prices_adjusted.parquet` and `data/pit_v2/universe_monthly.parquet`,
  the current point-in-time data (since 22 Nov 2026), which the paper engine also uses.
- **Reference check:** before any trade is scored, A10 and FM_C3 must reproduce
  `data/buystop_mix_result.txt` (pit_v2) within 0.05pp of CAGR and max DD on half A and
  half B in W1 and W2. If either does not, the run stops.
- Delivery: NSE's daily security-wise delivery file (`MTO_DDMMYYYY.DAT`, with
  `sec_bhavdata_full` as fallback), downloaded by `tests/download_delivery.py` into
  `data/delivery/delivery_equity.parquet`. The bhavcopies Falcon holds have no delivery
  column.
- Delivery rows are matched to `entity_id` through the price rows' own (date, symbol), so
  symbol changes carry over. **Only EQ-series figures count:** BE/BZ are trade-for-trade
  and always about 100% delivered.

## The score (`scoring/conviction.py`)

**Point in time.** A trade bought on `entry_date` is scored with data up to and including
the last session before `entry_date` (t0). For next-open entries that is the signal
close. For clean-close entries (FM_C3, decided at ~3:20 pm) it is the day before, because
that day's full volume and delivery are not known at the decision.

Three points, 0 or 1 each:

| Point | Rule |
|---|---|
| **VP** | Volume profile of the 60 sessions to t0: each session's turnover spread evenly over its high–low range, 50 equal price bins, value area = 70% grown from the point of control. 1 if close(t0) > value-area high **and** at most 10% of the profile's turnover lies between the close and 10% above it. |
| **DLV** | 1 if delivery % on t0 ≥ 1.3 × its mean over the 20 sessions before t0 (needs t0 and at least 15 of the 20). |
| **ACC** | Over the 10 sessions to t0, delivered value (delivery % × turnover) on up-close days > on down-close days (needs at least 7 usable sessions). |

Score = VP + DLV + ACC. A missing input scores 0 for that point; the share of trades with
missing delivery or profile is reported.

**Buckets and the sizing they would justify:**

| Score | Bucket | Size multiplier (later test only) |
|---|---|---|
| 0 | 0 | 0.75× |
| 1 | 1 | 1.0× |
| 2 or 3 | 2-3 | 1.5× |

2 and 3 are pooled because a blinded frequency check (below) showed score 3 would be
too rare to judge.

## Part 1 (judged): A10 and FM_C3

- **A10**: monthly momentum, top 20, 10% stop (`run_momentum(stop_pct=0.10)`).
- **FM_C3**: Falcon Momentum, clean close, 1:3 (`run_fm_entries(..., "closebuy", r_mult=3.0)`).
- These two form C_F_A, the paper-trading candidate. Both are re-run unchanged on half A
  and on half B (`data/holdout_split.csv`), on W1 2019-01-01 → 2026-10-30, W2 2008-01-01 →
  2017-12-31, and 2018 (reported only).
- Every closed trade is scored; `net` = pnl ÷ cost basis, after costs.

**Checks, per strategy, half and window:**
1. Mean net per trade rises with the bucket: 0 ≤ 1 ≤ 2-3.
2. Bucket 2-3 beats bucket 0 by at least 1.0 percentage point a trade.
3. Bucket 2-3 holds at least 30 trades.
4. Welch t of bucket 2-3 against the rest ≥ 1.5.

**Bar.** A strategy passes only if all four checks hold in **both** W1 and W2 on half A
**and** on half B. Each strategy is judged on its own; one can pass while the other fails.
A pass only allows a separately registered sized simulation (multipliers above, capped
total risk), judged against the unsized strategy on CAGR, worst drop and the six checks.

Also reported: win rate per bucket, the share of trades per bucket, the capital-weighted
mean net per trade under the multipliers, and missing-data shares.

## Part 2 (reported only): the top 25 committed trade logs

The 25 committed `data/*_W1.csv` / `*_W2.csv` trade logs with at least 100 closed trades
and the highest mean net per trade over W1 + W2, scored the same way. The scores are
computed on the all-stocks panel, so a log run on half A is scored with the same data.
Reported: mean net per bucket in W1 and W2, and how many of the 25 rise with the score in
both. This is selected on past results and decides nothing.

## Expected, stated before the run

DLV and ACC have the better chance of sorting trades. VP is likely to overlap with what
the entries already require: FM_C3 buys at 20-day highs, so about half its trades get
the VP point anyway. A10 enters at month-ends, not breakouts, so fewer of its trades get
it. A likely outcome is a small, non-monotone difference that fails check 2. If so, sizing
stays flat.

## Paper trading

The paper-trading plan frozen on 22 Nov 2026 is not changed. If IA agrees, the paper
server logs the score (`scoring.conviction.score_asof`, data to the previous close) next
to every signal from day one, **without acting on it**. That gives a clean live sample for
the 3-month review.

## What this does not decide

Whether either strategy works, which strategies are paper traded, or any change to entries
and exits.

## Before freezing: what has been looked at

- Unit tests (`tests/scoring/test_conviction.py`, 19): profile maths, each point's
  thresholds, EQ-only delivery mapping, NSE file parsers, the bucket checks, and that
  changing any data on or after `entry_date` leaves the score unchanged.
- **Blinded frequency check, 2026-11-28** (VP point only; pnl replaced with zero):
  - A10: 12.6% of trades get the VP point in W1 and 9.1% in W2.
  - FM_C3 (half A): 47.8% in W1 and 42.0% in W2.
  - This is why scores 2 and 3 are pooled.
- **Plumbing run, 2026-11-28:** the whole runner, with randomly generated delivery
  figures, to check it completes (about 1.5 minutes).
  - Its output was discarded.
  - One console line was seen: FM_C3 half B 2018, a reported-only window, on fake
    delivery data.

## Outputs

- `data/conviction_sizing_result.txt`
- `data/conviction_scores_<code>_<half>_<window>.csv` (one row per scored trade)

## How to run

    python tests/download_delivery.py            # once; needs NSE access (laptop or server)
    PYTHONHASHSEED=0 python tests/run_conviction_sizing.py > data/conviction_sizing.log

The delivery history is downloaded on the Oracle server (which reaches NSE) and brought
to the test machine through the `paper-data` branch.
