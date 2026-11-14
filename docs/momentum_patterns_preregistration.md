# Pre-registration: v3 patterns with monthly momentum (sleeve and entry timing)

**Status: FROZEN on 2026-11-14 14:09 IST.** Frozen by IA before any test code was written or run.
Never edit; add dated notes.

**Samples.** Each version runs once on half A, half B and all stocks, on W1 2019-01-01 →
2026-10-30, W2 2008-01-01 → 2017-12-31 and 2018, with the same six checks, costs and data,
and `PYTHONHASHSEED=0`. All windows are in-sample: both halves have been used for
monthly momentum, the current mix and the v3 pattern test. A pass would mean "paper
trade it", not "proven".

## Why

v3 pattern trades (P3, `docs/falcon_v3_patterns_preregistration.md`) had the best trade
quality of any breakout test (win 51-56%, +2.5% to +4.5% net per trade, drawdowns −15% to
−23%), but kept only 34-55% of capital invested, so its return stayed near the Nifty's.
Monthly momentum with a 10% stop (A10) earns the most but has deep drawdowns. The current
best balance is C_F_A: half A10, half Falcon Momentum clean close (FM_C3). This test asks
whether v3 patterns do that job better, either as the partner sleeve or as A10's entry
timing.

## Versions

| Code | What | Role |
|---|---|---|
| A10, FM_C3, C_F_A | as stored | references |
| P3 | as `docs/falcon_v3_patterns_preregistration.md` (v3 REAL_PATTERN, close-confirmed entry, v3 stop, 1:3, 40 sessions, 1% risk, 10 slots) | reference |
| **C_A_P3** | half A10, half P3 | **primary** |
| C_F_A_P3 | a third each of A10, FM_C3 and P3 | reported |
| A10T | A10's list, bought only on a v3 breakout (rules below) | reported |

### Sleeves (C_A_P3, C_F_A_P3)

1. Each sleeve runs on its own with its own capital, exactly as its reference, and the
   sleeves are reset to equal weights at the first session of every month, with no
   rebalancing cost charged (the existing `combine()` in `tests/run_portfolio_combo.py`,
   as used for C_F_A).

### Entry timing (A10T)

2. The list is A10's: at each month end, the top 20 of that month's universe by 12-1
   momentum (252 to 21 sessions ago).
3. At the first session of a month, holdings not on the new list are sold at the open,
   as in A10. Holdings still on the list are kept.
4. A list stock that is not held is bought at the close of the first session on which
   (a) it has a v3 `REAL_PATTERN` setup from a scan in the last 5 sessions (the stored
   v3 scans) and (b) that session meets FV2 rule 6: High > pivot, Close > pivot,
   (Close − Low) ÷ (High − Low) ≥ 0.5, and the Nifty 50 above its 50-DMA.
5. Size: equity ÷ 20, limited by the cash on hand. No more than 20 holdings.
6. Stop: 10% below the fill (A10's), checked from the session after the fill; sold at the
   stop, or at the open if it gaps below. A stopped stock is not re-bought before the next
   month-end list. There is no target and no time stop; a holding stays while it is on
   the list.
7. Uninvested cash earns nothing.

## Reference checks (before any version is judged)

- A10 and C_F_A must reproduce their stored results within 0.05pp (CAGR and max drawdown):
  half A `data/wick_exit_result.txt`, half B `data/halfB_confirmation_result.txt`, all
  stocks (A10) `data/a_stop_result.txt`; W1 and W2.
- P3 must reproduce `data/falcon_v3_patterns_result.txt` on all three samples, W1 and W2.

## Adoption bar (C_A_P3; all must hold on both half A and half B, in both W1 and W2)

1. At least 5 of the 6 checks;
2. max drawdown no deeper than C_F_A's on the same sample and window;
3. CAGR ÷ |max drawdown| at least C_F_A's on the same sample and window.

Figures are compared as printed in the result file. Stored C_F_A figures for reference:

| Sample, window | C_F_A CAGR | Max DD | CAGR ÷ |DD| |
|---|---|---|---|
| Half A, W1 | 20.66% | −25.85% | 0.80 |
| Half A, W2 | 12.60% | −20.89% | 0.60 |
| Half B, W1 | 16.13% | −31.42% | 0.51 |
| Half B, W2 | 12.44% | −36.14% | 0.34 |

Also reported: average capital invested, the correlation of monthly returns between the
A10 sleeve and the P3 and FM_C3 sleeves, 2018, and for A10T the number of list stocks
bought per month and the share of list months each stock was held.

## What adoption would mean

C_A_P3 would replace C_F_A as the paper-trading candidate beside A10 alone. Paper
trading would decide.

## Expected, stated before the run

C_A_P3 has shallower drawdowns than C_F_A in some cells (P3's drawdowns are smaller than
FM_C3's), but a lower return in 2008-17, where FM_C3 earned 11-13% and P3 6-7%. It is
likely to fail rule 3 in W2. A10T holds far fewer stocks than A10, so it returns much less;
its drawdowns may be smaller.

## Output

`data/momentum_patterns_result.txt`, runner `tests/run_momentum_patterns.py`, blocks named
`CODE@SAMPLE`. A10T is new code in `backtesting/momentum_timing.py`; nothing existing
changes.

**Note, 2026-11-14 (implementation, before any result was seen):** rule 5 does not say
how cash is shared when several list stocks qualify on the same session and cash is short.
A10T uses A10's own convention (`run_momentum`): each gets min(equity ÷ 20, cash ÷ number
of buys that session × 0.995). A smoke run on half A for 2018 (A10T only, 2 buys) checked
the code and was discarded.

---

## Results — 2026-11-14 (added after the run; nothing above was changed)

**Run notes.** `tests/run_momentum_patterns.py`, one run, `PYTHONHASHSEED=0`.
**Reference checks: all 16 matched** within 0.05pp (A10, C_F_A and P3 on half A and half B;
A10 and P3 on all stocks; W1 and W2).

**Correction to the reference table above (dated note).** The stored C_F_A drawdowns for
half A were copied from the wrong columns of the scorecard. The correct stored figures,
reproduced by this run, are half A W1 20.66% / −20.89% (CAGR ÷ |DD| 0.99) and half A W2
12.61% / −35.65% (0.35). Half B was correct. The bar compares with C_F_A's figures as
printed in the result file, so it is judged with these. The verdict below is the same
with either table.

### Primary C_A_P3 against the frozen bar

| Sample, window | Checks | Max DD (C_F_A) | CAGR ÷ |DD| (C_F_A) | Bar |
|---|---|---|---|---|
| Half A, W1 | 4/6 ✗ | −22.60% (−20.89%) ✗ | 16.43 ÷ 22.60 = 0.73 (0.99) ✗ | **FAIL** |
| Half A, W2 | 4/6 ✗ | −35.23% (−35.65%) ✓ | 10.08 ÷ 35.23 = 0.29 (0.35) ✗ | **FAIL** |
| Half B, W1 | 5/6 ✓ | −24.45% (−31.42%) ✓ | 18.89 ÷ 24.45 = 0.77 (0.51) ✓ | pass |
| Half B, W2 | 4/6 ✗ | −35.20% (−36.14%) ✓ | 10.05 ÷ 35.20 = 0.29 (0.34) ✗ | **FAIL** |

**Verdict: C_A_P3 FAILED its bar (3 of 4 cells). Not adopted.** C_F_A remains the
paper-trading candidate beside A10.

### All versions (CAGR / max DD / checks; average capital invested)

| Code | Half A W1 | Half A W2 | Half B W1 | Half B W2 | All W1 | All W2 |
|---|---|---|---|---|---|---|
| A10 | 25.93 / −32.51 / 6; 88% | 11.28 / −58.90 / 5; 85% | 23.22 / −41.36 / 5; 88% | 12.15 / −58.58 / 5; 85% | 26.36 / −39.44 / 5 | 13.17 / −59.05 / 5 |
| FM_C3 | 14.49 / −17.95 / 3 | 12.69 / −23.22 / 5 | 8.40 / −25.57 / 2 | 11.34 / −24.16 / 5 | 11.71 / −23.76 / 3 | 12.85 / −26.14 / 5 |
| P3 | 6.34 / −23.34 / 2; 43% | 7.47 / −14.89 / 4; 37% | 13.12 / −15.77 / 3; 38% | 6.45 / −19.15 / 3; 34% | 15.16 / −17.95 / 4 | 7.57 / −21.31 / 4 |
| C_F_A | 20.66 / −20.89 / 5; 71% | 12.61 / −35.65 / 5; 66% | 16.13 / −31.42 / 5; 71% | 12.43 / −36.14 / 5; 66% | 19.49 / −25.88 / 5 | 13.60 / −35.66 / 5 |
| **C_A_P3** | 16.43 / −22.60 / 4; 66% | 10.08 / −35.23 / 4; 61% | 18.89 / −24.45 / 5; 63% | 10.05 / −35.20 / 4; 59% | 21.46 / −25.96 / 5 | 11.10 / −35.86 / 5 |
| C_F_A_P3 | 15.98 / −17.46 / 4 | 11.12 / −25.37 / 5 | 15.47 / −23.04 / 5 | 10.70 / −25.90 / 5 | 18.35 / −20.98 / 5 | 11.84 / −25.83 / 5 |
| A10T | 1.87 / −6.69 / 1; 7% | 2.07 / −5.25 / 1; 7% | 4.97 / −11.61 / 1; 11% | 1.45 / −7.07 / 2; 6% | 5.15 / −5.10 / 1 | 1.56 / −6.66 / 2 |

2018: C_F_A −25.85% (A) / −26.34% (B); C_A_P3 −26.63% / −22.24%; C_F_A_P3 −22.76% / −20.18%;
A10 −36.13% / −36.03%.

Monthly return correlation with the A10 sleeve: P3 0.40 / 0.41 (half A W1 / W2), 0.44 / 0.34
(half B); FM_C3 0.56 / 0.54 (half A), 0.67 / 0.50 (half B).

A10T bought 0.4-0.5 list stocks per month on average and held 5-9% of list slots at month
end (45-49 buys per window).

### Reading (information only; no decision rests on it)

- Swapping FM_C3 for P3 beside A10 helps only in 2019-26 on half B. In 2008-17 the P3 half
  earns 6-7% against FM_C3's 11-13%, so the mix loses return without a shallower drawdown
  (A10's −59% dominates either half-and-half mix).
- The three-way mix (C_F_A_P3, reported only) is the most balanced combination tested: it
  cut the 2008-17 drawdown from about −36% to about −26% on both halves and had a better
  return-to-drawdown ratio than C_F_A in 3 of 4 cells, at a cost of 1.5-4.7 points of
  yearly return. Being reported, it cannot be adopted from this test; it has now been seen
  on both halves, so only paper trading could test it.
- P3 is less correlated with A10 than FM_C3 is (about 0.4 against 0.5-0.67), which is why it
  helps in a three-way split.
- A10T almost never trades: momentum leaders rarely sit in a fresh v3 base at the right
  edge, so 90%+ of the account stays in cash.
- Expectation check: shallower drawdowns in some cells (held: half B W1, and slightly in
  W2); lower 2008-17 return (held); fails rule 3 in W2 (held, and also on half A W1);
  A10T returns much less with smaller drawdowns (held).

**Correction, 2026-11-14:** in the reading above, "at a cost of 1.5-4.7 points of yearly return" should read "at a cost of 0.7-4.7 points" (half B 2019-26 lost 0.66 points).
