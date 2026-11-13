# Pre-registration: Falcon v2 patterns with a retest entry

**Status: DRAFT (2026-11-13). Not frozen. No test code written.**

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
