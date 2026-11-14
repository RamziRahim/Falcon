# Pre-registration: Falcon pattern engine v2 (fixed pivots, trend gate, close-confirmed entry)

**Status: FROZEN on 2026-11-10 16:00 IST.** Frozen by IA before any code was written or run. Never edit;
add dated notes.

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

---

## Results — 2026-11-11 (added after the run; nothing above was changed)

**Run notes.** The queue was interrupted by a machine restart during the first scan and
restarted from scratch on 2026-11-11; no variant produced results before that. Scans and
the test ran strictly one after another with `PYTHONHASHSEED=0`.
**Reference check:** F_REF on half A reproduced the stored file exactly (W1 8.90% /
−32.14%, W2 −1.61% / −48.36%).

**Detections (2008–2026).** v2 pivots: half A 13,774 (original 15,576), half B 12,621
(14,181), all 26,395 (29,757). Passing rules 4–5: half A 8,290, half B 7,343, all 15,633.

### Primary variant FV2 against the frozen bar

| Sample, window | CAGR (Nifty) | Checks | Max DD | Win | Net/trade | Bar |
|---|---|---|---|---|---|---|
| Half A, W1 | 9.50% (10.03%) ✗ | 3/6 ✗ | −29.59% ✗ | 45.7% ✓ | +1.79% ✓ | **FAIL** |
| Half A, W2 | 6.36% (5.54%) ✓ | 4/6 ✓ | −25.13% ✗ | 48.2% ✓ | +1.72% ✓ | **FAIL** |
| Half B, W1 | 11.64% (10.03%) ✓ | 3/6 ✗ | −21.95% ✓ | 46.5% ✓ | +2.59% ✓ | **FAIL** |
| Half B, W2 | 5.58% (5.54%) ✓ | 4/6 ✓ | −28.34% ✗ | 46.4% ✓ | +1.50% ✓ | **FAIL** |

**Verdict: FV2 FAILED its bar in all four cells. Not adopted.** Rule 4 (win rate and net
per trade) held everywhere. Rule 1 failed on half A W1; rule 2 failed in W1 on both
halves; rule 3 failed in three of four cells. Falcon's patterns stay out of the trading
rules, as stated before the run.

### All versions (CAGR / max DD / win / net per trade / closed trades / checks)

| Code | Sample | W1 2019–26 | W2 2008–17 | 2018 |
|---|---|---|---|---|
| F_REF | A | 8.90 / −32.14 / 45.1 / +0.78 / 827 / 3 | −1.61 / −48.36 / 44.0 / +0.17 / 913 / 1 | −26.10 / −30.76 / 23.7 / −3.42 / 97 / 0 |
| **FV2** | A | 9.50 / −29.59 / 45.7 / +1.79 / 431 / 3 | 6.36 / −25.13 / 48.2 / +1.72 / 417 / 4 | −7.55 / −15.07 / 29.8 / −2.26 / 47 / 2 |
| FV2A | A | 9.23 / −29.07 / 46.1 / +2.18 / 451 / 3 | 9.04 / −20.91 / 49.9 / +2.10 / 429 / 4 | −8.40 / −13.88 / 30.0 / −2.14 / 50 / 2 |
| FV2M | A | 3.18 / −29.53 / 43.2 / +1.40 / 257 / 1 | 3.96 / −19.30 / 44.7 / +1.38 / 253 / 4 | 0.56 / −10.31 / 36.0 / −0.53 / 25 / 2 |
| F_REF | B | −1.33 / −46.53 / 43.2 / +0.31 / 813 / 1 | −3.45 / −51.31 / 43.7 / −0.07 / 909 / 1 | −16.19 / −24.59 / 28.0 / −3.39 / 75 / 1 |
| **FV2** | B | 11.64 / −21.95 / 46.5 / +2.59 / 383 / 3 | 5.58 / −28.34 / 46.4 / +1.50 / 403 / 4 | −2.01 / −11.37 / 34.9 / −1.86 / 43 / 2 |
| FV2A | B | 11.81 / −22.44 / 45.5 / +2.44 / 415 / 3 | 4.85 / −34.15 / 43.6 / +0.99 / 427 / 3 | −1.89 / −12.79 / 30.4 / −1.97 / 46 / 2 |
| FV2M | B | 5.24 / −24.62 / 41.6 / +2.64 / 214 / 2 | 3.84 / −17.53 / 46.4 / +2.23 / 207 / 3 | 0.79 / −8.47 / 42.9 / +0.16 / 28 / 2 |
| F_REF | All | −0.87 / −33.81 / 41.4 / −0.06 / 911 / 1 | −4.71 / −55.55 / 41.3 / −0.06 / 1074 / 1 | −21.50 / −27.99 / 26.6 / −3.13 / 109 / 1 |
| **FV2** | All | 12.20 / −24.63 / 44.6 / +1.88 / 491 / 3 | 4.31 / −30.39 / 44.9 / +0.88 / 497 / 4 | −1.19 / −15.67 / 37.0 / −0.83 / 54 / 2 |
| FV2A | All | 14.87 / −29.51 / 45.7 / +2.35 / 514 / 3 | 6.90 / −26.30 / 46.8 / +1.63 / 517 / 4 | −3.74 / −15.56 / 35.0 / −1.25 / 60 / 2 |
| FV2M | All | 10.54 / −35.87 / 44.7 / +2.27 / 385 / 3 | 7.11 / −22.57 / 45.7 / +1.98 / 376 / 4 | −0.88 / −12.94 / 41.5 / −0.15 / 41 / 2 |

### Also reported for FV2

| Sample, window | Trades/yr | Pivot touches rejected by rule 6 | Exit mix (stop / time / target) |
|---|---|---|---|
| Half A, W1 | 55.1 | 66.5% | 197 / 170 / 64 |
| Half A, W2 | 41.7 | 65.0% | 177 / 183 / 56 (+1 delisted) |
| Half A, 2018 | 47.2 | 67.6% | 31 / 13 / 3 |
| Half B, W1 | 48.9 | 66.6% | 166 / 154 / 62 (+1 delisted) |
| Half B, W2 | 40.3 | 67.1% | 176 / 178 / 48 (+1 delisted) |
| Half B, 2018 | 43.1 | 70.2% | 25 / 15 / 3 |
| All, W1 | 62.7 | 65.7% | 231 / 180 / 80 |
| All, W2 | 49.7 | 65.4% | 221 / 224 / 50 (+2 delisted) |
| All, 2018 | 54.2 | 67.8% | 30 / 19 / 5 |

### Reading (information only; no decision rests on it)

- v2 turned a losing rule set into a modestly positive one on stocks it was never tuned
  on: half B went from −1.3% / −3.5% a year to +11.6% / +5.6%, with drawdowns cut from
  −47% / −51% to −22% / −28%, and net per trade from about 0 to +1.5–2.6%.
- It is still not good enough: returns are near the Nifty's, not clearly above it, and
  it passes only 3–4 of 6 checks. Trades roughly halved, as expected.
- The pivot fixes did not help on their own: FV2A (original pivots) is about equal to or
  better than FV2 in 4 of 6 decade cells. The gain came from the trend gate, the
  close-confirmed entry and the Nifty filter.
- Only 13–16% of trades reach the 1:3 target; about 40–45% end at the 40-session time
  stop. Adding a momentum-rank gate (FV2M) cut trades by about 45% without raising
  returns on either half.
- Expectation check: trades fell by about half (expected a third of F_REF), win rate
  45–48% (expected near 50%), return positive but modest (as expected), half B was not
  weaker than half A (expected weaker).
