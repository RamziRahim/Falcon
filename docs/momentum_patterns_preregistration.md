# Pre-registration: v3 patterns with monthly momentum (sleeve and entry timing)

**Status: DRAFT (2026-11-14). Not frozen. No test code written.**

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
