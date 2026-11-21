# Pre-registration: Falcon v2 patterns with a retest entry

**Status: FROZEN on 2026-11-13 16:22 IST.** Frozen by IA ("Implement and test and report results") before any
test code was written or run. Never edit; add dated notes.

**Samples.** Each variant runs once on half A and half B (`data/holdout_split.csv`) and
on all stocks, on W1 2019-01-01 → 2026-10-30, W2 2008-01-01 → 2017-12-31 and 2018, with
the same six checks, costs and data, and `PYTHONHASHSEED=0`. The stored v2 scans
(`data/pit/falcon_setups_v2_*.parquet`) are reused; nothing is rescanned.
- **Neither half is a clean test.** Half A shaped the v2 rules, and half B was used once
  for the v2 test (`docs/falcon_v2_preregistration.md`, 2026-11-11). A pass here is
  weaker evidence than that test was; only paper trading could confirm it.

One variant is **primary**; only it can be adopted. All windows are in-sample.

## Why

FV2 buys at the close of a confirmed breakout. It roughly matched the Nifty and failed
its bar, mostly on drawdown and on the six checks. Retest entries were tested on the
20-day-high breakout (#3) and failed (`docs/s_retest_preregistration.md`,
`docs/retest_depth_preregistration.md`), but never on Falcon's patterns. This test asks
whether waiting for the price to come back to the pivot after a confirmed breakout gives
a better entry than buying the breakout close.

## Rules

Rules 1-5 (v2 detection and the filters at the scan date), rule 8 (stop), rule 10
(sizing, 10 slots, priority by 126-session return rank) of
`docs/falcon_v2_preregistration.md` apply unchanged. Rules 6, 7 and 9 are replaced by:

### Breakout day (no purchase)

R1. The **breakout day** is the first session, among the 5 after the scan, that meets
    all of FV2's rule 6 conditions: High > pivot; Close > pivot; (Close − Low) ÷
    (High − Low) ≥ 0.5; the Nifty 50 closes above its 50-DMA. As in FV2, the setup is
    cancelled if a session closes at or below Falcon's stop before a breakout day.

### Retest entry (primary, FV2R)

R2. From the session after the breakout day, for **10 sessions**, a limit buy order
    rests at the **pivot**. It fills on the first session whose Low ≤ pivot, at the
    lower of the pivot and that session's Open.
R3. The order is cancelled, unfilled, if a session **closes** at or below Falcon's stop,
    or after the 10th session. There is no Nifty condition on the fill day.
R4. Stop = the higher of Falcon's structural stop and fill − 3 × ATR(14) (ATR as of the
    session before the fill). Skip if the stop is not below the fill or is more than 15%
    below it.
R5. Target = fill + 3 × (fill − stop). Time stop 40 sessions from the fill (sell at the
    next open). On the fill session the stop is checked (Low ≤ stop → sold at the stop
    that day); the target is not. On later sessions the stop wins ties.
R6. One open order or position per stock. If the slots are full when an order would
    fill, the fill is skipped and the order stays live.

## Versions

| Code | Entry | Role |
|---|---|---|
| FV2 | close of the breakout day (as tested on 2026-11-11) | reference |
| **FV2R** | limit at the pivot, R2-R6 | **primary** |
| FV2RC | within the same 10 sessions, buy at the **close** of the first session with Low ≤ pivot and Close > pivot; no exit checks on the entry session; otherwise R3-R6 | reported |
| FV2RE | limit at the 20-day EMA of closes (previous session's value) instead of the pivot; fills when Low ≤ EMA, at the lower of the EMA and the Open; only while that EMA is above Falcon's stop; otherwise R3-R6 | reported |

**Reference check.** FV2 must reproduce `data/falcon_v2_result.txt` (CAGR and max
drawdown within 0.05pp) on all three samples, W1 and W2, before any variant runs.

## Adoption bar (FV2R; all must hold on **both** half A and half B, in **both** W1 and W2)

The same absolute bar as the v2 test:
1. CAGR above the Nifty's;
2. at least 4 of the 6 checks;
3. max drawdown no deeper than −25.00%;
4. win rate at least 45.0%, and mean net per trade at least +1.00%.

And, so that it is an improvement and not just a pass:
5. CAGR not lower than FV2's on the same sample and window.

Figures are compared as printed in the result file.

Also reported, per sample and window: trades per year; the share of breakout days that
retest the pivot within 10 sessions (fill rate); what share of filled trades hit the
stop; the exit mix; the 2018 result; and, for information, the 40-session return from
the breakout close of the breakouts that never retested.

## What adoption would mean

FV2R would become the pattern entry and trade plan in Falcon's decision engine. It would
not replace monthly momentum or FM; running it beside them would be a separate
registered test. Because neither half is clean, adoption would mean "paper trade it",
not "trade it".

## Expected, stated before the run

About half of the breakout days retest the pivot, so fewer trades than FV2. The retested
breakouts are the weaker ones: a lower win rate and a lower return than FV2, with a
smaller average loss because the entry is nearer the stop. FV2R is expected to fail
rule 5 and probably rule 1. FV2RC is expected to do best of the three.

## Output

`data/falcon_v2_retest_result.txt`, runner `tests/run_falcon_v2_retest.py`, blocks named
`CODE@SAMPLE`. Implemented as an optional parameter of `run_setups_v2` that defaults to
the current behaviour.

---

## Results — 2026-11-13 (added after the run; nothing above was changed)

**Run notes.** Implemented as `run_setups_v2(..., entry=...)` (default `"close"` = FV2
unchanged); runner `tests/run_falcon_v2_retest.py`, one run with `PYTHONHASHSEED=0`,
reusing the stored v2 scans. A smoke run on half A, 2018 was made first (FV2 matched its
stored 2018 result) and discarded.
**Reference check:** FV2 reproduced `data/falcon_v2_result.txt` exactly on half A, half B
and all stocks, W1 and W2.

### Primary variant FV2R against the frozen bar

| Sample, window | CAGR (Nifty) | Checks | Max DD | Win / net | CAGR vs FV2 | Bar |
|---|---|---|---|---|---|---|
| Half A, W1 | 4.57% (10.03%) ✗ | 3/6 ✗ | −32.43% ✗ | 42.3% / +1.07% ✗ | 4.57 < 9.50 ✗ | **FAIL** |
| Half A, W2 | 3.86% (5.54%) ✗ | 4/6 ✓ | −23.22% ✓ | 44.4% / +1.05% ✗ | 3.86 < 6.36 ✗ | **FAIL** |
| Half B, W1 | 4.73% (10.03%) ✗ | 3/6 ✗ | −33.40% ✗ | 36.7% / +1.27% ✗ | 4.73 < 11.64 ✗ | **FAIL** |
| Half B, W2 | 4.60% (5.54%) ✗ | 3/6 ✗ | −30.96% ✗ | 45.1% / +1.52% ✓ | 4.60 < 5.58 ✗ | **FAIL** |

**Verdict: FV2R FAILED its bar in all four cells. Not adopted.** It is below the Nifty and
below FV2 everywhere. Rule 5 (beat FV2) and rule 1 (beat the Nifty) failed in every cell,
as expected before the run.

### All versions (CAGR / max DD / win / net per trade / closed trades / checks)

| Code | Sample | W1 2019–26 | W2 2008–17 | 2018 |
|---|---|---|---|---|
| FV2 | A | 9.50 / −29.59 / 45.7 / +1.79 / 431 / 3 | 6.36 / −25.13 / 48.2 / +1.72 / 417 / 4 | −7.55 / −15.07 / 29.8 / −2.26 / 47 / 2 |
| **FV2R** | A | 4.57 / −32.43 / 42.3 / +1.07 / 442 / 3 | 3.86 / −23.22 / 44.4 / +1.05 / 441 / 4 | −4.94 / −14.37 / 29.2 / −1.69 / 48 / 2 |
| FV2RC | A | 7.27 / −16.86 / 46.9 / +1.91 / 341 / 2 | 4.75 / −19.22 / 45.6 / +1.27 / 364 / 4 | −8.37 / −13.42 / 29.4 / −2.21 / 34 / 2 |
| FV2RE | A | 7.25 / −24.36 / 39.7 / +1.38 / 418 / 2 | 7.09 / −16.48 / 42.4 / +1.65 / 403 / 4 | −6.79 / −14.78 / 26.3 / −1.54 / 38 / 2 |
| FV2 | B | 11.64 / −21.95 / 46.5 / +2.59 / 383 / 3 | 5.58 / −28.34 / 46.4 / +1.50 / 403 / 4 | −2.01 / −11.37 / 34.9 / −1.86 / 43 / 2 |
| **FV2R** | B | 4.73 / −33.40 / 36.7 / +1.27 / 401 / 3 | 4.60 / −30.96 / 45.1 / +1.52 / 406 / 3 | −14.38 / −16.81 / 25.0 / −3.31 / 40 / 2 |
| FV2RC | B | 5.96 / −21.68 / 43.5 / +2.02 / 299 / 3 | 3.67 / −29.45 / 45.0 / +1.33 / 331 / 3 | −12.05 / −14.93 / 24.2 / −4.27 / 33 / 2 |
| FV2RE | B | 0.93 / −41.57 / 33.8 / +0.95 / 376 / 1 | 2.33 / −33.14 / 34.8 / +0.07 / 345 / 3 | −12.40 / −16.94 / 22.2 / −2.47 / 36 / 2 |
| FV2 | All | 12.20 / −24.63 / 44.6 / +1.88 / 491 / 3 | 4.31 / −30.39 / 44.9 / +0.88 / 497 / 4 | −1.19 / −15.67 / 37.0 / −0.83 / 54 / 2 |
| **FV2R** | All | 8.36 / −42.31 / 38.4 / +1.11 / 597 / 3 | 3.88 / −35.01 / 42.9 / +1.04 / 571 / 3 | −9.37 / −17.88 / 31.3 / −1.51 / 67 / 2 |
| FV2RC | All | 7.25 / −25.18 / 45.2 / +1.81 / 442 / 2 | 2.94 / −27.85 / 44.7 / +1.14 / 461 / 2 | −7.39 / −13.78 / 35.2 / −2.24 / 54 / 2 |
| FV2RE | All | 10.86 / −35.43 / 37.2 / +1.24 / 626 / 3 | 4.08 / −38.03 / 38.7 / +0.91 / 599 / 3 | −12.60 / −17.31 / 24.3 / −1.81 / 70 / 2 |

### Also reported for FV2R

| Sample, window | Trades/yr | Breakout days | Filled | Never came back to the pivot | Their 40-session gain from the breakout close (gross) | Filled trades ending at the stop | Stopped on the fill day | Exit mix (stop / time / target) |
|---|---|---|---|---|---|---|---|---|
| Half A, W1 | 56.5 | 778 | 56.8% | 187 (24%) | +9.0% | 52.3% | 11 | 231 / 145 / 66 |
| Half A, W2 | 44.1 | 792 | 56.9% | 191 (24%) | +9.0% | 47.8% | 8 | 211 / 163 / 66 (+1 delisted) |
| Half A, 2018 | 48.2 | 65 | 84.6% | 8 (12%) | +0.1% | 68.8% | 1 | 33 / 10 / 5 |
| Half B, W1 | 51.2 | 687 | 58.4% | 169 (25%) | +10.8% | 54.1% | 8 | 217 / 110 / 73 (+1 delisted) |
| Half B, W2 | 40.6 | 661 | 62.9% | 150 (23%) | +9.0% | 47.0% | 11 | 191 / 154 / 61 |
| Half B, 2018 | 40.1 | 58 | 75.9% | 11 (19%) | +4.9% | 65.0% | 1 | 26 / 11 / 3 |
| All, W1 | 76.3 | 1,517 | 39.4% | 365 (24%) | +9.7% | 54.3% | 23 | 324 / 162 / 110 (+1 delisted) |
| All, W2 | 57.1 | 1,495 | 38.9% | 349 (23%) | +8.9% | 49.4% | 28 | 282 / 209 / 79 (+1 delisted) |
| All, 2018 | 67.2 | 125 | 61.6% | 19 (15%) | +2.9% | 64.2% | 1 | 43 / 16 / 8 |

"Filled" is filled ÷ breakout days; the rest of the breakouts either never came back,
came back while all 10 slots were full, or had a stop more than 15% away. FV2 for
comparison: 42–47% of trades ended at the stop in W1 and W2.

### Reading (information only; no decision rests on it)

- About three-quarters of confirmed v2 breakouts come back to the pivot within 10
  sessions. The quarter that never come back are the best ones: they rose about +9% to
  +11% over the next 40 sessions. Waiting for a retest gives those up, and buys more of
  the ones that are failing.
- The retest fill is closer to the stop, so the average loss is a little smaller, but
  more trades hit the stop (47–54% against 42–47% for FV2) and the win rate falls.
- None of the retest variants beat FV2 on both halves. FV2RC (dip to the pivot, close
  back above) had the shallowest drawdowns on half A but was weaker than FV2 on half B.
  FV2RE (20-day EMA) collapsed on half B.
- This matches the #3 retest tests: across both breakout systems, buying the confirmed
  breakout beats waiting for a pullback.
- Expectation check: about half of the breakouts filled (expected about half); win rate
  and return lower than FV2 (expected); FV2R failed rules 5 and 1 (expected); FV2RC was
  not clearly the best of the three (expected it would be).
