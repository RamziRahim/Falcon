# Pre-registration: Falcon pattern engine v2 (fixed pivots, trend gate, close-confirmed entry)

**Status: DRAFT, written 2026-11-10. NOT FROZEN.** No code written, nothing run. IA to
confirm or change the variants and the adoption bar, then replace this line with
"FROZEN on <date, time>" before any run. After that: never edit; add dated notes.

**Samples.** Each variant runs once on half A and half B (`data/holdout_split.csv`) and
on all stocks, on W1 2019-01-01 → 2026-10-30, W2 2008-01-01 → 2017-12-31 and 2018, with
the same six checks, costs and data, and `PYTHONHASHSEED=0`.
- **Half A is not a clean test:** every rule below was chosen from the half-A study
  (`docs/falcon_false_breakout_study.md`).
- **Half B has never been used for any Falcon pattern test. It is the real test here.**

One variant is **primary**; only it can be adopted. All windows are in-sample.

## Why

The half-A study of 8,175 triggered Falcon patterns found:
- 55% of pivot triggers close back below the pivot, and they lose (−0.4% net). Nothing
  known beforehand predicts them. Those that close above make +2.0% to +2.6%.
- Detections not above a rising 200-DMA, or more than 10-15% below the 52-week high, have
  no edge.
- Two detectors set their pivot below a recent high: the triangle uses the average of
  two highs, and the VCP uses the last contraction's high.
- Pattern type and Falcon's pattern scores carry no information.

## Rules

### Detection (v2 changes to the pattern engine, behind a switch; defaults unchanged)

1. **Ascending triangle pivot** = the higher of the two swing highs (was their average).
2. **VCP pivot** = the highest swing high among its contractions (was the last
   contraction's high).
3. Everything else in the scan is unchanged (`tests/scan_falcon_setups.py`): every 5
   sessions, the same four patterns, pre-breakout, within 5% below the pivot, Falcon's
   structural stop. A new scan is run for W1, W2 and 2018.

### Filters at the scan date

4. Close above the 200-DMA, 50-DMA above the 200-DMA, and the 200-DMA above its value 20
   sessions earlier.
5. Close at or above 85% of the 52-week high (the highest High of 252 sessions, at least
   200 valid).

### Entry (replaces the pivot buy-stop)

6. On any of the 5 sessions after the scan, buy **at the close** of the first session
   where all of these hold:
   - High > pivot;
   - Close > pivot;
   - the close is in the upper half of the day's range ((Close − Low) ÷ (High − Low) ≥ 0.5);
   - the Nifty 50 closes above its 50-DMA that day.

   There is no volume condition and no limit on how far above the pivot it closes.
7. A session that touches the pivot but fails rule 6 does not cancel the order; a later
   session in the window can still qualify. The order is cancelled if a session closes at
   or below Falcon's stop first.

### Stop, target and sizing

8. Stop = the higher of Falcon's structural stop and fill − 3 × ATR(14). Skip if the stop
   is more than 15% below the fill.
9. Target = fill + 3 × (fill − stop). Time stop 40 sessions (sell at the next open). No
   exit checks on the entry session. The stop wins ties.
10. Risk 1% of equity per trade, ≤ 25% per position, 10 slots. When signals exceed free
    slots, the higher 126-session return rank goes first; Falcon's pattern score is not
    used.

## Versions

| Code | Detection | Filters 4-5 | Entry | Role |
|---|---|---|---|---|
| F_REF | original | none | pivot buy-stop, Falcon stop / target | reference (`docs/falcon_salvage_preregistration.md`) |
| **FV2** | v2 pivots | yes | rules 6-10 | **primary** |
| FV2A | original | yes | rules 6-10 | reported (isolates the pivot fixes) |
| FV2M | v2 pivots | yes, plus 126-session return rank in the top 20% | rules 6-10 | reported |

F_REF has stored results only for half A, W1 and W2; it is checked there within 0.05pp.

## Adoption bar (FV2; all must hold on **both** half A and half B, in **both** W1 and W2)

1. CAGR above the Nifty's;
2. at least 4 of the 6 checks;
3. max drawdown no deeper than −25.00%;
4. win rate at least 45.0%, and mean net per trade at least +1.00%.

Figures are compared as printed in the result file.

Also reported: trades per year, the share of pivot touches rejected by rule 6, the exit
mix, and the 2018 result.

## What adoption would mean

FV2 would replace the pattern entry and trade plan in Falcon's decision engine, and the
dashboard's pattern scores would become labels only. It would not replace monthly
momentum or FM; whether to run it beside them would be a separate registered test.

## Expected, stated before the run

Fewer trades than F_REF (about a third), a win rate near 50%, and a positive but modest
return. Half B is likely to be weaker than half A. If FV2 fails on half B, Falcon's
patterns stay out of the trading rules.

## Output

`data/falcon_v2_result.txt`
